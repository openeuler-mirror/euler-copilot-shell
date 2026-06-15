//go:build pty

package pty

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	expect "github.com/Netflix/go-expect"
)

// TestRepl_SlashHelp verifies /help displays the slash command list and the REPL stays open.
func TestRepl_SlashHelp(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("/help")
	output, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("/session list"))
	if err != nil {
		t.Fatalf("expected /help to show /session list: %v", err)
	}
	if !strings.Contains(output, "/ask <prompt>") {
		t.Fatalf("/help output missing /ask: %q", output)
	}
	if !strings.Contains(output, "/exit") {
		t.Fatalf("/help output missing /exit: %q", output)
	}

	// Prompt should reappear — REPL stays open.
	_, err = c.Expect(expect.WithTimeout(3*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after /help: %v", err)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_SlashNew verifies /new sets the "fresh session" flag and REPL continues.
func TestRepl_SlashNew(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("/new")
	output, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("[new]"))
	if err != nil {
		t.Fatalf("expected [new] confirmation: %v", err)
	}
	if !strings.Contains(output, "fresh") && !strings.Contains(output, "new") {
		t.Fatalf("/new output missing confirmation: %q", output)
	}

	// Prompt should reappear.
	_, err = c.Expect(expect.WithTimeout(3*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after /new: %v", err)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_SlashUnknownSuggestion verifies that mistyped slash commands show suggestions.
func TestRepl_SlashUnknownSuggestion(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	// /hel should suggest /help
	c.SendLine("/hel")
	output, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("did you mean /help"))
	if err != nil {
		t.Fatalf("expected suggestion for /hel: %v; output=%q", err, output)
	}

	// /agnt should suggest /agent
	c.SendLine("/agnt")
	output, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("did you mean /agent"))
	if err != nil {
		t.Fatalf("expected suggestion for /agnt: %v; output=%q", err, output)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_SlashAskGracefulError verifies /ask without a server shows a graceful error.
func TestRepl_SlashAskGracefulError(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("/ask 检查系统内存")
	// Without a server, expect an error about the server not reachable.
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("[error]"))
	if err != nil {
		t.Fatalf("expected [error] from /ask without server: %v; output=%q", err, output)
	}

	// Prompt should reappear.
	_, err = c.Expect(expect.WithTimeout(3*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after /ask error: %v", err)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_SlashSessionListGracefulError verifies /session list without a server
// shows a graceful error and the REPL stays open.
func TestRepl_SlashSessionListGracefulError(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("/session list")
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("[error]"))
	if err != nil {
		t.Fatalf("expected [error] from /session list without server: %v; output=%q", err, output)
	}
	if !strings.Contains(output, "session list") {
		t.Fatalf("error should mention session list: %q", output)
	}

	// Prompt should reappear.
	_, err = c.Expect(expect.WithTimeout(3*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after /session list error: %v", err)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_SlashSessionContinueGracefulError verifies /session continue without
// a server shows a graceful error.
func TestRepl_SlashSessionContinueGracefulError(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("/session continue ses_fake")
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("[error]"))
	if err != nil {
		t.Fatalf("expected [error] from /session continue without server: %v; output=%q", err, output)
	}

	// Prompt should reappear.
	_, err = c.Expect(expect.WithTimeout(3*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after /session continue error: %v", err)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_AllExitCommands verifies all variants (/exit, /quit, /q) work in REPL.
func TestRepl_AllExitCommands(t *testing.T) {
	tests := []string{"/exit", "/quit", "/q"}
	for _, quitCmd := range tests {
		t.Run(quitCmd, func(t *testing.T) {
			c := newConsole(t, 10*time.Second)
			defer c.Close()

			cmd := startWitty(t, c)
			defer stopWitty(t, cmd, c)

			waitForReplPrompt(t, c)

			c.SendLine(quitCmd)
			waitForExit(t, cmd, 5*time.Second)
		})
	}
}

// TestRepl_UsrBinLsNotSlash verifies /usr/bin/ls is NOT treated as a slash command.
// It should be passed to the AI runner, which will error without a server.
func TestRepl_UsrBinLsNotSlash(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("/usr/bin/ls")
	// Since /usr/bin/ls is not a known slash command, it should be sent to the
	// runner (AI) which will fail to connect. We should see an error, NOT a
	// slash command suggestion.
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("[error]"))
	if err != nil {
		t.Fatalf("expected [error] for /usr/bin/ls sent to runner: %v; output=%q", err, output)
	}
	// It must NOT show a slash command suggestion like "did you mean".
	if strings.Contains(output, "did you mean") {
		t.Fatalf("/usr/bin/ls should NOT trigger slash command suggestion: %q", output)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// TestRepl_CtrlDExit verifies Ctrl+D exits the REPL cleanly.
func TestRepl_CtrlDExit(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.Send("\x04") // Ctrl+D

	exitDone := make(chan error, 1)
	go func() {
		exitDone <- cmd.Wait()
	}()

	select {
	case err := <-exitDone:
		if err != nil {
			t.Fatalf("witty exited with error after Ctrl+D: %v", err)
		}
	case <-time.After(5 * time.Second):
		cmd.Process.Kill()
		cmd.Wait()
		t.Fatal("witty did not exit after Ctrl+D")
	}
}

// TestRepl_EmptyInputShowsPrompt verifies that Enter on empty line re-displays prompt.
func TestRepl_EmptyInputShowsPrompt(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	cmd := startWitty(t, c)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	c.SendLine("")
	_, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after empty line: %v", err)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// --- Helpers ---

func newConsole(t *testing.T, timeout time.Duration) *expect.Console {
	t.Helper()
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(timeout))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	return c
}

func startWitty(t *testing.T, c *expect.Console) *exec.Cmd {
	t.Helper()
	wittyPath := buildWittyBinary(t)

	cmd := exec.Command(wittyPath, "--server-url", "http://127.0.0.1:14096")
	cmd.Env = append(os.Environ(),
		"TERM=xterm-256color",
		"NO_COLOR=1",
		"WITTY_MODEL=",
		"WITTY_VARIANT=",
	)
	cmd.Stdin = c.Tty()
	cmd.Stdout = c.Tty()
	cmd.Stderr = c.Tty()

	if err := cmd.Start(); err != nil {
		t.Fatalf("start witty: %v", err)
	}
	return cmd
}

func stopWitty(t *testing.T, cmd *exec.Cmd, c *expect.Console) {
	t.Helper()
	c.Tty().Close()
	if cmd.Process != nil {
		cmd.Process.Kill()
	}
	cmd.Wait()
}

func waitForReplPrompt(t *testing.T, c *expect.Console) {
	t.Helper()
	_, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected REPL prompt 'witty [build] > ': %v", err)
	}
}

func waitForExit(t *testing.T, cmd *exec.Cmd, timeout time.Duration) {
	t.Helper()
	exitDone := make(chan error, 1)
	go func() {
		exitDone <- cmd.Wait()
	}()
	select {
	case err := <-exitDone:
		if err != nil {
			t.Fatalf("witty exited with error: %v", err)
		}
	case <-time.After(timeout):
		cmd.Process.Kill()
		cmd.Wait()
		t.Fatal("witty did not exit in time")
	}
}

// buildWittyBinary compiles the witty binary and returns its path.
func buildWittyBinary(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	binPath := filepath.Join(dir, "witty")
	buildCmd := exec.Command("go", "build", "-o", binPath, "./cmd/witty")
	buildCmd.Dir = repoRoot(t)
	buildCmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := buildCmd.CombinedOutput(); err != nil {
		t.Fatalf("build witty: %v\n%s", err, string(out))
	}
	return binPath
}

// repoRoot returns the repository root directory.
func repoRoot(t *testing.T) string {
	t.Helper()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	for dir := wd; dir != "/" && dir != "."; dir = filepath.Dir(dir) {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
	}
	t.Fatal("cannot find repo root (no go.mod found)")
	return ""
}
