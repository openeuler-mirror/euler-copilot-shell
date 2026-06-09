package app

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
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

func TestAsk_DelegatesToRunnerWithConfigDefaults(t *testing.T) {
	runner := &fakeAskRunner{}
	app := &App{
		cfg: config.Config{
			DefaultAgent: "build",
			DefaultModel: "opencode/gpt-5.1-codex",
		},
		ask: runner,
	}

	err := app.Ask(context.Background(), core.AskRequest{Prompt: "hello", CWD: "/work"})
	if err != nil {
		t.Fatalf("Ask() error = %v", err)
	}
	if runner.req.Prompt != "hello" || runner.req.CWD != "/work" {
		t.Fatalf("request = %+v", runner.req)
	}
	if runner.req.Agent != "build" {
		t.Fatalf("agent = %q, want build", runner.req.Agent)
	}
	if runner.req.Model != "opencode/gpt-5.1-codex" {
		t.Fatalf("model = %q, want config default", runner.req.Model)
	}
	if runner.req.Mode != core.ModeAsk {
		t.Fatalf("mode = %q, want %q", runner.req.Mode, core.ModeAsk)
	}
}

func TestAsk_PreservesExplicitAgentAndModel(t *testing.T) {
	runner := &fakeAskRunner{}
	app := &App{
		cfg: config.Config{
			DefaultAgent: "default",
			DefaultModel: "opencode/default-model",
		},
		ask: runner,
	}

	err := app.Ask(context.Background(), core.AskRequest{
		Prompt: "hello",
		Agent:  "custom-agent",
		Model:  "custom/provider-model",
		Mode:   core.ModeAsk,
	})
	if err != nil {
		t.Fatalf("Ask() error = %v", err)
	}
	if runner.req.Agent != "custom-agent" {
		t.Fatalf("agent = %q, want explicit override", runner.req.Agent)
	}
	if runner.req.Model != "custom/provider-model" {
		t.Fatalf("model = %q, want explicit override", runner.req.Model)
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

type fakeAskRunner struct {
	req core.AskRequest
	err error
}

func (f *fakeAskRunner) Run(_ context.Context, req core.AskRequest) error {
	f.req = req
	return f.err
}
