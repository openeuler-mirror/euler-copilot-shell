package app

import (
	"bytes"
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"atomgit.com/openeuler/euler-copilot-shell/internal/config"
	"atomgit.com/openeuler/euler-copilot-shell/internal/core"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
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

func TestInitBash_RendersTemplate(t *testing.T) {
	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{Config: config.LoadOptions{ConfigFiles: []string{}}, Stdout: &stdout, Version: version.New("1.2.3", "abc", "today")})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	script, err := container.InitBash(context.Background())
	if err != nil {
		t.Fatalf("InitBash() error = %v", err)
	}
	for _, want := range []string{"Witty Bash integration 1.2.3", "__witty_classify()", "__witty_shell_dispatch()"} {
		if !strings.Contains(script, want) {
			t.Fatalf("InitBash() = %q, want %q", script, want)
		}
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
			DefaultAgent:   "build",
			DefaultModel:   "opencode/gpt-5.1-codex",
			DefaultVariant: "reasoning-high",
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
	if runner.req.Variant != "reasoning-high" {
		t.Fatalf("variant = %q, want config default", runner.req.Variant)
	}
	if runner.req.Mode != core.ModeAsk {
		t.Fatalf("mode = %q, want %q", runner.req.Mode, core.ModeAsk)
	}
}

func TestAsk_PreservesExplicitAgentAndModel(t *testing.T) {
	runner := &fakeAskRunner{}
	app := &App{
		cfg: config.Config{
			DefaultAgent:   "default",
			DefaultModel:   "opencode/default-model",
			DefaultVariant: "default-variant",
		},
		ask: runner,
	}

	err := app.Ask(context.Background(), core.AskRequest{
		Prompt:  "hello",
		Agent:   "custom-agent",
		Model:   "custom/provider-model",
		Variant: "custom-variant",
		Mode:    core.ModeAsk,
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
	if runner.req.Variant != "custom-variant" {
		t.Fatalf("variant = %q, want explicit override", runner.req.Variant)
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

func TestDoctor_PinpointsConnectionFailure(t *testing.T) {
	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides:   config.Overrides{ServerURL: "http://127.0.0.1:59999"},
		},
		Stdout: &stdout,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	report, err := container.Doctor(context.Background())
	if err != nil {
		t.Fatalf("Doctor() error = %v", err)
	}
	if !hasFailStatus(report) {
		t.Errorf("report should contain FAIL status; report:\n%s", report)
	}
	if !strings.Contains(report, "server reachable") {
		t.Errorf("report does not mention server reachable; report:\n%s", report)
	}
	if !strings.Contains(report, "connection refused") {
		t.Errorf("report does not pinpoint connection failure; report:\n%s", report)
	}
	if !strings.Contains(report, "SKIP") {
		t.Errorf("report should contain SKIP for endpoint checks; report:\n%s", report)
	}
}

func TestDoctor_HealthyServer_AllChecksPass(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/global/health":
			_, _ = w.Write([]byte(`{"healthy":true,"version":"1.0.0"}`))
		case "/doc", "/event":
			w.WriteHeader(http.StatusOK)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer server.Close()

	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides:   config.Overrides{ServerURL: server.URL},
		},
		Stdout: &stdout,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	report, err := container.Doctor(context.Background())
	if err != nil {
		t.Fatalf("Doctor() error = %v", err)
	}
	if hasFailStatus(report) {
		t.Errorf("report should not contain FAIL status for healthy server; report:\n%s", report)
	}
	if !strings.Contains(report, "server reachable") {
		t.Errorf("report should mention server reachable; report:\n%s", report)
	}
	if !strings.Contains(report, "/doc endpoint") {
		t.Errorf("report should mention /doc endpoint; report:\n%s", report)
	}
	if !strings.Contains(report, "/event endpoint") {
		t.Errorf("report should mention /event endpoint; report:\n%s", report)
	}
}

func TestDoctor_NonInteractiveDoesNotReportShellIntegration(t *testing.T) {
	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
		},
		Stdout: &stdout,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	report, err := container.Doctor(context.Background())
	if err != nil {
		t.Fatalf("Doctor() error = %v", err)
	}
	// In non-interactive (test) environment, shell integration should be SKIP
	if !strings.Contains(report, "shell integration") {
		t.Errorf("report should mention shell integration; report:\n%s", report)
	}
	shellLine := extractLineContaining(report, "shell integration")
	if !strings.Contains(shellLine, "SKIP") {
		t.Errorf("shell integration should be SKIP in non-interactive env; got: %s", shellLine)
	}
}

func TestDoctor_DoesNotLeakSensitiveData(t *testing.T) {
	var stdout bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides:   config.Overrides{ServerURL: "http://127.0.0.1:59999"},
		},
		Stdout: &stdout,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	report, err := container.Doctor(context.Background())
	if err != nil {
		t.Fatalf("Doctor() error = %v", err)
	}
	// Verify no token/key/auth headers are leaked
	for _, sensitive := range []string{"Authorization", "Bearer", "api_key", "apiKey", "token"} {
		if strings.Contains(strings.ToLower(report), strings.ToLower(sensitive)) {
			t.Errorf("report may leak sensitive data (%q); report:\n%s", sensitive, report)
		}
	}
}

func extractLineContaining(s, substr string) string {
	for _, line := range strings.Split(s, "\n") {
		if strings.Contains(line, substr) {
			return line
		}
	}
	return ""
}

// hasFailStatus returns true if the report contains a check with FAIL status
// (not just the Summary line which always mentions "FAIL" as a label).
func hasFailStatus(report string) bool {
	for _, line := range strings.Split(report, "\n") {
		if strings.Contains(line, "[FAIL]") {
			return true
		}
	}
	return false
}
