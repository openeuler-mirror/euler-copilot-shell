package core

import (
	"context"
	"errors"
	"fmt"
	"net"
	"net/url"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

// AskMode identifies the caller context for a prompt request.
type AskMode string

const (
	ModeAsk AskMode = "ask"
)

var ErrStreamEndedWithoutIdle = fmt.Errorf("event stream ended before session.idle")

// Runner executes the shared ask pipeline used by CLI, REPL, and shell entrypoints.
type Runner interface {
	Run(ctx context.Context, req AskRequest) error
}

// AskRequest contains the normalized inputs needed by the ask execution pipeline.
type AskRequest struct {
	Prompt    string
	CWD       string
	SessionID string
	ForceNew  bool
	Agent     string
	Model     string
	Variant   string
	Mode      AskMode
}

// SessionResolver resolves or continues the target session for a request.
type SessionResolver interface {
	Resolve(ctx context.Context, cwd string, forceNew bool) (session.Context, error)
	Continue(ctx context.Context, id string) (session.Context, error)
}

// EventRouter provides normalized event subscriptions scoped to a session.
type EventRouter interface {
	Subscribe(ctx context.Context, targetSessionID string, filter transport.EventFilter) (<-chan event.AppEvent, <-chan error)
}

// TextRenderer renders text deltas and flushes buffered output.
type TextRenderer interface {
	WriteDelta(ctx context.Context, delta string) error
	Flush(ctx context.Context) error
	// WriteReasoning writes reasoning (thinking) deltas with a separate visual
	// style, distinct from the final answer text. When the reasoning renderer
	// is disabled, this should be a no-op.
	WriteReasoning(ctx context.Context, delta string) error
	// FlushReasoning flushes any buffered reasoning text.
	FlushReasoning(ctx context.Context) error
	// ResetReasoning resets the first-paragraph flag so the next reasoning
	// block starts with a fresh "Thinking:" label.
	ResetReasoning()
	Resize(width int)
}

// EventPresenter renders structured non-text events.
type EventPresenter interface {
	PresentEvent(ctx context.Context, evt event.AppEvent) error
	PresentError(ctx context.Context, err error) error
	// PresentSessionIdle outputs the final answer summary line.
	// Called when session.idle is received (the only reliable stream-end signal).
	PresentSessionIdle(ctx context.Context) error
}

// InteractionManager handles permission/question events.
type InteractionManager interface {
	HandleEvent(ctx context.Context, evt event.AppEvent) error
	SetDirectory(dir string)
}

// Transport sends prompts to the server.
type Transport interface {
	ProviderDefaults(ctx context.Context, directory, workspace string) (transport.ProviderDefaults, error)
	SendPromptAsync(ctx context.Context, sessionID string, req transport.PromptRequest) error
}

// Options configures AskRunner dependencies.
type Options struct {
	Transport  Transport
	Events     EventRouter
	Sessions   SessionResolver
	Renderer   TextRenderer
	Presenter  EventPresenter
	Permission InteractionManager
	ServerURL  string
}

type serverError struct {
	ServerURL string
	Hint      string
	Err       error
}

func (e *serverError) Error() string {
	if e == nil {
		return ""
	}
	message := fmt.Sprintf("opencode server %s: %v", e.ServerURL, e.Err)
	if e.Hint != "" {
		message += "; " + e.Hint
	}
	return message
}

func (e *serverError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}

func decorateServerError(serverURL string, err error) error {
	if err == nil || serverURL == "" {
		return err
	}
	var existing *serverError
	if errors.As(err, &existing) {
		return err
	}
	var httpErr *transport.HTTPError
	if errors.As(err, &httpErr) {
		return &serverError{ServerURL: serverURL, Err: err}
	}
	if isNetworkError(err) {
		return &serverError{
			ServerURL: serverURL,
			Err:       err,
			Hint:      "ensure `opencode serve --port 4096` is running and reachable",
		}
	}
	return err
}

func isNetworkError(err error) bool {
	var netErr net.Error
	if errors.As(err, &netErr) {
		return true
	}
	var urlErr *url.Error
	if errors.As(err, &urlErr) {
		return true
	}
	var opErr *net.OpError
	return errors.As(err, &opErr)
}
