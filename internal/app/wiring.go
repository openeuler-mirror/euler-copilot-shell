package app

import (
	"context"
	"io"
	"log/slog"
	"os"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/terminal"
	"atomgit.com/openeuler/witty-cli/internal/transport"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

// Options contains process-level dependencies used by the composition root.
type Options struct {
	Config           config.LoadOptions
	Version          version.Info
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

	return &App{
		cfg:       cfg,
		logger:    logger,
		transport: transportClient,
		events:    eventRouter,
		sessions:  sessionResolver,
		version:   opts.Version,
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
	file, ok := writer.(*os.File)
	return ok && terminal.IsTerminal(file)
}
