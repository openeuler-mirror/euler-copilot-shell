package app

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/event"
	permissionpkg "atomgit.com/openeuler/witty-cli/internal/permission"
	presenterpkg "atomgit.com/openeuler/witty-cli/internal/presenter"
	"atomgit.com/openeuler/witty-cli/internal/renderer"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/transport"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

func TestNew_LoadsConfigAndVersion(t *testing.T) {
	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{
		Config:  config.LoadOptions{ConfigFiles: []string{}},
		Version: version.New("1.0.0", "abc", "today"),
		Stdout:  &stdout,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	if container.Config().ServerURL != config.DefaultServerURL {
		t.Fatalf("ServerURL = %q, want default", container.Config().ServerURL)
	}
	if container.Version().Version != "1.0.0" {
		t.Fatalf("Version = %q, want 1.0.0", container.Version().Version)
	}
	if container.Transport() == nil {
		t.Fatal("Transport() = nil, want wired transport client")
	}
	if container.Events() == nil {
		t.Fatal("Events() = nil, want wired event router")
	}
	if container.Sessions() == nil {
		t.Fatal("Sessions() = nil, want wired session resolver")
	}
	if container.Renderer() == nil {
		t.Fatal("Renderer() = nil, want wired text renderer")
	}
	if container.Presenter() == nil {
		t.Fatal("Presenter() = nil, want wired presenter")
	}
	if container.Permission() == nil {
		t.Fatal("Permission() = nil, want wired permission manager")
	}
}

func TestInitBash_ReturnsPlaceholder(t *testing.T) {
	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{Config: config.LoadOptions{ConfigFiles: []string{}}, Stdout: &stdout})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	script, err := container.InitBash(context.Background())
	if err != nil {
		t.Fatalf("InitBash() error = %v", err)
	}
	if !strings.Contains(script, "Witty Bash integration placeholder") {
		t.Fatalf("InitBash() = %q, want placeholder", script)
	}
}

func TestSessionServices_UseWiredTransport(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/session":
			if r.Method != http.MethodGet {
				t.Fatalf("list method = %s, want GET", r.Method)
			}
			_, _ = w.Write([]byte(`[{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work","title":"One","version":"dev","time":{"created":0,"updated":0}}]`))
		case "/session/ses_1":
			if r.Method != http.MethodGet {
				t.Fatalf("get method = %s, want GET", r.Method)
			}
			_, _ = w.Write([]byte(`{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work","title":"One","version":"dev","time":{"created":0,"updated":0}}`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides:   config.Overrides{ServerURL: server.URL},
		},
		Stdout:           &stdout,
		SessionStatePath: filepath.Join(t.TempDir(), "state.json"),
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	summaries, err := container.ListSessions(context.Background())
	if err != nil {
		t.Fatalf("ListSessions() error = %v", err)
	}
	if len(summaries) != 1 || summaries[0].ID != "ses_1" {
		t.Fatalf("ListSessions() = %+v, want ses_1", summaries)
	}
	ctx, err := container.ContinueSession(context.Background(), "ses_1")
	if err != nil {
		t.Fatalf("ContinueSession() error = %v", err)
	}
	if ctx.ID != "ses_1" {
		t.Fatalf("ContinueSession() ID = %q, want ses_1", ctx.ID)
	}
}

func TestAsk_RejectsEmptyPrompt(t *testing.T) {
	app := &App{}
	var userErr *presenterpkg.UserError
	if err := app.Ask(context.Background(), "   "); !errors.As(err, &userErr) {
		t.Fatalf("Ask(empty) error = %v, want presenter.UserError", err)
	}
}

func TestAsk_DispatchesRendererAndPresenter(t *testing.T) {
	renderer := &fakeTextRenderer{}
	presenter := &fakePresenter{}
	transportClient := &fakeTransport{}
	app := &App{
		cfg:       config.Default(),
		transport: transportClient,
		events: &fakeRouter{events: []event.AppEvent{
			{Kind: event.EventStepStarted},
			{Kind: event.EventTextDelta, Payload: event.TextDeltaPayload{Delta: "hello\n\n"}},
			{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "bash", CallID: "call_1", Input: json.RawMessage(`{"cmd":"ls"}`)}},
			{Kind: event.EventSessionIdle},
		}},
		sessions:  &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
		renderer:  renderer,
		presenter: presenter,
	}

	if err := app.Ask(context.Background(), "hello"); err != nil {
		t.Fatalf("Ask() error = %v", err)
	}
	if transportClient.sentSessionID != "ses_1" {
		t.Fatalf("SendPromptAsync session = %q, want ses_1", transportClient.sentSessionID)
	}
	if got := transportClient.promptReq.Parts; len(got) != 1 || got[0].Text != "hello" || got[0].Type != "text" {
		t.Fatalf("prompt parts = %+v", got)
	}
	if !reflect.DeepEqual(renderer.deltas, []string{"hello\n\n"}) {
		t.Fatalf("renderer deltas = %#v", renderer.deltas)
	}
	if renderer.flushCount != 1 {
		t.Fatalf("renderer flush count = %d, want 1", renderer.flushCount)
	}
	if !reflect.DeepEqual(presenter.events, []event.AppEventKind{event.EventStepStarted, event.EventToolCalled}) {
		t.Fatalf("presented events = %#v", presenter.events)
	}
}

