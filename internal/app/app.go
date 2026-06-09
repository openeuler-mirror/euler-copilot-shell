package app

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/permission"
	"atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/renderer"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/transport"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

// Container exposes the narrow application surface used by CLI commands.
type Container interface {
	Config() config.Config
	Logger() *slog.Logger
	Transport() transport.Client
	Events() event.Router
	Sessions() session.Resolver
	Renderer() renderer.TextRenderer
	Presenter() presenter.Presenter
	Permission() permission.Manager
	Version() version.Info
	Ask(ctx context.Context, req core.AskRequest) error
	InitBash(ctx context.Context) (string, error)
	ListSessions(ctx context.Context) ([]session.Summary, error)
	ContinueSession(ctx context.Context, id string) (session.Context, error)
	Doctor(ctx context.Context) (string, error)
}

type App struct {
	cfg        config.Config
	logger     *slog.Logger
	transport  transport.Client
	events     event.Router
	sessions   session.Resolver
	renderer   renderer.TextRenderer
	presenter  presenter.Presenter
	permission permission.Manager
	ask        core.Runner
	version    version.Info
}

func (a *App) Config() config.Config {
	return a.cfg
}

func (a *App) Logger() *slog.Logger {
	return a.logger
}

func (a *App) Transport() transport.Client {
	return a.transport
}

func (a *App) Events() event.Router {
	return a.events
}

func (a *App) Sessions() session.Resolver {
	return a.sessions
}

func (a *App) Renderer() renderer.TextRenderer {
	return a.renderer
}

func (a *App) Presenter() presenter.Presenter {
	return a.presenter
}

func (a *App) Permission() permission.Manager {
	return a.permission
}

func (a *App) Version() version.Info {
	return a.version
}

func (a *App) Ask(ctx context.Context, req core.AskRequest) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if a.ask == nil {
		return fmt.Errorf("ask runner is not configured")
	}
	if req.Agent == "" {
		req.Agent = a.cfg.DefaultAgent
	}
	if req.Model == "" {
		req.Model = a.cfg.DefaultModel
	}
	if req.Mode == "" {
		req.Mode = core.ModeAsk
	}
	return a.ask.Run(ctx, req)
}

func (a *App) InitBash(ctx context.Context) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	return "# Witty Bash integration placeholder\n# Full Shell Adapter will be implemented in Phase 1.\n", nil
}

func (a *App) ListSessions(ctx context.Context) ([]session.Summary, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	return a.sessions.List(ctx, session.Scope{})
}

func (a *App) ContinueSession(ctx context.Context, id string) (session.Context, error) {
	if err := ctx.Err(); err != nil {
		return session.Context{}, err
	}
	return a.sessions.Continue(ctx, id)
}

func (a *App) Doctor(ctx context.Context) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	return fmt.Sprintf("witty doctor placeholder\nserver_url: %s\n", a.cfg.ServerURL), nil
}

func writerOrDiscard(writer io.Writer) io.Writer {
	if writer == nil {
		return io.Discard
	}
	return writer
}

func stdoutWriter(writer io.Writer) io.Writer {
	if writer == nil {
		return os.Stdout
	}
	return writer
}

func stderrWriter(writer io.Writer) io.Writer {
	if writer == nil {
		return os.Stderr
	}
	return writer
}
