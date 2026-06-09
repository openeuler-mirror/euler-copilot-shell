package app

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/permission"
	"atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/renderer"
	"atomgit.com/openeuler/witty-cli/internal/session"
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
	rendererService, err := renderer.NewMarkdownRenderer(renderer.Options{
		Writer:     stdout,
		IsTTY:      isTTY,
		Width:      terminal.Width(stdoutFile),
		Theme:      cfg.Theme,
		NoColor:    cfg.NoColor,
		InputFile:  os.Stdin,
		OutputFile: stdoutFile,
	})
	if err != nil {
		return nil, fmt.Errorf("create renderer: %w", err)
	}
	presenterService := presenter.NewPresenter(presenter.Options{
		Writer:  stdout,
		IsTTY:   isTTY,
		NoColor: cfg.NoColor,
	})
	var prompt terminal.Prompter
	if interactiveTTY {
		prompt = terminal.NewPrompter(os.Stdin, stdout)
	}
	permissionService, err := permission.NewManager(permission.Options{
		Transport:   transportClient,
		Prompt:      prompt,
		Writer:      stdout,
		Interactive: interactiveTTY,
	})
	if err != nil {
		return nil, fmt.Errorf("create permission manager: %w", err)
	}

	return &App{
		cfg:        cfg,
		logger:     logger,
		transport:  transportClient,
		events:     eventRouter,
		sessions:   sessionResolver,
		renderer:   rendererService,
		presenter:  presenterService,
		permission: permissionService,
		version:    opts.Version,
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
