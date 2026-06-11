//go:build pty

package pty

import (
	"os"
	"os/exec"
	"path/filepath"
	"testing"
	"time"

	expect "github.com/Netflix/go-expect"
)

// TestRepl_PromptAndExit verifies that witty enters REPL mode when invoked
// without subcommands, displays the expected prompt, and exits cleanly
// on /exit and /quit commands. No opencode server is needed.
func TestRepl_PromptAndExit(t *testing.T) {
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	defer c.Close()

	wittyPath := buildWittyBinary(t)

	cmd := exec.Command(wittyPath, "--server-url", "http://127.0.0.1:14096")
	cmd.Env = append(os.Environ(),
		"TERM=xterm-256color",
		"NO_COLOR=1",
		// Override any host-level config to ensure deterministic prompt.
		"WITTY_MODEL=",
		"WITTY_VARIANT=",
	)
	cmd.Stdin = c.Tty()
	cmd.Stdout = c.Tty()
	cmd.Stderr = c.Tty()

	if err := cmd.Start(); err != nil {
		t.Fatalf("start witty: %v", err)
	}
	defer func() {
		c.Tty().Close()
		cmd.Process.Kill()
		cmd.Wait()
	}()

	// The REPL prompt should appear immediately.
	// Match substring to be robust against optional model/variant in the prompt.
	_, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected REPL prompt 'witty [build] > ': %v", err)
	}

	// /exit should exit the REPL cleanly.
	c.SendLine("/exit")

	exitDone := make(chan error, 1)
	go func() {
		exitDone <- cmd.Wait()
	}()

	select {
	case err := <-exitDone:
		if err != nil {
			t.Fatalf("witty exited with error after /exit: %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("witty did not exit after /exit")
	}
}

// TestRepl_QuitCommands verifies all accepted quit commands (/exit, /quit, /q).
func TestRepl_QuitCommands(t *testing.T) {
	tests := []string{"/exit", "/quit", "/q"}
	for _, quitCmd := range tests {
		t.Run(quitCmd, func(t *testing.T) {
			c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
			if err != nil {
				t.Fatalf("NewTestConsole() error = %v", err)
			}
			defer c.Close()

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

			// Wait for prompt (substring match for cross-env robustness).
			_, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
			if err != nil {
				cmd.Process.Kill()
				cmd.Wait()
				t.Fatalf("expected prompt: %v", err)
			}

			c.SendLine(quitCmd)

			exitDone := make(chan error, 1)
			go func() {
				exitDone <- cmd.Wait()
			}()

			select {
			case err := <-exitDone:
				if err != nil {
					t.Fatalf("witty exited with error after %s: %v", quitCmd, err)
				}
			case <-time.After(5 * time.Second):
				cmd.Process.Kill()
				cmd.Wait()
				t.Fatalf("witty did not exit after %s", quitCmd)
			}
		})
	}
}

// TestRepl_CtrlD_Exit verifies that Ctrl+D (EOF on stdin) exits the REPL cleanly.
// In a PTY, Ctrl+D is sent as the ASCII EOT character (\x04).
func TestRepl_CtrlD_Exit(t *testing.T) {
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	defer c.Close()

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

	// Wait for prompt
	_, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
	if err != nil {
		cmd.Process.Kill()
		cmd.Wait()
		t.Fatalf("expected prompt: %v", err)
	}

	// Send Ctrl+D via ASCII EOT (End-of-Transmission) character.
	// In canonical terminal mode, this triggers EOF on the reading end.
	c.Send("\x04")

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
		t.Fatal("witty did not exit after Ctrl+D (\\x04)")
	}
}

// TestRepl_EmptyInputShowsPrompt verifies that pressing Enter on an empty
// line re-displays the prompt without crashing.
func TestRepl_EmptyInputShowsPrompt(t *testing.T) {
	c, err := expect.NewTestConsole(t, expect.WithDefaultTimeout(10*time.Second))
	if err != nil {
		t.Fatalf("NewTestConsole() error = %v", err)
	}
	defer c.Close()

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
	defer func() {
		c.Tty().Close()
		cmd.Process.Kill()
		cmd.Wait()
	}()

	// First prompt
	_, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected first prompt: %v", err)
	}

	// Send empty line — should re-display prompt
	c.SendLine("")
	_, err = c.Expect(expect.WithTimeout(5*time.Second), expect.String("witty [build"))
	if err != nil {
		t.Fatalf("expected prompt after empty line: %v", err)
	}

	// Now exit cleanly
	c.SendLine("/exit")
	exitDone := make(chan error, 1)
	go func() {
		exitDone <- cmd.Wait()
	}()
	select {
	case err := <-exitDone:
		if err != nil {
			t.Fatalf("witty exited with error: %v", err)
		}
	case <-time.After(5 * time.Second):
		t.Fatal("witty did not exit")
	}
}

// buildWittyBinary compiles the witty binary and returns its path.
// The binary is cached across tests within the same test binary run via t.TempDir.
func buildWittyBinary(t *testing.T) string {
	t.Helper()

	// Use a fixed name so multiple tests reuse the same build.
	dir := t.TempDir()
	binPath := filepath.Join(dir, "witty")

	// go build -o <path> ./cmd/witty
	buildCmd := exec.Command("go", "build", "-o", binPath, "./cmd/witty")
	// Build from the module root: go up from test/pty/ to the repo root.
	buildCmd.Dir = repoRoot(t)
	buildCmd.Env = append(os.Environ(), "CGO_ENABLED=0")
	if out, err := buildCmd.CombinedOutput(); err != nil {
		t.Fatalf("build witty: %v\n%s", err, string(out))
	}

	return binPath
}

// repoRoot returns the repository root directory (parent of test/).
func repoRoot(t *testing.T) string {
	t.Helper()
	// test/pty/repl_pty_test.go → repo root is two levels up from test/pty/
	// We resolve relative to the working directory, which should be the repo root.
	wd, err := os.Getwd()
	if err != nil {
		t.Fatalf("getwd: %v", err)
	}
	// Walk up until we find go.mod
	for dir := wd; dir != "/" && dir != "."; dir = filepath.Dir(dir) {
		if _, err := os.Stat(filepath.Join(dir, "go.mod")); err == nil {
			return dir
		}
	}
	t.Fatal("cannot find repo root (no go.mod found)")
	return ""
}
