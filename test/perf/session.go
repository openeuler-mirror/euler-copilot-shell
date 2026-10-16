//go:build perf

package perf

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/shellinit"
	"github.com/creack/pty"
)

// perfPrompt is the PS1 used by every perf session.  The harness synchronises
// on it, so it has to stay distinctive.
const perfPrompt = "witty-perf> "

// session drives an interactive Bash through a PTY.  Everything Bash writes is
// appended to a buffer, so callers synchronise on markers instead of sleeping.
type session struct {
	tb   testing.TB
	cmd  *exec.Cmd
	ptmx *os.File

	mu   sync.Mutex
	buf  []byte
	done chan struct{}
	seq  int

	closeOnce sync.Once
}

// startSession launches `bash --norc --noprofile -i` in a PTY with an isolated
// HOME and runs the given setup lines before returning.
func startSession(tb testing.TB, home string, setup ...string) *session {
	tb.Helper()
	requireBash5(tb)

	cmd := exec.Command("bash", "--norc", "--noprofile", "-i")
	cmd.Env = envWith(os.Environ(),
		"PS1="+perfPrompt,
		"TERM=xterm-256color",
		"HOME="+home,
		"INPUTRC=/dev/null",
		"LC_ALL=C.UTF-8",
		"WITTY_SHELL_ENABLE=1",
		"WITTY_SHELL_DEBUG=0",
	)

	ptmx, err := pty.StartWithSize(cmd, &pty.Winsize{Rows: 50, Cols: 200})
	if err != nil {
		tb.Fatalf("start interactive bash: %v", err)
	}

	s := &session{tb: tb, cmd: cmd, ptmx: ptmx, done: make(chan struct{})}
	go s.readLoop()
	tb.Cleanup(s.Close)

	s.waitFor(perfPrompt, 10*time.Second)
	s.drain(200 * time.Millisecond)
	for _, line := range setup {
		s.Run(line)
	}
	// Let PROMPT_COMMAND hooks finish (sourcing the witty init script defers the
	// trap installation to the next prompt) before the test starts.
	s.waitFor(perfPrompt, 10*time.Second)
	s.drain(200 * time.Millisecond)
	return s
}

// requireBash5 skips the test on platforms without a Bash that has readline
// trapping semantics (macOS ships Bash 3.2); PTY tests belong on openEuler.
func requireBash5(tb testing.TB) {
	tb.Helper()
	out, err := exec.Command("bash", "-c", `printf '%s' "${BASH_VERSINFO[0]}"`).Output()
	if err != nil {
		tb.Skipf("bash is not available: %v", err)
	}
	major, err := strconv.Atoi(strings.TrimSpace(string(out)))
	if err != nil || major < 5 {
		tb.Skipf("perf tests need Bash 5.x with readline (found %q); run them on openEuler",
			strings.TrimSpace(string(out)))
	}
}

// envWith returns base with the given KEY=VALUE entries applied, replacing any
// existing entry for the same key (later duplicates would be ambiguous).
func envWith(base []string, kv ...string) []string {
	replaced := make(map[string]bool, len(kv))
	for _, entry := range kv {
		key, _, _ := strings.Cut(entry, "=")
		replaced[key] = true
	}
	out := make([]string, 0, len(base)+len(kv))
	for _, entry := range base {
		key, _, _ := strings.Cut(entry, "=")
		if replaced[key] {
			continue
		}
		out = append(out, entry)
	}
	return append(out, kv...)
}

func (s *session) readLoop() {
	defer close(s.done)
	buf := make([]byte, 8192)
	for {
		n, err := s.ptmx.Read(buf)
		if n > 0 {
			s.mu.Lock()
			s.buf = append(s.buf, buf[:n]...)
			s.mu.Unlock()
		}
		if err != nil {
			return
		}
	}
}

// Send writes raw keys (including control characters) to the terminal.
func (s *session) Send(keys string) {
	s.tb.Helper()
	if _, err := s.ptmx.WriteString(keys); err != nil {
		s.tb.Fatalf("write to pty: %v", err)
	}
}

// Run sends one shell line and waits until Bash printed the line's marker.
func (s *session) Run(line string) string {
	s.tb.Helper()
	token := s.newToken("OK")
	s.Send(line + "; echo " + token + "\n")
	return s.waitForOutputLine(token, 30*time.Second)
}

// MeasureCompletion types keys followed by TAB and returns how long the shell
// needed to become responsive again.
//
// The marker line is sent as type-ahead while the completion runs: readline
// only echoes it once the completion has finished, so the time until the marker
// command runs is exactly the freeze the user experiences.  Ctrl-U discards
// whatever the completion left on the command line.
func (s *session) MeasureCompletion(keys string) time.Duration {
	s.tb.Helper()
	token := s.newToken("MARK")
	s.drain(150 * time.Millisecond)

	start := time.Now()
	s.Send(keys)
	s.Send("\x15echo " + token + "\n")
	s.waitForOutputLine(token, 60*time.Second)
	return time.Since(start)
}

