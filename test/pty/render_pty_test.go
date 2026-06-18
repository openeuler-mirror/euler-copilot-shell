//go:build pty

package pty

import (
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"

	expect "github.com/Netflix/go-expect"
)

// TestRender_BasicToolAndReasoning verifies that witty renders tool calls,
// reasoning, and session idle summary correctly when connected to a mock
// opencode server.
func TestRender_BasicToolAndReasoning(t *testing.T) {
	mock := newMockOpenCode(defaultRenderEvents())
	defer mock.Close()

	c := newConsole(t, 30*time.Second)
	defer c.Close()

	cmd := startWittyWithServer(t, c, mock.URL)
	defer stopWitty(t, cmd, c)

	waitForReplPrompt(t, c)

	// Send a prompt via /ask.
	c.SendLine("/ask test")
	output, err := c.Expect(
		expect.WithTimeout(20*time.Second),
		expect.String("answered in"),
	)
	if err != nil {
		t.Fatalf("expected session idle summary: %v; output=%q", err, output)
	}

	// Verify tool call rendering: running indicator
	if !strings.Contains(output, "bash") {
		t.Errorf("output should contain bash tool: %q", output)
	}

	// Verify bash output indentation
	if !strings.Contains(output, "nsswitch.conf") {
		t.Errorf("output should contain bash output: %q", output)
	}

	// Verify no [step] text appears.
	if strings.Contains(output, "[step]") {
		t.Errorf("output should NOT contain [step] text: %q", output)
	}

	// Verify summary line format.
	if !strings.Contains(output, "answered in") {
		t.Errorf("output should contain 'answered in': %q", output)
	}

	// Verify agent/model don't show "unknown".
	if strings.Contains(output, "unknown") {
		t.Errorf("output should NOT contain 'unknown': %q", output)
	}

	c.SendLine("/exit")
	waitForExit(t, cmd, 5*time.Second)
}

// startWittyWithServer starts witty pointing at the given server URL.
func startWittyWithServer(t *testing.T, c *expect.Console, serverURL string) *exec.Cmd {
	t.Helper()
	wittyPath := buildWittyBinary(t)

	cmd := exec.Command(wittyPath,
		"--server-url", serverURL,
		"--model", "mock/mock-model",
	)
	cmd.Env = append(os.Environ(),
		"TERM=xterm-256color",
		"NO_COLOR=1",
	)
	cmd.Stdin = c.Tty()
	cmd.Stdout = c.Tty()
	cmd.Stderr = c.Tty()

	if err := cmd.Start(); err != nil {
		t.Fatalf("start witty: %v", err)
	}
	return cmd
}
