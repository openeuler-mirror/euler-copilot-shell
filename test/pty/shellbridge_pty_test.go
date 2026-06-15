//go:build pty

package pty

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"atomgit.com/openeuler/witty-cli/internal/shellinit"
	expect "github.com/Netflix/go-expect"
)

// TestShellbridge_SlashHelpRoute verifies /help is dispatched as a control command.
func TestShellbridge_SlashHelpRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/help")
	// Mock witty echoes "witty $@", so we expect "witty shell-control -- /help"
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /help"))
	if err != nil {
		t.Fatalf("expected /help to dispatch as control: %v", err)
	}
}

// TestShellbridge_SlashNewRoute verifies /new dispatches as a control command.
func TestShellbridge_SlashNewRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/new")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /new"))
	if err != nil {
		t.Fatalf("expected /new to dispatch as control: %v", err)
	}
}

// TestShellbridge_SlashSessionListRoute verifies /session list dispatches as control.
func TestShellbridge_SlashSessionListRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/session list")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /session list"))
	if err != nil {
		t.Fatalf("expected /session list to dispatch as control: %v", err)
	}
}

// TestShellbridge_SlashSessionContinueRoute verifies /session continue dispatches as control.
func TestShellbridge_SlashSessionContinueRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/session continue ses_1")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /session continue ses_1"))
	if err != nil {
		t.Fatalf("expected /session continue to dispatch as control: %v", err)
	}
}

// TestShellbridge_SlashAgentRoute verifies /agent dispatches as control.
func TestShellbridge_SlashAgentRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/agent build")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /agent build"))
	if err != nil {
		t.Fatalf("expected /agent to dispatch as control: %v", err)
	}
}

// TestShellbridge_SlashModelRoute verifies /model dispatches as control.
func TestShellbridge_SlashModelRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/model opencode/gpt-4")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /model opencode/gpt-4"))
	if err != nil {
		t.Fatalf("expected /model to dispatch as control: %v", err)
	}
}

// TestShellbridge_SlashExitRoute verifies /exit dispatches as control (not agent).
func TestShellbridge_SlashExitRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine("/exit")
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control -- /exit"))
	if err != nil {
		t.Fatalf("expected /exit to dispatch as control: %v", err)
	}
	// /exit must NOT go to the agent route (would be "witty ask -- /exit")
	if strings.Contains(output, "witty ask") {
		t.Fatal("/exit should dispatch as control, not agent route")
	}
}

// TestShellbridge_UsrBinLsRoute verifies /usr/bin/ls is NOT treated as a slash control.
func TestShellbridge_UsrBinLsRoute(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Put a real /usr/bin/ls in the mock path so bash can run it.
	// Symlink or copy /bin/ls into mockDir as "ls".
	realLs := "/bin/ls"
	if _, err := os.Stat(realLs); err != nil {
		realLs = "/usr/bin/ls"
	}
	lsContent, err := os.ReadFile(realLs)
	if err != nil {
		t.Skipf("cannot read ls binary: %v", err)
	}
	if err := os.WriteFile(filepath.Join(mockDir, "ls"), lsContent, 0o755); err != nil {
		t.Fatalf("write mock ls: %v", err)
	}

	// Type /usr/bin/ls — since PATH includes mockDir, it won't find /usr/bin/ls
	// directly, but the classifier should route it as shell because of explicit
	// path prefix, not as control.
	c.SendLine("/usr/bin/ls")
	// Since /usr/bin/ls may not exist in the PTY environment, bash will print
	// an error. The key is that it should NOT dispatch via witty (no "witty shell-control").
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("$ ", "# "))
	if err != nil {
		t.Fatalf("expected prompt after /usr/bin/ls: %v", err)
	}
	if strings.Contains(output, "witty shell-control") || strings.Contains(output, "witty ask") {
		t.Fatalf("/usr/bin/ls should not dispatch through witty: %q", output)
	}
}

// TestShellbridge_NaturalLanguageToAgent verifies that natural language input
// dispatches to the agent route.
func TestShellbridge_NaturalLanguageToAgent(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine(`检查系统内存`)
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask -- 检查系统内存`))
	if err != nil {
		t.Fatalf("expected witty ask for natural language: %v", err)
	}
}

// TestShellbridge_ShellCommandNotRewritten verifies regular shell commands
// pass through unchanged and are not rewritten to witty dispatch.
func TestShellbridge_ShellCommandNotRewritten(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	c.SendLine(`echo shell_ok`)
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("shell_ok"))
	if err != nil {
		t.Fatalf("expected shell command output 'shell_ok': %v", err)
	}
}

// TestShellbridge_HistoryNoWrapper verifies __witty_shell_dispatch does NOT
// appear in bash history after a natural language query.
func TestShellbridge_HistoryNoWrapper(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Natural language query.
	c.SendLine(`检查系统内存`)
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask`))
	if err != nil {
		t.Fatalf("expected witty ask: %v", err)
	}

	// Shell command.
	c.SendLine(`echo marker_1`)
	_, err = c.Expect(expect.WithTimeout(10*time.Second), expect.String("marker_1"))
	if err != nil {
		t.Fatalf("expected marker_1: %v", err)
	}

	// Check history.
	c.SendLine(`history`)
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String(`检查系统内存`))
	if err != nil {
		t.Fatalf("expected history to contain original input '检查系统内存': %v", err)
	}
	if strings.Contains(output, "__witty_shell_dispatch") {
		t.Fatalf("history contains __witty_shell_dispatch wrapper, but should not")
	}
}