// MeasureSeries runs MeasureCompletion repeats times.
func (s *session) MeasureSeries(keys string, repeats int) []time.Duration {
	s.tb.Helper()
	out := make([]time.Duration, 0, repeats)
	for i := 0; i < repeats; i++ {
		out = append(out, s.MeasureCompletion(keys))
	}
	return out
}

// Best returns the smallest duration: latency noise only ever adds time.
func Best(durations []time.Duration) time.Duration {
	best := time.Duration(0)
	for i, d := range durations {
		if i == 0 || d < best {
			best = d
		}
	}
	return best
}

// FormatDurations renders measurements for logs, e.g. "12ms,8ms,9ms (best 8ms)".
func FormatDurations(durations []time.Duration) string {
	parts := make([]string, 0, len(durations))
	for _, d := range durations {
		parts = append(parts, d.Round(time.Millisecond).String())
	}
	return strings.Join(parts, ",") + " (best " + Best(durations).Round(time.Millisecond).String() + ")"
}

// waitFor waits for a marker to show up in the session output.
func (s *session) waitFor(token string, timeout time.Duration) string {
	s.tb.Helper()
	return s.waitForOccurrence(token, 1, timeout)
}

// waitForOutputLine waits until token was printed as a line of its own, i.e. as
// the output of `echo token` rather than as part of the terminal echo of the
// typed command.
//
// Matching the echo would be racy: while a command is running, Bash keeps the
// terminal in canonical mode, so the kernel echoes pending input a first time
// and readline redraws it a second time at the next prompt.  Only the command
// output is a complete line containing just the token.
func (s *session) waitForOutputLine(token string, timeout time.Duration) string {
	s.tb.Helper()
	deadline := time.Now().Add(timeout)
	for {
		snapshot := string(s.snapshot())
		if idx, ok := outputLineIndex(snapshot, token); ok {
			end := idx + len(token)
			s.mu.Lock()
			consumed := string(s.buf[:min(end, len(s.buf))])
			if end <= len(s.buf) {
				s.buf = s.buf[end:]
			}
			s.mu.Unlock()
			return consumed
		}
		if time.Now().After(deadline) {
			s.tb.Fatalf("timed out after %s waiting for output line %q; last output: %q",
				timeout, token, tail(snapshot, 600))
		}
		time.Sleep(2 * time.Millisecond)
	}
}

// waitForOccurrence waits until token was printed n times, then consumes and
// returns everything up to the last match.  Failures include the tail of the
// output so a hanging shell is debuggable from the test log alone.
func (s *session) waitForOccurrence(token string, n int, timeout time.Duration) string {
	s.tb.Helper()
	deadline := time.Now().Add(timeout)
	for {
		snapshot := string(s.snapshot())
		if idx := nthIndex(snapshot, token, n); idx >= 0 {
			end := idx + len(token)
			s.mu.Lock()
			consumed := string(s.buf[:min(end, len(s.buf))])
			if end <= len(s.buf) {
				s.buf = s.buf[end:]
			}
			s.mu.Unlock()
			return consumed
		}
		if time.Now().After(deadline) {
			s.tb.Fatalf("timed out after %s waiting for %q (n=%d); last output: %q",
				timeout, token, n, tail(string(s.snapshot()), 600))
		}
		time.Sleep(2 * time.Millisecond)
	}
}

// drain reads until the shell has been quiet for idle.
func (s *session) drain(idle time.Duration) {
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		before := len(s.snapshot())
		time.Sleep(idle)
		if len(s.snapshot()) == before {
			s.mu.Lock()
			s.buf = s.buf[:0]
			s.mu.Unlock()
			return
		}
	}
}

func (s *session) snapshot() []byte {
	s.mu.Lock()
	defer s.mu.Unlock()
	return append([]byte(nil), s.buf...)
}

func (s *session) newToken(kind string) string {
	s.seq++
	return fmt.Sprintf("WITTY_PERF_%s_%d", kind, s.seq)
}

// Close kills the shell and releases the PTY.
func (s *session) Close() {
	s.closeOnce.Do(func() {
		if s.cmd.Process != nil {
			_ = s.cmd.Process.Kill()
		}
		_ = s.ptmx.Close()
		select {
		case <-s.done:
		case <-time.After(2 * time.Second):
		}
		_ = s.cmd.Wait()
	})
}