func TestAsk_DelegatesInteractionEventsToPermissionManager(t *testing.T) {
	trace := []string{}
	renderer := &fakeTextRenderer{trace: &trace}
	presenter := &fakePresenter{}
	permission := &fakePermissionManager{trace: &trace}
	app := &App{
		cfg:       config.Default(),
		transport: &fakeTransport{},
		events: &fakeRouter{events: []event.AppEvent{
			{Kind: event.EventTextDelta, Payload: event.TextDeltaPayload{Delta: "hello"}},
			{Kind: event.EventPermissionAsked, Payload: event.PermissionAskedPayload{RequestID: "per_1", Permission: "tool"}},
			{Kind: event.EventQuestionAsked, Payload: event.QuestionAskedPayload{RequestID: "que_1", Questions: []event.QuestionInfo{{Question: "Continue?"}}}},
			{Kind: event.EventSessionIdle},
		}},
		sessions:   &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
		renderer:   renderer,
		presenter:  presenter,
		permission: permission,
	}

	if err := app.Ask(context.Background(), "hello"); err != nil {
		t.Fatalf("Ask() error = %v", err)
	}
	if !reflect.DeepEqual(permission.events, []event.AppEventKind{event.EventPermissionAsked, event.EventQuestionAsked}) {
		t.Fatalf("interaction events = %#v, want permission/question", permission.events)
	}
	if !reflect.DeepEqual(presenter.events, []event.AppEventKind{event.EventPermissionAsked, event.EventQuestionAsked}) {
		t.Fatalf("presented interaction events = %#v, want permission/question", presenter.events)
	}
	if renderer.flushCount != 3 {
		t.Fatalf("renderer flush count = %d, want 3", renderer.flushCount)
	}
	if indexOf(trace, "flush:1") == -1 || indexOf(trace, "flush:1") > indexOf(trace, "interaction:permission.asked") {
		t.Fatalf("trace = %#v, want first flush before permission handling", trace)
	}
	if indexOf(trace, "flush:2") == -1 || indexOf(trace, "flush:2") > indexOf(trace, "interaction:question.asked") {
		t.Fatalf("trace = %#v, want second flush before question handling", trace)
	}
}

func TestAsk_EOFBeforeIdleFlushesAndReturnsError(t *testing.T) {
	renderer := &fakeTextRenderer{}
	app := &App{
		cfg:       config.Default(),
		transport: &fakeTransport{},
		events: &fakeRouter{events: []event.AppEvent{
			{Kind: event.EventTextDelta, Payload: event.TextDeltaPayload{Delta: "tail"}},
		}},
		sessions: &fakeSessions{resolved: session.Context{ID: "ses_1", Directory: "/work"}},
		renderer: renderer,
	}

	err := app.Ask(context.Background(), "hello")
	if !errors.Is(err, ErrStreamEndedWithoutIdle) {
		t.Fatalf("Ask() error = %v, want ErrStreamEndedWithoutIdle", err)
	}
	if renderer.flushCount != 1 {
		t.Fatalf("renderer flush count = %d, want 1", renderer.flushCount)
	}
}

