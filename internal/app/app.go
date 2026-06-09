package app

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"strings"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/permission"
	"atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/renderer"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/transport"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

var ErrStreamEndedWithoutIdle = fmt.Errorf("event stream ended before session.idle")

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
	Ask(ctx context.Context, prompt string) error
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

func (a *App) Ask(ctx context.Context, prompt string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	prompt = strings.TrimSpace(prompt)
	if prompt == "" {
		return &presenter.UserError{Op: "ask", Err: fmt.Errorf("prompt is required")}
	}

	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	sessionCtx, err := a.sessions.Resolve(runCtx, "", false)
	if err != nil {
		return fmt.Errorf("resolve session: %w", err)
	}

	events, errs := a.events.Subscribe(runCtx, sessionCtx.ID, transport.EventFilter{Directory: sessionCtx.Directory})
	req := transport.PromptRequest{
		Directory: sessionCtx.Directory,
		Agent:     a.cfg.DefaultAgent,
		Parts:     []transport.PromptPart{{Type: "text", Text: prompt}},
	}
	if err := a.transport.SendPromptAsync(runCtx, sessionCtx.ID, req); err != nil {
		return fmt.Errorf("send prompt: %w", err)
	}

	for events != nil || errs != nil {
		select {
		case <-runCtx.Done():
			return runCtx.Err()
		case err, ok := <-errs:
			if !ok {
				errs = nil
				continue
			}
			if err != nil {
				_ = a.flushRenderer(runCtx)
				return fmt.Errorf("subscribe events: %w", err)
			}
		case evt, ok := <-events:
			if !ok {
				events = nil
				continue
			}
			done, err := a.handleAskEvent(runCtx, evt)
			if err != nil {
				_ = a.flushRenderer(runCtx)
				return err
			}
			if done {
				return a.flushRenderer(runCtx)
			}
		}
	}

	_ = a.flushRenderer(runCtx)
	return fmt.Errorf("ask runner: %w", ErrStreamEndedWithoutIdle)
}

func (a *App) handleAskEvent(ctx context.Context, evt event.AppEvent) (bool, error) {
	switch evt.Kind {
	case event.EventTextDelta:
		payload, ok := evt.Payload.(event.TextDeltaPayload)
		if !ok {
			return false, &presenter.SchemaError{Op: "render text delta", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		if a.renderer == nil {
			return false, nil
		}
		return false, a.renderer.WriteDelta(ctx, payload.Delta)
	case event.EventStepStarted,
		event.EventStepEnded,
		event.EventToolCalled,
		event.EventToolSucceeded,
		event.EventToolFailed:
		if a.presenter == nil {
			return false, nil
		}
		return false, a.presenter.PresentEvent(ctx, evt)
	case event.EventPermissionAsked, event.EventQuestionAsked:
		if err := a.flushRenderer(ctx); err != nil {
			return false, err
		}
		if a.presenter != nil {
			if err := a.presenter.PresentEvent(ctx, evt); err != nil {
				return false, err
			}
		}
		if a.permission == nil {
			return false, fmt.Errorf("ask interaction: permission manager is not configured")
		}
		return false, a.permission.HandleEvent(ctx, evt)
	case event.EventSessionIdle:
		return true, nil
	default:
		return false, nil
	}
}

func (a *App) flushRenderer(ctx context.Context) error {
	if a.renderer == nil {
		return nil
	}
	return a.renderer.Flush(ctx)
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