// TestShellbridge_ControlHistoryNoWrapper verifies that slash control commands
// do not leak wrapper lines into history.
func TestShellbridge_ControlHistoryNoWrapper(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Send several control commands.
	c.SendLine("/help")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control"))
	if err != nil {
		t.Fatalf("expected /help dispatch: %v", err)
	}

	c.SendLine("/new")
	_, err = c.Expect(expect.WithTimeout(10*time.Second), expect.String("witty shell-control"))
	if err != nil {
		t.Fatalf("expected /new dispatch: %v", err)
	}

	// Check history.
	c.SendLine(`history`)
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("/new"))
	if err != nil {
		t.Fatalf("expected history to contain /new: %v", err)
	}
	if strings.Contains(output, "__witty_shell_dispatch") {
		t.Fatalf("history contains __witty_shell_dispatch wrapper, but should not")
	}
}

// setupMockWitty creates a temporary directory with a mock "witty" script.
func setupMockWitty(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	mock := filepath.Join(dir, "witty")
	content := `#!/bin/bash
# Mock witty for PTY tests — echoes "witty" prefix plus args.
echo witty "$@"
exit 0
`
	if err := os.WriteFile(mock, []byte(content), 0o755); err != nil {
		t.Fatalf("write mock witty: %v", err)
	}
	return dir
}

// writeWittyInitScript renders the witty Bash integration script and writes it
// to a temp file so bash can source it cleanly.
func writeWittyInitScript(t *testing.T, mockDir string) string {
	t.Helper()
	script := renderBashScript(t, mockDir)
	path := filepath.Join(t.TempDir(), "witty-init.bash")
	if err := os.WriteFile(path, []byte(script), 0o644); err != nil {
		t.Fatalf("write init script: %v", err)
	}
	return path
}

// renderBashScript generates the witty Bash integration script via shellinit.
func renderBashScript(t *testing.T, mockDir string) string {
	t.Helper()
	r := shellinit.NewRenderer()
	script, err := r.RenderBash(context.Background(), shellinit.BashOptions{
		BinaryPath:   filepath.Join(mockDir, "witty"),
		Version:      "test",
		ShellEnabled: true,
		ShellDebug:   false,
	})
	if err != nil {
		t.Fatalf("render bash script: %v", err)
	}
	return script
}

// startBash launches an interactive bash process using the console's Tty.
func startBash(t *testing.T, c *expect.Console, mockDir string) (*exec.Cmd, <-chan struct{}) {
	t.Helper()
	done := make(chan struct{})
	cmd := exec.Command("bash", "--norc", "--noprofile", "-i")
	cmd.Env = append(os.Environ(),
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=1",
		"PATH="+mockDir+":"+os.Getenv("PATH"),
	)
	cmd.Stdin = c.Tty()
	cmd.Stdout = c.Tty()
	cmd.Stderr = c.Tty()
	if err := cmd.Start(); err != nil {
		t.Fatalf("start bash: %v", err)
	}
	go func() {
		cmd.Wait()
		close(done)
	}()
	return cmd, done
}

// cleanupBash closes the Tty, waits briefly, then kills bash if still running.
func cleanupBash(t *testing.T, cmd *exec.Cmd, done <-chan struct{}, c *expect.Console) {
	t.Helper()
	c.Tty().Close()
	select {
	case <-done:
		return
	case <-time.After(2 * time.Second):
		if cmd.Process != nil {
			cmd.Process.Kill()
		}
		<-done
	}
}

// waitForPrompt waits until bash outputs its initial prompt.
func waitForPrompt(t *testing.T, c *expect.Console) {
	t.Helper()
	_, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("bash"))
	if err != nil {
		t.Fatalf("no bash prompt: %v", err)
	}
}

// sourceWittyScript sends a source command to load the witty init script.
func sourceWittyScript(t *testing.T, c *expect.Console, initPath string) {
	t.Helper()
	c.SendLine("source '" + initPath + "'")
	_, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("$ ", "# "))
	if err != nil {
		t.Fatalf("no prompt after sourcing witty script: %v", err)
	}
}
