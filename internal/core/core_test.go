package core

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"reflect"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/transport"
	generated "atomgit.com/openeuler/witty-cli/internal/transport/generated"
)

func TestAskRunner_Run_CompletesAndBuildsPromptRequest(t *testing.T) {
	renderer := &fakeTextRenderer{}
	presenter := &fakePresenter{}
	transportClient := &fakeTransport{}
	sessions := &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}}
	router := &fakeRouter{events: []event.AppEvent{
		{Kind: event.EventStepStarted},
		{Kind: event.EventTextDelta, Payload: event.TextDeltaPayload{Delta: "hello\n\n"}},
		{Kind: event.EventToolFailed, Payload: event.ToolResultPayload{CallID: "call_1", Error: "boom"}},
		{Kind: event.EventSessionIdle},
	}}
	runner := mustRunner(t, Options{
		Transport: transportClient,
		Events:    router,
		Sessions:  sessions,
		Renderer:  renderer,
		Presenter: presenter,
	})

	err := runner.Run(context.Background(), AskRequest{
		Prompt:   "hello",
		CWD:      "/work",
		ForceNew: true,
		Agent:    "build",
		Model:    "opencode/gpt-5.1-codex",
		Variant:  "reasoning-high",
		Mode:     ModeAsk,
	})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if sessions.resolveCalls != 1 || sessions.resolveCWD != "/work" || !sessions.resolveForceNew {
		t.Fatalf("resolve calls/cwd/forceNew = %d/%q/%v", sessions.resolveCalls, sessions.resolveCWD, sessions.resolveForceNew)
	}
	if sessions.continueCalls != 0 {
		t.Fatalf("continue calls = %d, want 0", sessions.continueCalls)
	}
	if router.targetSessionID != "ses_1" {
		t.Fatalf("target session = %q, want ses_1", router.targetSessionID)
	}
	if router.filter.Directory != "/work" {
		t.Fatalf("event filter directory = %q, want /work", router.filter.Directory)
	}
	if transportClient.sentSessionID != "ses_1" {
		t.Fatalf("SendPromptAsync session = %q, want ses_1", transportClient.sentSessionID)
	}
	if transportClient.promptReq.Directory != "/work" {
		t.Fatalf("prompt directory = %q, want /work", transportClient.promptReq.Directory)
	}
	if transportClient.promptReq.Agent != "build" {
		t.Fatalf("prompt agent = %q, want build", transportClient.promptReq.Agent)
	}
	if transportClient.promptReq.Model == nil || transportClient.promptReq.Model.ProviderID != "opencode" || transportClient.promptReq.Model.ModelID != "gpt-5.1-codex" {
		t.Fatalf("prompt model = %+v, want provider/model split", transportClient.promptReq.Model)
	}
	if transportClient.promptReq.Variant != "reasoning-high" {
		t.Fatalf("prompt variant = %q, want reasoning-high", transportClient.promptReq.Variant)
	}
	if got := transportClient.promptReq.Parts; len(got) != 1 || got[0].Type != "text" || got[0].Text != "hello" {
		t.Fatalf("prompt parts = %+v", got)
	}
	if !reflect.DeepEqual(renderer.deltas, []string{"hello\n\n"}) {
		t.Fatalf("renderer deltas = %#v", renderer.deltas)
	}
	if renderer.flushCount != 1 {
		t.Fatalf("renderer flush count = %d, want 1", renderer.flushCount)
	}
	if !reflect.DeepEqual(presenter.events, []event.AppEventKind{event.EventStepStarted, event.EventToolFailed}) {
		t.Fatalf("presented events = %#v", presenter.events)
	}
}

