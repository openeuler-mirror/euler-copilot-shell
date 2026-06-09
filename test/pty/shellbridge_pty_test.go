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

// TestShellbridge_NaturalLanguageToAgent verifies that typing natural language
// (Chinese) at the prompt triggers witty ask (agent route) via the Bash
// readline binding.
func TestShellbridge_NaturalLanguageToAgent(t *testing.T) {
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)

	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Type a natural language query and press Enter.
	c.SendLine(`检查系统内存`)

	// The mock witty echoes "witty $@" so expect "witty ask -- 检查系统内存".
	_, err = c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask -- 检查系统内存`))
	if err != nil {
		t.Fatalf("expected witty ask to be called for natural language input: %v", err)
	}
}

// TestShellbridge_ShellCommandNotRewritten verifies that regular shell commands
// pass through unchanged and are not rewritten to witty dispatch.
func TestShellbridge_ShellCommandNotRewritten(t *testing.T) {
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)

	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Type a regular shell command.
	c.SendLine(`echo shell_ok`)

	// Should see the echo output directly, not a witty dispatch.
	_, err = c.Expect(expect.WithTimeout(10*time.Second), expect.String("shell_ok"))
	if err != nil {
		t.Fatalf("expected shell command output 'shell_ok', but got error: %v", err)
	}
}

// TestShellbridge_HistoryNoWrapper verifies that __witty_shell_dispatch does
// NOT appear in bash history after a natural language query.
func TestShellbridge_HistoryNoWrapper(t *testing.T) {
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)

	bashCmd, bashDone := startBash(t, c, mockDir)
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Type a natural language query.
	c.SendLine(`检查系统内存`)
	_, err = c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask`))
	if err != nil {
		t.Fatalf("expected witty ask: %v", err)
	}

	// Type a shell command.
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

	// The wrapper line must NOT appear in history.
	if strings.Contains(output, "__witty_shell_dispatch") {
		t.Fatalf("history contains __witty_shell_dispatch wrapper, but should not")
	}
}

// setupMockWitty creates a temporary directory with a mock "witty" script that
// echoes "witty" followed by its arguments so tests can verify dispatch.
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
// to a temp file so bash can source it cleanly (avoids heredoc PTY issues).
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

// startBash launches an interactive bash process using the console's Tty as
// stdin/stdout/stderr. Returns the cmd and a channel that closes when bash exits.
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

	// Close the slave to send EOF to bash's stdin.
	c.Tty().Close()

	// Give bash a moment to exit on EOF.
	select {
	case <-done:
		return
	case <-time.After(2 * time.Second):
		// Bash didn't exit; kill it.
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

	// Use single quotes to protect the path.
	c.SendLine("source '" + initPath + "'")

	// Wait for the prompt to reappear after sourcing.
	_, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("$ ", "# "))
	if err != nil {
		t.Fatalf("no prompt after sourcing witty script: %v", err)
	}
}
