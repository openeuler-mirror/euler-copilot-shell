package core

import (
	"context"
	"fmt"
	"strings"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

type askRunner struct {
	transport  Transport
	events     EventRouter
	sessions   SessionResolver
	renderer   TextRenderer
	presenter  EventPresenter
	permission InteractionManager
	serverURL  string
}

// NewAskRunner creates the shared ask execution pipeline.
func NewAskRunner(opts Options) (Runner, error) {
	if opts.Transport == nil {
		return nil, fmt.Errorf("ask transport is required")
	}
	if opts.Events == nil {
		return nil, fmt.Errorf("ask event router is required")
	}
	if opts.Sessions == nil {
		return nil, fmt.Errorf("ask session resolver is required")
	}
	return &askRunner{
		transport:  opts.Transport,
		events:     opts.Events,
		sessions:   opts.Sessions,
		renderer:   opts.Renderer,
		presenter:  opts.Presenter,
		permission: opts.Permission,
		serverURL:  opts.ServerURL,
	}, nil
}

func (r *askRunner) Run(ctx context.Context, req AskRequest) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	prompt := strings.TrimSpace(req.Prompt)
	if prompt == "" {
		return &presenter.UserError{Op: "ask", Err: fmt.Errorf("prompt is required")}
	}
	if req.ForceNew && strings.TrimSpace(req.SessionID) != "" {
		return &presenter.UserError{Op: "ask", Err: fmt.Errorf("session id cannot be combined with force new")}
	}
	if req.Mode == "" {
		req.Mode = ModeAsk
	}

	model, err := parseModel(req.Model)
	if err != nil {
		return err
	}

	runCtx, cancel := context.WithCancel(ctx)
	defer cancel()

	sessionCtx, err := r.resolveSession(runCtx, req)
	if err != nil {
		return decorateServerError(r.serverURL, fmt.Errorf("resolve session: %w", err))
	}

	directory := requestDirectory(sessionCtx, req.CWD)
	if model == nil {
		model = modelFromSession(sessionCtx)
	}
	if model == nil {
		model, err = r.defaultModel(runCtx, directory)
		if err != nil {
			return err
		}
	}

	events, errs := r.events.Subscribe(runCtx, sessionCtx.ID, transport.EventFilter{Directory: directory})
	promptReq := transport.PromptRequest{
		Directory: directory,
		Agent:     strings.TrimSpace(req.Agent),
		Parts:     []transport.PromptPart{{Type: "text", Text: prompt}},
	}
	if model != nil {
		promptReq.Model = model
	}
	if err := r.transport.SendPromptAsync(runCtx, sessionCtx.ID, promptReq); err != nil {
		return decorateServerError(r.serverURL, fmt.Errorf("send prompt: %w", err))
	}

	for events != nil || errs != nil {
		select {
		case <-runCtx.Done():
			_ = r.flushRenderer(context.WithoutCancel(runCtx))
			return runCtx.Err()
		case err, ok := <-errs:
			if !ok {
				errs = nil
				continue
			}
			if err != nil {
				_ = r.flushRenderer(context.WithoutCancel(runCtx))
				return decorateServerError(r.serverURL, fmt.Errorf("subscribe events: %w", err))
			}
		case evt, ok := <-events:
			if !ok {
				events = nil
				continue
			}
			done, err := r.handleEvent(runCtx, evt)
			if err != nil {
				_ = r.flushRenderer(context.WithoutCancel(runCtx))
				return err
			}
			if done {
				return r.flushRenderer(context.WithoutCancel(runCtx))
			}
		}
	}

	_ = r.flushRenderer(context.WithoutCancel(runCtx))
	return fmt.Errorf("ask runner: %w", ErrStreamEndedWithoutIdle)
}

func (r *askRunner) resolveSession(ctx context.Context, req AskRequest) (session.Context, error) {
	sessionID := strings.TrimSpace(req.SessionID)
	if sessionID != "" {
		return r.sessions.Continue(ctx, sessionID)
	}
	return r.sessions.Resolve(ctx, strings.TrimSpace(req.CWD), req.ForceNew)
}

func (r *askRunner) handleEvent(ctx context.Context, evt event.AppEvent) (bool, error) {
	switch evt.Kind {
	case event.EventTextDelta:
		payload, ok := evt.Payload.(event.TextDeltaPayload)
		if !ok {
			return false, &presenter.SchemaError{Op: "render text delta", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		if r.renderer == nil {
			return false, nil
		}
		return false, r.renderer.WriteDelta(ctx, payload.Delta)
	case event.EventStepStarted,
		event.EventStepEnded,
		event.EventToolCalled,
		event.EventToolSucceeded,
		event.EventToolFailed:
		if r.presenter == nil {
			return false, nil
		}
		return false, r.presenter.PresentEvent(ctx, evt)
	case event.EventPermissionAsked, event.EventQuestionAsked:
		if err := r.flushRenderer(ctx); err != nil {
			return false, err
		}
		if r.presenter != nil {
			if err := r.presenter.PresentEvent(ctx, evt); err != nil {
				return false, err
			}
		}
		if r.permission == nil {
			return false, fmt.Errorf("ask interaction: permission manager is not configured")
		}
		return false, r.permission.HandleEvent(ctx, evt)
	case event.EventSessionIdle:
		return true, nil
	default:
		return false, nil
	}
}

func (r *askRunner) flushRenderer(ctx context.Context) error {
	if r.renderer == nil {
		return nil
	}
	return r.renderer.Flush(ctx)
}

func (r *askRunner) defaultModel(ctx context.Context, directory string) (*transport.PromptModel, error) {
	defaults, err := r.transport.ProviderDefaults(ctx, directory, "")
	if err != nil {
		return nil, decorateServerError(r.serverURL, fmt.Errorf("resolve default model: %w", err))
	}
	if modelID := strings.TrimSpace(defaults.Default["opencode"]); modelID != "" {
		return &transport.PromptModel{ProviderID: "opencode", ModelID: modelID}, nil
	}
	for _, providerID := range defaults.Connected {
		modelID := strings.TrimSpace(defaults.Default[providerID])
		if providerID == "" || modelID == "" {
			continue
		}
		return &transport.PromptModel{ProviderID: providerID, ModelID: modelID}, nil
	}
	return nil, nil
}

func modelFromSession(sessionCtx session.Context) *transport.PromptModel {
	if sessionCtx.Session.Model == nil {
		return nil
	}
	providerID := strings.TrimSpace(sessionCtx.Session.Model.ProviderID)
	modelID := strings.TrimSpace(sessionCtx.Session.Model.ID)
	if providerID == "" || modelID == "" {
		return nil
	}
	return &transport.PromptModel{ProviderID: providerID, ModelID: modelID}
}

func parseModel(value string) (*transport.PromptModel, error) {
	trimmed := strings.TrimSpace(value)
	if trimmed == "" {
		return nil, nil
	}
	providerID, modelID, ok := strings.Cut(trimmed, "/")
	if !ok || strings.TrimSpace(providerID) == "" || strings.TrimSpace(modelID) == "" {
		return nil, &presenter.UserError{Op: "ask", Err: fmt.Errorf("model must use provider/model format")}
	}
	return &transport.PromptModel{
		ProviderID: strings.TrimSpace(providerID),
		ModelID:    strings.TrimSpace(modelID),
	}, nil
}

func requestDirectory(sessionCtx session.Context, cwd string) string {
	if sessionCtx.Directory != "" {
		return sessionCtx.Directory
	}
	return strings.TrimSpace(cwd)
}