func TestLogger_DebugWritesToNonTTYStderr(t *testing.T) {
	debug := true
	var stderr bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides: config.Overrides{
				Debug: &debug,
			},
		},
		Stdout: &bytes.Buffer{},
		Stderr: &stderr,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	container.Logger().Debug("debug message")
	if !strings.Contains(stderr.String(), "debug message") {
		t.Fatalf("debug log = %q, want debug message", stderr.String())
	}
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
	resolved session.Context
}

func (f *fakeSessions) Resolve(context.Context, string, bool) (session.Context, error) {
	return f.resolved, nil
}

func (f *fakeSessions) Continue(context.Context, string) (session.Context, error) {
	return session.Context{}, nil
}

func (f *fakeSessions) List(context.Context, session.Scope) ([]session.Summary, error) {
	return nil, nil
}

type fakeTransport struct {
	sentSessionID string
	promptReq     transport.PromptRequest
}

func (f *fakeTransport) Health(context.Context) (transport.Health, error) {
	return transport.Health{}, nil
}

func (f *fakeTransport) CreateSession(context.Context, transport.CreateSessionRequest) (transport.Session, error) {
	return transport.Session{}, nil
}

func (f *fakeTransport) GetSession(context.Context, string) (transport.Session, error) {
	return transport.Session{}, nil
}

func (f *fakeTransport) ListSessions(context.Context, transport.SessionFilter) ([]transport.Session, error) {
	return nil, nil
}

func (f *fakeTransport) SendPromptAsync(_ context.Context, sessionID string, req transport.PromptRequest) error {
	f.sentSessionID = sessionID
	f.promptReq = req
	return nil
}

func (f *fakeTransport) ReplyPermission(context.Context, string, transport.PermissionDecision) (bool, error) {
	return false, nil
}

func (f *fakeTransport) ReplyQuestion(context.Context, string, [][]string) (bool, error) {
	return false, nil
}

func (f *fakeTransport) RejectQuestion(context.Context, string) (bool, error) {
	return false, nil
}

func (f *fakeTransport) SubscribeEvents(context.Context, transport.EventFilter) (<-chan transport.RawEvent, <-chan error) {
	return nil, nil
}

type fakeRouter struct {
	events []event.AppEvent
	err    error
}

func (f *fakeRouter) Normalize(transport.RawEvent) (event.AppEvent, bool) {
	return event.AppEvent{}, false
}

func (f *fakeRouter) Subscribe(context.Context, string, transport.EventFilter) (<-chan event.AppEvent, <-chan error) {
	events := make(chan event.AppEvent, len(f.events))
	errs := make(chan error, 1)
	for _, evt := range f.events {
		events <- evt
	}
	close(events)
	if f.err != nil {
		errs <- f.err
	}
	close(errs)
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

func (f *fakePresenter) PresentStepStarted(context.Context) error { return nil }
func (f *fakePresenter) PresentStepEnded(context.Context, event.StepEndedPayload) error {
	return nil
}
func (f *fakePresenter) PresentToolCalled(context.Context, event.ToolCalledPayload) error { return nil }
func (f *fakePresenter) PresentToolSucceeded(context.Context, event.ToolResultPayload) error {
	return nil
}
func (f *fakePresenter) PresentToolFailed(context.Context, event.ToolResultPayload) error { return nil }
func (f *fakePresenter) PresentPermission(context.Context, event.PermissionAskedPayload) error {
	return nil
}
func (f *fakePresenter) PresentQuestion(context.Context, event.QuestionAskedPayload) error {
	return nil
}
func (f *fakePresenter) PresentError(context.Context, error) error { return nil }

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

func (f *fakePermissionManager) HandlePermission(context.Context, event.PermissionAskedPayload) error {
	return f.err
}

func (f *fakePermissionManager) HandleQuestion(context.Context, event.QuestionAskedPayload) error {
	return f.err
}

var _ renderer.TextRenderer = (*fakeTextRenderer)(nil)
var _ presenterpkg.Presenter = (*fakePresenter)(nil)
var _ permissionpkg.Manager = (*fakePermissionManager)(nil)
