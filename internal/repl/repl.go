package repl

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
)

// Loop provides an interactive REPL that reads user input,
// dispatches to core.Runner for prompts, and handles control commands.
type Loop interface {
	Run(ctx context.Context) error
}

// Options configures the REPL loop.
type Options struct {
	Runner core.Runner
	Config config.Config
	CWD    string
	Stdin  io.Reader
	Stdout io.Writer
}

type repl struct {
	runner core.Runner
	cfg    config.Config
	cwd    string
	stdin  io.Reader
	stdout io.Writer
}

// New creates a REPL loop.
func New(opts Options) (Loop, error) {
	if opts.Runner == nil {
		return nil, fmt.Errorf("repl: runner is required")
	}
	if opts.Stdin == nil {
		opts.Stdin = os.Stdin
	}
	if opts.Stdout == nil {
		opts.Stdout = os.Stdout
	}
	if opts.CWD == "" {
		var err error
		opts.CWD, err = os.Getwd()
		if err != nil {
			return nil, fmt.Errorf("repl: resolve cwd: %w", err)
		}
	}
	return &repl{
		runner: opts.Runner,
		cfg:    opts.Config,
		cwd:    opts.CWD,
		stdin:  opts.Stdin,
		stdout: opts.Stdout,
	}, nil
}

func (r *repl) prompt() string {
	agent := r.cfg.DefaultAgent
	if agent == "" {
		agent = config.DefaultAgent
	}
	if r.cfg.DefaultModel != "" {
		return fmt.Sprintf("witty [%s:%s] > ", agent, r.cfg.DefaultModel)
	}
	return fmt.Sprintf("witty [%s] > ", agent)
}

// Run starts the REPL loop. It returns nil on clean exit (Ctrl+D or /exit).
// The parent ctx is used only to detect application-level cancellation (e.g., SIGTERM);
// SIGINT during the REPL loop only cancels the current ask, not the loop itself.
func (r *repl) Run(ctx context.Context) error {
	loopCtx := context.WithoutCancel(ctx)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT)
	defer signal.Stop(sigCh)

	var (
		askCancel   context.CancelFunc
		askCancelMu sync.Mutex
	)

	// Dedicated goroutine: SIGINT cancels current ask if one is running.
	go func() {
		for range sigCh {
			askCancelMu.Lock()
			cancel := askCancel
			askCancelMu.Unlock()
			if cancel != nil {
				cancel()
			}
		}
	}()

	scanner := bufio.NewScanner(r.stdin)
	fmt.Fprint(r.stdout, r.prompt())

	for {
		// Respect application-level cancellation.
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		if !scanner.Scan() {
			fmt.Fprintln(r.stdout)
			if err := scanner.Err(); err != nil {
				return fmt.Errorf("repl: read input: %w", err)
			}
			return nil
		}

		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			fmt.Fprint(r.stdout, r.prompt())
			continue
		}

		if isExitCommand(line) {
			return nil
		}

		// Execute the prompt through the shared ask pipeline.
		askCtx, cancel := context.WithCancel(loopCtx)
		askCancelMu.Lock()
		askCancel = cancel
		askCancelMu.Unlock()

		req := core.AskRequest{
			Prompt:  line,
			CWD:     r.cwd,
			Agent:   r.cfg.DefaultAgent,
			Model:   r.cfg.DefaultModel,
			Variant: r.cfg.DefaultVariant,
			Mode:    core.ModeAsk,
		}

		if err := r.runner.Run(askCtx, req); err != nil {
			if askCtx.Err() != nil {
				fmt.Fprintln(r.stdout, "\n[cancelled]")
			} else {
				fmt.Fprintf(r.stdout, "\n[error] %v\n", err)
			}
		}

		cancel()
		askCancelMu.Lock()
		askCancel = nil
		askCancelMu.Unlock()

		fmt.Fprintln(r.stdout)
		fmt.Fprint(r.stdout, r.prompt())
	}
}

func isExitCommand(input string) bool {
	lower := strings.ToLower(strings.TrimSpace(input))
	switch lower {
	case "/exit", "/quit", "/q":
		return true
	default:
		return false
	}
}
