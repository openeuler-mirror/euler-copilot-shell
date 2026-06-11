package repl

import (
	"context"
	"errors"
	"io"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/terminal"
)

type fakeRunner struct {
	runFn func(ctx context.Context, req core.AskRequest) error
	calls atomic.Int64
}

func (f *fakeRunner) Run(ctx context.Context, req core.AskRequest) error {
	f.calls.Add(1)
	if f.runFn != nil {
		return f.runFn(ctx, req)
	}
	return nil
}

func (f *fakeRunner) callCount() int64 {
	return f.calls.Load()
}

func TestNew_ValidatesRunner(t *testing.T) {
	_, err := New(Options{Runner: nil, Config: config.Default()})
	if err == nil {
		t.Fatal("expected error when runner is nil")
	}
}

func TestNew_Defaults(t *testing.T) {
	runner := &fakeRunner{}
	loop, err := New(Options{Runner: runner, Config: config.Default()})
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	if loop == nil {
		t.Fatal("loop is nil")
	}
}

func TestPrompt_WithModel(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	cfg.DefaultModel = "opencode/gpt-4"
	r := &repl{cfg: cfg}
	prompt := r.prompt()
	expected := "witty [build:opencode/gpt-4] > "
	if prompt != expected {
		t.Fatalf("prompt = %q, want %q", prompt, expected)
	}
}

func TestPrompt_WithoutModel(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	cfg.DefaultModel = ""
	r := &repl{cfg: cfg}
	prompt := r.prompt()
	expected := "witty [build] > "
	if prompt != expected {
		t.Fatalf("prompt = %q, want %q", prompt, expected)
	}
}

func TestPrompt_DefaultAgentFallback(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = ""
	r := &repl{cfg: cfg}
	prompt := r.prompt()
	if !strings.Contains(prompt, config.DefaultAgent) {
		t.Fatalf("prompt %q should contain default agent %q", prompt, config.DefaultAgent)
	}
}

func TestIsExitCommand(t *testing.T) {
	tests := []struct {
		input    string
		expected bool
	}{
		{"/exit", true},
		{"/EXIT", true},
		{"/quit", true},
		{"/Quit", true},
		{"/q", true},
		{"/Q", true},
		{" /exit ", true},
		{"/help", false},
		{"hello", false},
		{"exit", false},
		{"", false},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			if got := isExitCommand(tt.input); got != tt.expected {
				t.Fatalf("isExitCommand(%q) = %v, want %v", tt.input, got, tt.expected)
			}
		})
	}
}

func TestRun_ExitOnEOF(t *testing.T) {
	runner := &fakeRunner{}
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader(""),
		Stdout: io.Discard,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	ctx := context.Background()
	if err := loop.Run(ctx); err != nil {
		t.Fatalf("Run() returned error on EOF: %v", err)
	}
}

func TestRun_ExitOnCommand(t *testing.T) {
	for _, cmd := range []string{"/exit\n", "/quit\n", "/q\n"} {
		t.Run(cmd, func(t *testing.T) {
			runner := &fakeRunner{}
			loop, err := New(Options{
				Runner: runner,
				Config: config.Default(),
				Stdin:  strings.NewReader(cmd),
				Stdout: io.Discard,
				CWD:    "/tmp",
			})
			if err != nil {
				t.Fatal(err)
			}

			if err := loop.Run(context.Background()); err != nil {
				t.Fatalf("Run() returned error on %s: %v", cmd, err)
			}
			if runner.callCount() != 0 {
				t.Fatalf("runner called %d times for exit command %s", runner.callCount(), cmd)
			}
		})
	}
}

func TestRun_DispatchesToRunner(t *testing.T) {
	runner := &fakeRunner{}
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader("check memory\n/exit\n"),
		Stdout: io.Discard,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("runner call count = %d, want 1", runner.callCount())
	}
}

func TestRun_SkipsBlankLines(t *testing.T) {
	runner := &fakeRunner{}
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader("\n\n\n/exit\n"),
		Stdout: io.Discard,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 0 {
		t.Fatalf("runner called %d times for blank lines", runner.callCount())
	}
}

func TestRun_MultiplePrompts(t *testing.T) {
	runner := &fakeRunner{}
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader("first\nsecond\nthird\n/exit\n"),
		Stdout: io.Discard,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 3 {
		t.Fatalf("runner call count = %d, want 3", runner.callCount())
	}
}

func TestRun_RespectsParentCancellation(t *testing.T) {
	// Parent cancellation before the loop starts should be respected.
	runner := &fakeRunner{}
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader(""),
		Stdout: io.Discard,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	if err := loop.Run(ctx); err != nil {
		t.Fatalf("Run() returned unexpected error: %v", err)
	}
}

func TestRun_RespectsParentCancellationBetweenAsks(t *testing.T) {
	// After an ask completes, if the parent context is cancelled,
	// the REPL should exit on the next ctx.Done() check.
	// Use a pipe: write one line, then close on cancel to unblock scanner.
	r, w := io.Pipe()

	go func() {
		if _, err := w.Write([]byte("first\n")); err != nil {
			return
		}
	}()

	runner := &fakeRunner{}
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  r,
		Stdout: io.Discard,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	ctx, cancel := context.WithCancel(context.Background())

	done := make(chan error, 1)
	go func() {
		done <- loop.Run(ctx)
	}()

	// Wait for the ask to finish, then cancel and close the pipe
	// to unblock the scanner for the next read.
	time.Sleep(200 * time.Millisecond)
	cancel()
	w.Close()

	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Run() returned unexpected error: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("Run() did not return after parent cancellation")
	}
}

func TestRun_ErrorInRunner(t *testing.T) {
	runner := &fakeRunner{
		runFn: func(ctx context.Context, req core.AskRequest) error {
			return errors.New("something went wrong")
		},
	}
	var out strings.Builder
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader("bad prompt\n/exit\n"),
		Stdout: &out,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	output := out.String()
	if !strings.Contains(output, "something went wrong") {
		t.Fatalf("output %q should contain error message", output)
	}
}

func TestRun_SkippedValidation(t *testing.T) {
	// Verify that invalid input to core.Runner is handled gracefully in REPL context.
	runner := &fakeRunner{
		runFn: func(ctx context.Context, req core.AskRequest) error {
			if strings.TrimSpace(req.Prompt) == "" {
				return errors.New("prompt is required")
			}
			return nil
		},
	}
	// The REPL already trims input, so blank lines are skipped.
	// This test verifies the runner itself gets valid prompts.
	var out strings.Builder
	loop, err := New(Options{
		Runner: runner,
		Config: config.Default(),
		Stdin:  strings.NewReader("valid\n/exit\n"),
		Stdout: &out,
		CWD:    "/tmp",
	})
	if err != nil {
		t.Fatal(err)
	}

	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("call count = %d, want 1", runner.callCount())
	}
}

// Ensure the Loop interface is satisfied.
var _ Loop = (*repl)(nil)

// Ensure terminal.Prompter is not required (scanner-based REPL).
var _ = terminal.Prompter(nil) // compile-time check that package is importable
