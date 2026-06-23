package session

import (
	"context"
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
)

func TestResolve_UsesPinnedSession(t *testing.T) {
	statePath := filepath.Join(t.TempDir(), "state.json")
	store := newStateStore(statePath)
	if err := store.save(state{CurrentByDirectory: map[string]string{"/work": "ses_pinned"}}); err != nil {
		t.Fatalf("save state: %v", err)
	}
	fake := &fakeTransport{sessionsByID: map[string]transport.Session{
		"ses_pinned": testSession("ses_pinned", "/work"),
	}}
	resolver := mustResolver(t, fake, statePath)

	ctx, err := resolver.Resolve(context.Background(), "/work", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if ctx.ID != "ses_pinned" {
		t.Fatalf("Resolve() ID = %q, want ses_pinned", ctx.ID)
	}
	if fake.getCalls != 1 || fake.listCalls != 0 || fake.createCalls != 0 {
		t.Fatalf("calls get/list/create = %d/%d/%d", fake.getCalls, fake.listCalls, fake.createCalls)
	}
}

func TestResolve_ListsCurrentDirectoryBeforeCreate(t *testing.T) {
	statePath := filepath.Join(t.TempDir(), "state.json")
	fake := &fakeTransport{listSessions: []transport.Session{testSession("ses_existing", "/work")}}
	resolver := mustResolver(t, fake, statePath)

	ctx, err := resolver.Resolve(context.Background(), "/work", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if ctx.ID != "ses_existing" {
		t.Fatalf("Resolve() ID = %q, want existing", ctx.ID)
	}
	if fake.lastListFilter.Directory != "/work" {
		t.Fatalf("list filter = %+v, want /work", fake.lastListFilter)
	}
	assertPinned(t, statePath, "/work", "ses_existing")
}

func TestResolve_ForceNewCreatesSession(t *testing.T) {
	statePath := filepath.Join(t.TempDir(), "state.json")
	fake := &fakeTransport{created: testSession("ses_new", "/work")}
	resolver := mustResolver(t, fake, statePath)

	ctx, err := resolver.Resolve(context.Background(), "/work", true)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if ctx.ID != "ses_new" {
		t.Fatalf("Resolve() ID = %q, want new", ctx.ID)
	}
	if fake.createCalls != 1 || fake.lastCreate.Directory != "/work" {
		t.Fatalf("create calls=%d req=%+v", fake.createCalls, fake.lastCreate)
	}
	assertPinned(t, statePath, "/work", "ses_new")
}

func TestResolve_CreatesWhenNoExistingSession(t *testing.T) {
	statePath := filepath.Join(t.TempDir(), "state.json")
	fake := &fakeTransport{created: testSession("ses_new", "/work")}
	resolver := mustResolver(t, fake, statePath)

	ctx, err := resolver.Resolve(context.Background(), "/work", false)
	if err != nil {
		t.Fatalf("Resolve() error = %v", err)
	}
	if ctx.ID != "ses_new" {
		t.Fatalf("Resolve() ID = %q, want new", ctx.ID)
	}
	if fake.listCalls != 1 || fake.createCalls != 1 {
		t.Fatalf("list/create calls = %d/%d, want 1/1", fake.listCalls, fake.createCalls)
	}
}

func TestContinue_GetsSessionAndPinsDirectory(t *testing.T) {
	statePath := filepath.Join(t.TempDir(), "state.json")
	fake := &fakeTransport{sessionsByID: map[string]transport.Session{
		"ses_1": testSession("ses_1", "/work"),
	}}
	resolver := mustResolver(t, fake, statePath)

	ctx, err := resolver.Continue(context.Background(), "ses_1")
	if err != nil {
		t.Fatalf("Continue() error = %v", err)
	}
	if ctx.ID != "ses_1" {
		t.Fatalf("Continue() ID = %q, want ses_1", ctx.ID)
	}
	assertPinned(t, statePath, "/work", "ses_1")
}

func TestContinue_NotFoundHasClearError(t *testing.T) {
	fake := &fakeTransport{getErr: errors.New("not found")}
	resolver := mustResolver(t, fake, filepath.Join(t.TempDir(), "state.json"))

	_, err := resolver.Continue(context.Background(), "ses_missing")
	if err == nil {
		t.Fatal("Continue() error = nil, want error")
	}
	if !strings.Contains(err.Error(), "continue session \"ses_missing\"") || !strings.Contains(err.Error(), "not found") {
		t.Fatalf("Continue() error = %q, want session id context", err.Error())
	}
}

func TestList_ReturnsSummaries(t *testing.T) {
	agent := "build"
	fake := &fakeTransport{listSessions: []transport.Session{{ID: "ses_1", Title: "One", Directory: "/work", Agent: &agent}}}
	resolver := mustResolver(t, fake, filepath.Join(t.TempDir(), "state.json"))
	limit := 5.0

	summaries, err := resolver.List(context.Background(), Scope{Directory: "/work", Search: "one", Limit: &limit})
	if err != nil {
		t.Fatalf("List() error = %v", err)
	}
	if len(summaries) != 1 || summaries[0].ID != "ses_1" || summaries[0].Agent != "build" {
		t.Fatalf("summaries = %+v", summaries)
	}
	if fake.lastListFilter.Directory != "/work" || fake.lastListFilter.Search != "one" || fake.lastListFilter.Limit == nil || *fake.lastListFilter.Limit != 5 {
		t.Fatalf("list filter = %+v", fake.lastListFilter)
	}
}

func TestDefaultStatePath_UsesXDGStateHome(t *testing.T) {
	path, err := DefaultStatePath(mapLookup(map[string]string{"XDG_STATE_HOME": "/state"}), nil)
	if err != nil {
		t.Fatalf("DefaultStatePath() error = %v", err)
	}
	if path != filepath.Join("/state", "witty", "state.json") {
		t.Fatalf("DefaultStatePath() = %q", path)
	}
}

func TestDefaultStatePath_UsesHomeFallback(t *testing.T) {
	path, err := DefaultStatePath(mapLookup(nil), func() (string, error) { return "/home/user", nil })
	if err != nil {
		t.Fatalf("DefaultStatePath() error = %v", err)
	}
	if path != filepath.Join("/home/user", ".local", "state", "witty", "state.json") {
		t.Fatalf("DefaultStatePath() = %q", path)
	}
}

func mustResolver(t *testing.T, fake *fakeTransport, statePath string) Resolver {
	t.Helper()
	resolver, err := NewService(Options{Transport: fake, StatePath: statePath})
	if err != nil {
		t.Fatalf("NewService() error = %v", err)
	}
	return resolver
}

func assertPinned(t *testing.T, statePath, cwd, wantID string) {
	t.Helper()
	store := newStateStore(statePath)
	state, err := store.load()
	if err != nil {
		t.Fatalf("load state: %v", err)
	}
	if got := state.CurrentByDirectory[cwd]; got != wantID {
		t.Fatalf("pinned[%s] = %q, want %q", cwd, got, wantID)
	}
	info, err := os.Stat(statePath)
	if err != nil {
		t.Fatalf("stat state file: %v", err)
	}
	if info.Mode().Perm() != 0o600 {
		t.Fatalf("state file mode = %o, want 600", info.Mode().Perm())
	}
}

func testSession(id, directory string) transport.Session {
	return transport.Session{ID: id, Directory: directory, Title: id}
}

type fakeTransport struct {
	sessionsByID map[string]transport.Session
	listSessions []transport.Session
	created      transport.Session
	getErr       error
	listErr      error
	createErr    error

	getCalls       int
	listCalls      int
	createCalls    int
	lastGetID      string
	lastListFilter transport.SessionFilter
	lastCreate     transport.CreateSessionRequest
}

func (f *fakeTransport) CreateSession(_ context.Context, req transport.CreateSessionRequest) (transport.Session, error) {
	f.createCalls++
	f.lastCreate = req
	if f.createErr != nil {
		return transport.Session{}, f.createErr
	}
	if f.created.ID == "" {
		f.created = testSession("ses_created", req.Directory)
	}
	return f.created, nil
}

func (f *fakeTransport) GetSession(_ context.Context, sessionID string) (transport.Session, error) {
	f.getCalls++
	f.lastGetID = sessionID
	if f.getErr != nil {
		return transport.Session{}, f.getErr
	}
	if f.sessionsByID != nil {
		if session, ok := f.sessionsByID[sessionID]; ok {
			return session, nil
		}
	}
	return transport.Session{}, errors.New("not found")
}

func (f *fakeTransport) ListSessions(_ context.Context, filter transport.SessionFilter) ([]transport.Session, error) {
	f.listCalls++
	f.lastListFilter = filter
	if f.listErr != nil {
		return nil, f.listErr
	}
	return f.listSessions, nil
}

func mapLookup(values map[string]string) func(string) (string, bool) {
	return func(key string) (string, bool) {
		if values == nil {
			return "", false
		}
		value, ok := values[key]
		return value, ok
	}
}
