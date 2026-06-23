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

	"atomgit.com/openeuler/euler-copilot-shell/internal/shellbridge"
	"atomgit.com/openeuler/euler-copilot-shell/internal/shellinit"
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

// TestShellbridge_DebugMode verifies that WITTY_SHELL_DEBUG=1 outputs routing
// decisions (classify info) to stderr for agent-routed input.
func TestShellbridge_DebugMode(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=1",
		"WITTY_SHELL_DEBUG=1",
	})
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Natural language input should be classified as agent with debug output.
	c.SendLine(`检查系统内存`)
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask`))
	if err != nil {
		t.Fatalf("expected witty ask for natural language: %v", err)
	}
	// Debug output should contain classify routing decision on stderr.
	if !strings.Contains(output, "classify") {
		t.Fatalf("expected debug output containing 'classify', got: %q", output)
	}
}

// TestShellbridge_DisableSwitch verifies that WITTY_SHELL_ENABLE=0 prevents
// the DEBUG trap from installing and natural language falls through to bash's
// command_not_found_handle.
func TestShellbridge_DisableSwitch(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	// Render script with ShellEnabled=false so the template default matches.
	initPath := writeWittyInitScriptWithEnable(t, mockDir, false)
	bashCmd, bashDone := startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=0",
	})
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Natural language input should NOT be intercepted by the DEBUG trap.
	c.SendLine(`检查系统内存`)
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("command not found"))
	if err != nil {
		t.Fatalf("expected 'command not found' when shell adapter disabled: %v; output=%q", err, output)
	}
	// Must NOT dispatch through witty.
	if strings.Contains(output, "witty ask") || strings.Contains(output, "witty shell-control") {
		t.Fatal("disabled shell adapter should not dispatch to witty")
	}
}

// TestShellbridge_UninstallBindings verifies __witty_uninstall_bindings restores
// the previous DEBUG trap and subsequent natural language input is no longer
// intercepted by the witty adapter.
func TestShellbridge_UninstallBindings(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=1",
	})
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// First verify the adapter is active.
	c.SendLine(`检查系统内存`)
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask`))
	if err != nil {
		t.Fatalf("expected witty ask before uninstall: %v", err)
	}

	// Uninstall the witty bindings.
	c.SendLine(`__witty_uninstall_bindings`)
	_, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("$ ", "# "))
	if err != nil {
		t.Fatalf("no prompt after uninstall: %v", err)
	}

	// Now natural language should fall through to bash's command_not_found_handle.
	c.SendLine(`检查系统内存`)
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("command not found"))
	if err != nil {
		t.Fatalf("expected 'command not found' after uninstall: %v; output=%q", err, output)
	}
	if strings.Contains(output, "witty ask") || strings.Contains(output, "witty shell-control") {
		t.Fatal("uninstalled shell adapter should not dispatch to witty")
	}
}

// TestShellbridge_ViMode verifies that 'set -o vi' does not prevent natural
// language input from being routed to the agent via the DEBUG trap. Since the
// DEBUG trap does not bind to a specific keymap, vi mode should be transparent.
func TestShellbridge_ViMode(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScript(t, mockDir)
	bashCmd, bashDone := startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=1",
	})
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)

	// Switch to vi mode before sourcing witty.
	c.SendLine(`set -o vi`)
	_, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("$ ", "# "))
	if err != nil {
		t.Fatalf("no prompt after set -o vi: %v", err)
	}

	sourceWittyScript(t, c, initPath)

	// Natural language input (CJK) should still route to agent in vi mode.
	c.SendLine(`检查系统内存`)
	_, err = c.Expect(expect.WithTimeout(10*time.Second), expect.String(`witty ask`))
	if err != nil {
		t.Fatalf("expected witty ask in vi mode: %v", err)
	}
}

