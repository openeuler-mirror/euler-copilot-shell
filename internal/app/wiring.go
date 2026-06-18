package app

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/permission"
	"atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/renderer"
	"atomgit.com/openeuler/witty-cli/internal/repl"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/shellinit"
	"atomgit.com/openeuler/witty-cli/internal/terminal"
	"atomgit.com/openeuler/witty-cli/internal/transport"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

// Options contains process-level dependencies used by the composition root.
type Options struct {
	Config           config.LoadOptions
	Version          version.Info
	Stdout           io.Writer
	Stderr           io.Writer
	SessionStatePath string
}

// New loads config, initializes shared infrastructure, and returns the app container.
func New(ctx context.Context, opts Options) (Container, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	cfg, err := config.Load(opts.Config)
	if err != nil {
		return nil, err
	}

	stdout := stdoutWriter(opts.Stdout)
	stdoutFile := writerFile(stdout)
	isTTY := terminal.IsTerminal(stdoutFile)
	interactiveTTY := isTTY && terminal.IsTerminal(os.Stdin)

	logger := newLogger(cfg, stderrWriter(opts.Stderr))
	transportClient, err := transport.NewClient(transport.Options{
		BaseURL: cfg.ServerURL,
		Logger:  logger,
	})
	if err != nil {
		return nil, err
	}
	sessionResolver, err := session.NewService(session.Options{
		Transport: transportClient,
		StatePath: opts.SessionStatePath,
	})
	if err != nil {
		return nil, err
	}
	eventRouter := event.NewRouter(transportClient)
	width := terminal.Width(stdoutFile)

	var rendererService renderer.TextRenderer
	if cfg.RendererPhase >= 2 {
		rendererService, err = renderer.NewEchoRenderer(renderer.EchoOptions{
			Writer:        stdout,
			IsTTY:         isTTY,
			Width:         width,
			Theme:         cfg.Theme,
			NoColor:       cfg.NoColor,
			InputFile:     os.Stdin,
			OutputFile:    stdoutFile,
			Enabled:       true,
			ShowReasoning: cfg.Display.ShowReasoning,
		})
	} else {
		rendererService, err = renderer.NewMarkdownRenderer(renderer.Options{
			Writer:        stdout,
			IsTTY:         isTTY,
			Width:         width,
			Theme:         cfg.Theme,
			NoColor:       cfg.NoColor,
			InputFile:     os.Stdin,
			OutputFile:    stdoutFile,
			ShowReasoning: cfg.Display.ShowReasoning,
		})
	}
	if err != nil {
		return nil, fmt.Errorf("create renderer: %w", err)
	}

	// Listen for terminal resize signals and forward to the renderer.
	if isTTY {
		go watchTerminalResize(ctx, rendererService, stdoutFile, logger)
	}

	presenterService := presenter.NewPresenter(presenter.Options{
		Writer:       stdout,
		IsTTY:        isTTY,
		NoColor:      cfg.NoColor,
		StepStyle:    cfg.Display.StepStyle,
		GroupContext: cfg.Display.GroupContext,
		Width:        width,
	})
	var prompt terminal.Prompter
	if interactiveTTY {
		prompt = terminal.NewPrompter(os.Stdin, stdout)
	}
	permissionService, err := permission.NewManager(permission.Options{
		Transport:   transportClient,
		Prompt:      prompt,
		SelectFn:    adaptPermissionSelect(prompt),
		Writer:      stdout,
		Interactive: interactiveTTY,
	})
	if err != nil {
		return nil, fmt.Errorf("create permission manager: %w", err)
	}
	askRunner, err := core.NewAskRunner(core.Options{
		Transport:  transportClient,
		Events:     eventRouter,
		Sessions:   sessionResolver,
		Renderer:   rendererService,
		Presenter:  presenterService,
		Permission: permissionService,
		ServerURL:  cfg.ServerURL,
	})
	if err != nil {
		return nil, fmt.Errorf("create ask runner: %w", err)
	}

	replLoop, err := repl.New(repl.Options{
		Runner:       askRunner,
		Sessions:     sessionResolver,
		Transport:    transportClient,
		Config:       cfg,
		ConfigWriter: config.NewWriter(nil),
	})
	if err != nil {
		return nil, fmt.Errorf("create repl: %w", err)
	}

	return &App{
		cfg:          cfg,
		logger:       logger,
		transport:    transportClient,
		events:       eventRouter,
		sessions:     sessionResolver,
		renderer:     rendererService,
		presenter:    presenterService,
		permission:   permissionService,
		ask:          askRunner,
		repl:         replLoop,
		shellInit:    shellinit.NewRenderer(),
		version:      opts.Version,
		configWriter: config.NewWriter(nil),
	}, nil
}

func newLogger(cfg config.Config, stderr io.Writer) *slog.Logger {
	writer := writerOrDiscard(stderr)
	if !cfg.Debug && !isTTYWriter(writer) {
		writer = io.Discard
	}

	level := slog.LevelInfo
	if cfg.Debug {
		level = slog.LevelDebug
	}

	handlerOpts := &slog.HandlerOptions{Level: level}
	if cfg.Debug {
		handlerOpts.ReplaceAttr = func(_ []string, attr slog.Attr) slog.Attr {
			if attr.Key == slog.TimeKey {
				return slog.Attr{}
			}
			return attr
		}
	}

	return slog.New(slog.NewTextHandler(writer, handlerOpts))
}

func isTTYWriter(writer io.Writer) bool {
	return terminal.IsTerminal(writerFile(writer))
}

func writerFile(writer io.Writer) *os.File {
	file, ok := writer.(*os.File)
	if !ok {
		return nil
	}
	return file
}

// adaptPermissionSelect builds a permission.SelectFn from a terminal.Prompter
// by converting between the two packages' SelectOption types.
func adaptPermissionSelect(p terminal.Prompter) func(ctx context.Context, title string, options []permission.SelectOption) (int, error) {
	if p == nil {
		return nil
	}
	return func(ctx context.Context, title string, options []permission.SelectOption) (int, error) {
		termOpts := make([]terminal.SelectOption, len(options))
		for i, o := range options {
			termOpts[i] = terminal.SelectOption{Label: o.Label, Description: o.Description, Value: o.Value}
		}
		return p.Select(ctx, title, termOpts)
	}
}

// watchTerminalResize listens for SIGWINCH and notifies the renderer of
// width changes. It exits when ctx is cancelled.
func watchTerminalResize(ctx context.Context, r renderer.TextRenderer, stdoutFile *os.File, logger *slog.Logger) {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGWINCH)
	defer signal.Stop(ch)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ch:
			width := terminal.Width(stdoutFile)
			logger.Debug("terminal resize", "width", width)
			r.Resize(width)
		}
	}
}
