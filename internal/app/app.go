package app

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"

	"atomgit.com/openeuler/euler-copilot-shell/internal/config"
	"atomgit.com/openeuler/euler-copilot-shell/internal/core"
	"atomgit.com/openeuler/euler-copilot-shell/internal/doctor"
	"atomgit.com/openeuler/euler-copilot-shell/internal/event"
	"atomgit.com/openeuler/euler-copilot-shell/internal/permission"
	"atomgit.com/openeuler/euler-copilot-shell/internal/presenter"
	"atomgit.com/openeuler/euler-copilot-shell/internal/renderer"
	"atomgit.com/openeuler/euler-copilot-shell/internal/repl"
	"atomgit.com/openeuler/euler-copilot-shell/internal/session"
	"atomgit.com/openeuler/euler-copilot-shell/internal/shellinit"
	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
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
	ListProviders(ctx context.Context) ([]ProviderStatus, error)
	ConnectProviderWithAPIKey(ctx context.Context, input, apiKey string) (ProviderStatus, error)
	ContinueSession(ctx context.Context, id string) (session.Context, error)
	StartREPL(ctx context.Context) error
	Doctor(ctx context.Context) (string, error)
	WriteConfig(ctx context.Context) config.Writer
}

type bashInitRenderer interface {
	RenderBash(ctx context.Context, opts shellinit.BashOptions) (string, error)
}

type App struct {
	cfg          config.Config
	logger       *slog.Logger
	transport    transport.Client
	events       event.Router
	sessions     session.Resolver
	renderer     renderer.TextRenderer
	presenter    presenter.Presenter
	permission   permission.Manager
	ask          core.Runner
	repl         repl.Loop
	shellInit    bashInitRenderer
	version      version.Info
	configWriter config.Writer
	doctor       doctor.Runner
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
	if req.Variant == "" {
		req.Variant = a.cfg.DefaultVariant
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
	renderer := a.shellInit
	if renderer == nil {
		renderer = shellinit.NewRenderer()
	}
	binaryPath := "witty"
	if exe, err := os.Executable(); err == nil {
		binaryPath = exe
	}
	return renderer.RenderBash(ctx, shellinit.BashOptions{
		BinaryPath:   binaryPath,
		Version:      a.version.Version,
		ShellEnabled: a.cfg.Shell.Enabled,
		ShellDebug:   a.cfg.Shell.Debug,
	})
}

func (a *App) ListSessions(ctx context.Context) ([]session.Summary, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	return a.sessions.List(ctx, session.Scope{})
}

func (a *App) WriteConfig(ctx context.Context) config.Writer {
	return a.configWriter
}

func (a *App) ContinueSession(ctx context.Context, id string) (session.Context, error) {
	if err := ctx.Err(); err != nil {
		return session.Context{}, err
	}
	return a.sessions.Continue(ctx, id)
}

func (a *App) StartREPL(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if a.repl == nil {
		return fmt.Errorf("repl is not configured")
	}
	return a.repl.Run(ctx)
}

func (a *App) Doctor(ctx context.Context) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	if a.doctor == nil {
		return "", fmt.Errorf("doctor runner is not configured")
	}
	checks := a.doctor.Run(ctx)
	return doctor.Format(checks), nil
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