func TestAskRunner_Run_UsesSessionModelWhenModelOmitted(t *testing.T) {
	transportClient := &fakeTransport{}
	runner := mustRunner(t, Options{
		Transport: transportClient,
		Events:    &fakeRouter{events: []event.AppEvent{{Kind: event.EventSessionIdle}}},
		Sessions: &fakeSessions{resolved: session.Context{
			ID:        "ses_1",
			Directory: "/work",
			Session: transport.Session{
				Model: &generated.SessionModel{ID: "big-pickle", ProviderID: "opencode"},
			},
		}},
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work"})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if transportClient.providerDefaultsCalls != 0 {
		t.Fatalf("ProviderDefaults calls = %d, want 0 when session model is available", transportClient.providerDefaultsCalls)
	}
	if transportClient.promptReq.Model == nil || transportClient.promptReq.Model.ProviderID != "opencode" || transportClient.promptReq.Model.ModelID != "big-pickle" {
		t.Fatalf("prompt model = %+v, want session model", transportClient.promptReq.Model)
	}
}

func TestAskRunner_Run_UsesConnectedDefaultModelWhenModelOmitted(t *testing.T) {
	transportClient := &fakeTransport{providerDefaults: transport.ProviderDefaults{
		Connected: []string{"zhipuai", "opencode", "deepseek"},
		Default: map[string]string{
			"zhipuai":  "glm-5v-turbo",
			"opencode": "big-pickle",
			"deepseek": "deepseek-v4-pro",
		},
	}}
	runner := mustRunner(t, Options{
		Transport: transportClient,
		Events:    &fakeRouter{events: []event.AppEvent{{Kind: event.EventSessionIdle}}},
		Sessions:  &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work"})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if transportClient.providerDefaultsCalls != 1 {
		t.Fatalf("ProviderDefaults calls = %d, want 1", transportClient.providerDefaultsCalls)
	}
	if transportClient.providerDefaultsDirectory != "/work" {
		t.Fatalf("ProviderDefaults directory = %q, want /work", transportClient.providerDefaultsDirectory)
	}
	if transportClient.promptReq.Model == nil {
		t.Fatal("prompt model = nil, want connected provider default")
	}
	if transportClient.promptReq.Model.ProviderID != "opencode" || transportClient.promptReq.Model.ModelID != "big-pickle" {
		t.Fatalf("prompt model = %+v, want opencode/big-pickle preference", transportClient.promptReq.Model)
	}
}

func TestAskRunner_Run_SkipsDisconnectedOpencodeDefaultModel(t *testing.T) {
	transportClient := &fakeTransport{providerDefaults: transport.ProviderDefaults{
		Connected: []string{"deepseek"},
		Default: map[string]string{
			"opencode": "big-pickle",
			"deepseek": "deepseek-v4-pro",
		},
	}}
	runner := mustRunner(t, Options{
		Transport: transportClient,
		Events:    &fakeRouter{events: []event.AppEvent{{Kind: event.EventSessionIdle}}},
		Sessions:  &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work"})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if transportClient.promptReq.Model == nil {
		t.Fatal("prompt model = nil, want connected provider default")
	}
	if transportClient.promptReq.Model.ProviderID != "deepseek" || transportClient.promptReq.Model.ModelID != "deepseek-v4-pro" {
		t.Fatalf("prompt model = %+v, want deepseek/deepseek-v4-pro", transportClient.promptReq.Model)
	}
}

func TestAskRunner_Run_ContinuesExplicitSession(t *testing.T) {
	transportClient := &fakeTransport{}
	sessions := &fakeSessions{continued: session.Context{ID: "ses_continue", Directory: "/continued"}}
	router := &fakeRouter{events: []event.AppEvent{{Kind: event.EventSessionIdle}}}
	runner := mustRunner(t, Options{Transport: transportClient, Events: router, Sessions: sessions})

	err := runner.Run(context.Background(), AskRequest{Prompt: "continue", CWD: "/current", SessionID: "ses_continue"})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if sessions.continueCalls != 1 || sessions.continueID != "ses_continue" {
		t.Fatalf("continue calls/id = %d/%q", sessions.continueCalls, sessions.continueID)
	}
	if sessions.resolveCalls != 0 {
		t.Fatalf("resolve calls = %d, want 0", sessions.resolveCalls)
	}
	if router.filter.Directory != "/continued" {
		t.Fatalf("event filter directory = %q, want /continued", router.filter.Directory)
	}
	if transportClient.promptReq.Directory != "/continued" {
		t.Fatalf("prompt directory = %q, want /continued", transportClient.promptReq.Directory)
	}
}

func TestAskRunner_Run_EOFBeforeIdleFlushesAndReturnsError(t *testing.T) {
	renderer := &fakeTextRenderer{}
	runner := mustRunner(t, Options{
		Transport: &fakeTransport{},
		Events: &fakeRouter{events: []event.AppEvent{
			{Kind: event.EventTextDelta, Payload: event.TextDeltaPayload{Delta: "tail"}},
		}},
		Sessions: &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
		Renderer: renderer,
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work"})
	if !errors.Is(err, ErrStreamEndedWithoutIdle) {
		t.Fatalf("Run() error = %v, want ErrStreamEndedWithoutIdle", err)
	}
	if renderer.flushCount != 1 {
		t.Fatalf("renderer flush count = %d, want 1", renderer.flushCount)
	}
}

func TestAskRunner_Run_FlushesBeforePermissionAndQuestion(t *testing.T) {
	trace := []string{}
	renderer := &fakeTextRenderer{trace: &trace}
	presenter := &fakePresenter{}
	permission := &fakePermissionManager{trace: &trace}
	runner := mustRunner(t, Options{
		Transport: &fakeTransport{},
		Events: &fakeRouter{events: []event.AppEvent{
			{Kind: event.EventTextDelta, Payload: event.TextDeltaPayload{Delta: "hello"}},
			{Kind: event.EventPermissionAsked, Payload: event.PermissionAskedPayload{RequestID: "per_1", Permission: "tool"}},
			{Kind: event.EventQuestionAsked, Payload: event.QuestionAskedPayload{RequestID: "que_1", Questions: []event.QuestionInfo{{Question: "Continue?"}}}},
			{Kind: event.EventSessionIdle},
		}},
		Sessions:   &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
		Renderer:   renderer,
		Presenter:  presenter,
		Permission: permission,
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work"})
	if err != nil {
		t.Fatalf("Run() error = %v", err)
	}
	if !reflect.DeepEqual(permission.events, []event.AppEventKind{event.EventPermissionAsked, event.EventQuestionAsked}) {
		t.Fatalf("interaction events = %#v, want permission/question", permission.events)
	}
	if !reflect.DeepEqual(presenter.events, []event.AppEventKind{event.EventPermissionAsked, event.EventQuestionAsked}) {
		t.Fatalf("presented events = %#v, want permission/question", presenter.events)
	}
	if renderer.flushCount != 3 {
		t.Fatalf("renderer flush count = %d, want 3", renderer.flushCount)
	}
	if indexOf(trace, "flush:1") == -1 || indexOf(trace, "flush:1") > indexOf(trace, "interaction:permission.asked") {
		t.Fatalf("trace = %#v, want flush before permission handling", trace)
	}
	if indexOf(trace, "flush:2") == -1 || indexOf(trace, "flush:2") > indexOf(trace, "interaction:question.asked") {
		t.Fatalf("trace = %#v, want flush before question handling", trace)
	}
}

func TestAskRunner_Run_Cancelled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	renderer := &fakeTextRenderer{}
	runner := mustRunner(t, Options{
		Transport: &fakeTransport{sendHook: cancel},
		Events: &fakeRouter{
			waitForCancel: true,
		},
		Sessions: &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
		Renderer: renderer,
	})

	err := runner.Run(ctx, AskRequest{Prompt: "hello", CWD: "/work"})
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("Run() error = %v, want context.Canceled", err)
	}
	if renderer.flushCount != 1 {
		t.Fatalf("renderer flush count = %d, want 1 on cancel", renderer.flushCount)
	}
}

func TestAskRunner_Run_InvalidModelFormatReturnsUserError(t *testing.T) {
	transportClient := &fakeTransport{}
	runner := mustRunner(t, Options{
		Transport: transportClient,
		Events:    &fakeRouter{},
		Sessions:  &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work", Model: "gpt-5"})
	var userErr *presenter.UserError
	if !errors.As(err, &userErr) {
		t.Fatalf("Run() error = %v, want presenter.UserError", err)
	}
	if transportClient.sendCalls != 0 {
		t.Fatalf("SendPromptAsync calls = %d, want 0", transportClient.sendCalls)
	}
}

func TestAskRunner_Run_ServerUnavailableIncludesURLAndHint(t *testing.T) {
	runner := mustRunner(t, Options{
		Transport: &fakeTransport{},
		Events:    &fakeRouter{},
		Sessions: &fakeSessions{resolveErr: &url.Error{
			Op:  "Get",
			URL: "http://127.0.0.1:4096/session",
			Err: errors.New("connection refused"),
		}},
		ServerURL: "http://127.0.0.1:4096",
	})

	err := runner.Run(context.Background(), AskRequest{Prompt: "hello", CWD: "/work"})
	if err == nil {
		t.Fatal("Run() error = nil, want server error")
	}
	message := err.Error()
	if !strings.Contains(message, "http://127.0.0.1:4096") {
		t.Fatalf("error = %q, want server URL", message)
	}
	if !strings.Contains(message, "ensure `opencode serve --port 4096` is running and reachable") {
		t.Fatalf("error = %q, want troubleshooting hint", message)
	}
}

func mustRunner(t *testing.T, opts Options) Runner {
	t.Helper()
	runner, err := NewAskRunner(opts)
	if err != nil {
		t.Fatalf("NewAskRunner() error = %v", err)
	}
	return runner
}

func indexOf(values []string, target string) int {
	for index, value := range values {
		if value == target {
			return index
		}
	}
	return -1
}

type fakeSessions struct {
	resolved        session.Context
	continued       session.Context
	resolveErr      error
	continueErr     error
	resolveCalls    int
	continueCalls   int
	resolveCWD      string
	resolveForceNew bool
	continueID      string
}

func (f *fakeSessions) Resolve(_ context.Context, cwd string, forceNew bool) (session.Context, error) {
	f.resolveCalls++
	f.resolveCWD = cwd
	f.resolveForceNew = forceNew
	if f.resolveErr != nil {
		return session.Context{}, f.resolveErr
	}
	return f.resolved, nil
}

func (f *fakeSessions) Continue(_ context.Context, id string) (session.Context, error) {
	f.continueCalls++
	f.continueID = id
	if f.continueErr != nil {
		return session.Context{}, f.continueErr
	}
	return f.continued, nil
}

type fakeTransport struct {
	sentSessionID             string
	promptReq                 transport.PromptRequest
	sendErr                   error
	sendHook                  func()
	sendCalls                 int
	providerDefaults          transport.ProviderDefaults
	providerDefaultsErr       error
	providerDefaultsCalls     int
	providerDefaultsDirectory string
}

func (f *fakeTransport) ProviderDefaults(_ context.Context, directory, _ string) (transport.ProviderDefaults, error) {
	f.providerDefaultsCalls++
	f.providerDefaultsDirectory = directory
	if f.providerDefaultsErr != nil {
		return transport.ProviderDefaults{}, f.providerDefaultsErr
	}
	return f.providerDefaults, nil
}

func (f *fakeTransport) SendPromptAsync(_ context.Context, sessionID string, req transport.PromptRequest) error {
	f.sendCalls++
	f.sentSessionID = sessionID
	f.promptReq = req
	if f.sendHook != nil {
		f.sendHook()
	}
	return f.sendErr
}

type fakeRouter struct {
	events          []event.AppEvent
	err             error
	waitForCancel   bool
	targetSessionID string
	filter          transport.EventFilter
}

func (f *fakeRouter) Subscribe(ctx context.Context, targetSessionID string, filter transport.EventFilter) (<-chan event.AppEvent, <-chan error) {
	f.targetSessionID = targetSessionID
	f.filter = filter
	events := make(chan event.AppEvent, len(f.events))
	errs := make(chan error, 1)
	go func() {
		defer close(events)
		defer close(errs)
		if f.waitForCancel {
			<-ctx.Done()
			return
		}
		for _, evt := range f.events {
			select {
			case <-ctx.Done():
				return
			case events <- evt:
			}
		}
		if f.err != nil {
			select {
			case <-ctx.Done():
				return
			case errs <- f.err:
			}
		}
	}()
	return events, errs
}

type fakeTextRenderer struct {
	deltas     []string
	flushCount int
	trace      *[]string
}

func (f *fakeTextRenderer) WriteDelta(_ context.Context, delta string) error {
	f.deltas = append(f.deltas, delta)
	if f.trace != nil {
		*f.trace = append(*f.trace, "render:"+delta)
	}
	return nil
}

func (f *fakeTextRenderer) Flush(context.Context) error {
	f.flushCount++
	if f.trace != nil {
		*f.trace = append(*f.trace, fmt.Sprintf("flush:%d", f.flushCount))
	}
	return nil
}

type fakePresenter struct {
	events []event.AppEventKind
}

func (f *fakePresenter) PresentEvent(_ context.Context, evt event.AppEvent) error {
	f.events = append(f.events, evt.Kind)
	return nil
}

type fakePermissionManager struct {
	events []event.AppEventKind
	trace  *[]string
	err    error
}

func (f *fakePermissionManager) HandleEvent(_ context.Context, evt event.AppEvent) error {
	f.events = append(f.events, evt.Kind)
	if f.trace != nil {
		*f.trace = append(*f.trace, "interaction:"+string(evt.Kind))
	}
	return f.err
}
