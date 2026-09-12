//go:build pty

package pty

import (
	"strings"
	"testing"
	"time"

	expect "github.com/Netflix/go-expect"
)

// TestShellbridge_OnlyTopLevelCommandsAreRouted pins the scope of the adapter:
// it rewrites the command line the user typed, not the commands a function
// executes.  `extdebug` makes the DEBUG trap inherited by shell functions,
// command substitutions and subshells (that is also what made command-heavy
// completions freeze the terminal), so the hook must bail out as soon as it
// fires inside a function.
func TestShellbridge_OnlyTopLevelCommandsAreRouted(t *testing.T) {
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

	// The marker is assembled at runtime so that the echoed function definition
	// cannot satisfy the expectation below.
	c.SendLine(`_witty_scope_probe() { printf '%s%s\n' scope_inner _marker; }`)
	if _, err := c.Expect(expect.WithTimeout(5*time.Second), expect.String("$ ", "# ")); err != nil {
		t.Fatalf("expected prompt after defining the function: %v", err)
	}

	c.SendLine("_witty_scope_probe")
	output, err := c.Expect(expect.WithTimeout(10*time.Second), expect.String("scope_inner_marker"))
	if err != nil {
		t.Fatalf("expected the function body to run: %v", err)
	}

	// Positive control: the user's own line is still classified.
	if !strings.Contains(output, "classify") {
		t.Fatalf("top-level command was not classified by the adapter: %q", output)
	}
	// The function body must stay untouched.
	if strings.Contains(output, "classify shell: printf") {
		t.Fatalf("command inside a function was classified by the trap: %q", output)
	}
	if strings.Contains(output, "witty ask") || strings.Contains(output, "witty shell-control") {
		t.Fatalf("command inside a function must not be dispatched to witty: %q", output)
	}
}