// newTestHome creates an isolated HOME for a perf session.  When sshHosts > 0
// it also generates a known_hosts file and an ssh config with that many
// entries, mirroring the environment size of a user who connects to lots of
// remote hosts - which is exactly what makes completion so expensive.
func newTestHome(tb testing.TB, sshHosts int) string {
	tb.Helper()
	home := tb.TempDir()
	if sshHosts <= 0 {
		return home
	}

	sshDir := filepath.Join(home, ".ssh")
	if err := os.MkdirAll(sshDir, 0o700); err != nil {
		tb.Fatalf("create %s: %v", sshDir, err)
	}
	var knownHosts, sshConfig strings.Builder
	for i := 0; i < sshHosts; i++ {
		fmt.Fprintf(&knownHosts, "host-%03d.example.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI%032d\n", i, i)
		fmt.Fprintf(&sshConfig, "Host cfg-%03d.example.com\n  HostName 10.0.%d.%d\n", i, i/250, i%250)
	}
	writeFile(tb, filepath.Join(sshDir, "known_hosts"), knownHosts.String(), 0o600)
	writeFile(tb, filepath.Join(sshDir, "config"), sshConfig.String(), 0o600)
	return home
}

// writeWittyStub writes a stand-in for the witty binary that records every
// invocation.  The Shell Adapter must never run it while the user is merely
// completing a line, so the perf tests assert that the log stays empty.
func writeWittyStub(tb testing.TB) (binaryPath, logPath string) {
	tb.Helper()
	dir := tb.TempDir()
	binaryPath = filepath.Join(dir, "witty")
	logPath = filepath.Join(dir, "witty-stub.log")
	writeFile(tb, binaryPath, "#!/bin/sh\nprintf '%s\\n' \"$*\" >> '"+logPath+"'\n", 0o755)
	return binaryPath, logPath
}

// writeWittyInit renders the current Bash integration script for a stub binary.
func writeWittyInit(tb testing.TB, binaryPath string) string {
	tb.Helper()
	script, err := shellinit.NewRenderer().RenderBash(context.Background(), shellinit.BashOptions{
		BinaryPath:   binaryPath,
		Version:      "perf",
		ShellEnabled: true,
		ShellDebug:   false,
	})
	if err != nil {
		tb.Fatalf("render witty bash init: %v", err)
	}
	path := filepath.Join(tb.TempDir(), "witty-init.bash")
	writeFile(tb, path, script, 0o644)
	return path
}

// writeScript writes a helper script (completion fixtures etc.) to disk.
func writeScript(tb testing.TB, name, content string) string {
	tb.Helper()
	path := filepath.Join(tb.TempDir(), name)
	writeFile(tb, path, content, 0o644)
	return path
}

func writeFile(tb testing.TB, path, content string, mode os.FileMode) {
	tb.Helper()
	if err := os.WriteFile(path, []byte(content), mode); err != nil {
		tb.Fatalf("write %s: %v", path, err)
	}
}

// trapCallsDuringCompletion wraps the witty DEBUG trap with a counter and
// reports how often the trap fired while a single completion ran.  The count
// says how heavy the completion is (bash-completion's ssh host scan fires it
// ~8000 times); whether that is acceptable is decided by the latency budget,
// which the adapter keeps green by returning early for anything that is not the
// command line the user typed.
func trapCallsDuringCompletion(tb testing.TB, home string, setup []string, keys string) int {
	tb.Helper()
	logPath := filepath.Join(tb.TempDir(), "trap-calls.log")
	counter := "trap 'printf . >> " + logPath + "; __witty_debug_hook' DEBUG"
	setupLines := append(append([]string{}, setup...), counter)
	s := startSession(tb, home, setupLines...)
	s.Run(": > " + logPath)
	_ = os.Remove(logPath)

	s.drain(150 * time.Millisecond)
	token := s.newToken("TRAPS")
	s.Send(keys)
	s.Send("\x15echo " + token + "\n")
	// Wait for the shell to be responsive again, otherwise a slow completion
	// would still be running when the counter is read.
	s.waitForOutputLine(token, 60*time.Second)

	info, err := os.Stat(logPath)
	if err != nil {
		tb.Fatalf("read trap-call log: %v", err)
	}
	return int(info.Size())
}

// nthIndex returns the byte offset of the nth occurrence of sep, or -1.
func nthIndex(haystack, sep string, n int) int {
	idx, offset := -1, 0
	for i := 0; i < n; i++ {
		found := strings.Index(haystack[offset:], sep)
		if found < 0 {
			return -1
		}
		idx = offset + found
		offset = idx + len(sep)
	}
	return idx
}

// outputLineIndex reports the offset of token when it appears as a complete
// line: at the start of a line and terminated by a newline.
func outputLineIndex(haystack, token string) (int, bool) {
	for offset := 0; ; {
		found := strings.Index(haystack[offset:], token)
		if found < 0 {
			return -1, false
		}
		idx := offset + found
		offset = idx + len(token)

		if idx != 0 && haystack[idx-1] != '\n' && haystack[idx-1] != '\r' {
			continue
		}
		rest := haystack[idx+len(token):]
		if strings.HasPrefix(rest, "\r\n") || strings.HasPrefix(rest, "\n") {
			return idx, true
		}
		// The terminating newline may simply not have arrived yet; wait for it
		// instead of matching the echo of a typed-ahead command.
	}
}

func tail(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[len(s)-n:]
}