// TestShellbridge_DeferredDisableViaBashrc simulates the real-world
// login shell flow where /etc/profile.d/witty.sh sources the adapter
// first, and then ~/.bashrc disables it before the first interactive
// prompt. The deferred PROMPT_COMMAND installer must respect the
// WITTY_SHELL_ENABLE value set by .bashrc.
func TestShellbridge_DeferredDisableViaBashrc(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	// ShellEnabled=true so the system default is "enabled".
	initPath := writeWittyInitScript(t, mockDir)
	// Start bash WITHOUT WITTY_SHELL_ENABLE — simulate login shell env.
	bashCmd, bashDone := startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
	})
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)

	// Simulate /etc/profile.d/witty.sh sourcing the script followed
	// immediately by ~/.bashrc setting WITTY_SHELL_ENABLE=0.
	// Both happen before the next prompt, so the deferred installer
	// sees the disabled flag.
	c.SendLine("source " + shellbridge.ShellQuote(initPath) + "; export WITTY_SHELL_ENABLE=0")
	_, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("$ ", "# "))
	if err != nil {
		t.Fatalf("no prompt after sourcing and disabling: %v", err)
	}

	// Natural language input should NOT dispatch through witty.
	c.SendLine("检查系统内存")
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("command not found"))
	if err != nil {
		t.Fatalf("expected 'command not found' when disabled via .bashrc order: %v; output=%q", err, output)
	}
	if strings.Contains(output, "witty ask") || strings.Contains(output, "witty shell-control") {
		t.Fatal("shell adapter disabled via .bashrc order should not dispatch to witty")
	}
}

// TestShellbridge_CommandNotFoundNoWittyPrefix verifies that when
// the shell adapter is disabled, the overridden command_not_found_handle
// returns 127 without printing a "witty:" branded message.
func TestShellbridge_CommandNotFoundNoWittyPrefix(t *testing.T) {
	c := newConsole(t, 10*time.Second)
	defer c.Close()

	mockDir := setupMockWitty(t)
	initPath := writeWittyInitScriptWithEnable(t, mockDir, false)
	bashCmd, bashDone := startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=0",
	})
	defer cleanupBash(t, bashCmd, bashDone, c)

	waitForPrompt(t, c)
	sourceWittyScript(t, c, initPath)

	// Type a nonsense command that the classifier won't route to agent.
	c.SendLine("nonexistent_cmd_123")
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("command not found"))
	if err != nil {
		t.Fatalf("expected 'command not found': %v; output=%q", err, output)
	}
	if strings.Contains(output, "witty:") {
		t.Fatalf("disabled adapter must not print 'witty:' prefix; got: %q", output)
	}
}

// --- Helpers ---

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
	return writeWittyInitScriptWithEnable(t, mockDir, true)
}

// writeWittyInitScriptWithEnable renders the witty Bash integration script
// with a specified ShellEnabled default and writes it to a temp file.
func writeWittyInitScriptWithEnable(t *testing.T, mockDir string, enabled bool) string {
	t.Helper()
	r := shellinit.NewRenderer()
	script, err := r.RenderBash(context.Background(), shellinit.BashOptions{
		BinaryPath:   filepath.Join(mockDir, "witty"),
		Version:      "test",
		ShellEnabled: enabled,
		ShellDebug:   false,
	})
	if err != nil {
		t.Fatalf("render bash script: %v", err)
	}
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
	return startBashWithEnv(t, c, mockDir, []string{
		"TERM=xterm-256color",
		"WITTY_SHELL_ENABLE=1",
	})
}

// startBashWithEnv launches an interactive bash process with custom environment variables.
func startBashWithEnv(t *testing.T, c *expect.Console, mockDir string, extraEnv []string) (*exec.Cmd, <-chan struct{}) {
	t.Helper()
	done := make(chan struct{})
	cmd := exec.Command("bash", "--norc", "--noprofile", "-i")
	cmd.Env = append(os.Environ(), extraEnv...)
	cmd.Env = append(cmd.Env, "PATH="+mockDir+":"+os.Getenv("PATH"))
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
