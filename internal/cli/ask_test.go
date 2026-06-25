package cli

import (
	"bytes"
	"context"
	"io"
	"log/slog"
	"os"
	"strings"
	"testing"

	"atomgit.com/openeuler/euler-copilot-shell/internal/app"
	"atomgit.com/openeuler/euler-copilot-shell/internal/config"
	"atomgit.com/openeuler/euler-copilot-shell/internal/core"
	"atomgit.com/openeuler/euler-copilot-shell/internal/event"
	"atomgit.com/openeuler/euler-copilot-shell/internal/permission"
	"atomgit.com/openeuler/euler-copilot-shell/internal/presenter"
	"atomgit.com/openeuler/euler-copilot-shell/internal/renderer"
	"atomgit.com/openeuler/euler-copilot-shell/internal/server"
	"atomgit.com/openeuler/euler-copilot-shell/internal/session"
	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
	"github.com/spf13/cobra"
)

func TestAskCommand_UsesArgumentPromptAndFlags(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{}
	opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
	opts.loadAppFn = func(context.Context, *cobra.Command) (app.Container, error) {
		fake.cfg = config.Config{DefaultAgent: opts.agent, DefaultModel: opts.model, DefaultVariant: opts.variant}
		return fake, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"--agent", "build", "--model", "opencode/gpt-5.1-codex", "--variant", "reasoning-high", "ask", "--session", "ses_123", "hello", "world"})

	err := cmd.ExecuteContext(context.Background())
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if fake.askReq.Prompt != "hello world" {
		t.Fatalf("prompt = %q, want joined args", fake.askReq.Prompt)
	}
	if fake.askReq.SessionID != "ses_123" {
		t.Fatalf("session id = %q, want ses_123", fake.askReq.SessionID)
	}
	if fake.askReq.Agent != "build" {
		t.Fatalf("agent = %q, want build", fake.askReq.Agent)
	}
	if fake.askReq.Model != "opencode/gpt-5.1-codex" {
		t.Fatalf("model = %q, want provider/model", fake.askReq.Model)
	}
	if fake.askReq.Variant != "reasoning-high" {
		t.Fatalf("variant = %q, want reasoning-high", fake.askReq.Variant)
	}
	if fake.askReq.Mode != core.ModeAsk {
		t.Fatalf("mode = %q, want %q", fake.askReq.Mode, core.ModeAsk)
	}
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("Getwd() error = %v", err)
	}
	if fake.askReq.CWD != cwd {
		t.Fatalf("cwd = %q, want %q", fake.askReq.CWD, cwd)
	}
}

func TestAskCommand_ReadsPromptFromStdin(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{cfg: config.Config{DefaultAgent: "default", DefaultModel: "opencode/default-model", DefaultVariant: "default-variant"}}
	opts := &rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetIn(strings.NewReader("explain this function\n"))
	cmd.SetArgs([]string{"ask", "--new"})

	err := cmd.ExecuteContext(context.Background())
	if err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if fake.askReq.Prompt != "explain this function" {
		t.Fatalf("prompt = %q, want stdin text", fake.askReq.Prompt)
	}
	if !fake.askReq.ForceNew {
		t.Fatal("ForceNew = false, want true")
	}
}

func TestAskCommand_RejectsMissingPrompt(t *testing.T) {
	var out, errOut bytes.Buffer
	cmd := newRootCommandWithOptions(&rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut})
	cmd.SetIn(strings.NewReader("   "))
	cmd.SetArgs([]string{"ask"})

	err := cmd.ExecuteContext(context.Background())
	if err == nil {
		t.Fatal("Execute() error = nil, want prompt error")
	}
	if !strings.Contains(err.Error(), "prompt is required") {
		t.Fatalf("error = %q, want prompt guidance", err.Error())
	}
}

func TestAskCommand_RejectsNewAndSessionTogether(t *testing.T) {
	var out, errOut bytes.Buffer
	cmd := newRootCommandWithOptions(&rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut})
	cmd.SetArgs([]string{"ask", "--new", "--session", "ses_1", "hello"})

	err := cmd.ExecuteContext(context.Background())
	if err == nil {
		t.Fatal("Execute() error = nil, want flag conflict")
	}
	if !strings.Contains(err.Error(), "--new and --session cannot be used together") {
		t.Fatalf("error = %q, want flag conflict message", err.Error())
	}
}

type fakeContainer struct {
	cfg                  config.Config
	askReq               core.AskRequest
	askErr               error
	providers            []app.ProviderStatus
	listProvidersErr     error
	connectProvider      app.ProviderStatus
	connectProviderErr   error
	connectProviderInput string
	connectProviderKey   string
	sessions             []session.Summary
	listSessionsErr      error
	continuedSession     session.Context
	continueSessionID    string
	continueSessionErr   error
	configWriter         config.Writer
	serverMgr            server.Manager
}

func (f *fakeContainer) Config() config.Config           { return f.cfg }
func (f *fakeContainer) Logger() *slog.Logger            { return slog.New(slog.NewTextHandler(io.Discard, nil)) }
func (f *fakeContainer) Transport() transport.Client     { return nil }
func (f *fakeContainer) Events() event.Router            { return nil }
func (f *fakeContainer) Sessions() session.Resolver      { return nil }
func (f *fakeContainer) Renderer() renderer.TextRenderer { return nil }
func (f *fakeContainer) Presenter() presenter.Presenter  { return nil }
func (f *fakeContainer) Permission() permission.Manager  { return nil }
func (f *fakeContainer) Version() version.Info           { return version.New("dev", "none", "unknown") }
func (f *fakeContainer) WriteConfig(context.Context) config.Writer {
	if f.configWriter != nil {
		return f.configWriter
	}
	return &fakeConfigWriter{}
}
func (f *fakeContainer) Ask(_ context.Context, req core.AskRequest) error {
	f.askReq = req
	return f.askErr
}
func (f *fakeContainer) InitBash(context.Context) (string, error) { return "", nil }
func (f *fakeContainer) ListSessions(context.Context) ([]session.Summary, error) {
	return f.sessions, f.listSessionsErr
}
func (f *fakeContainer) ListProviders(context.Context) ([]app.ProviderStatus, error) {
	return f.providers, f.listProvidersErr
}
func (f *fakeContainer) ConnectProviderWithAPIKey(_ context.Context, input, apiKey string) (app.ProviderStatus, error) {
	f.connectProviderInput = input
	f.connectProviderKey = apiKey
	return f.connectProvider, f.connectProviderErr
}
func (f *fakeContainer) ContinueSession(_ context.Context, id string) (session.Context, error) {
	f.continueSessionID = id
	return f.continuedSession, f.continueSessionErr
}
func (f *fakeContainer) Doctor(context.Context) (string, error) { return "", nil }
func (f *fakeContainer) StartREPL(context.Context) error        { return nil }
func (f *fakeContainer) ServerManager() server.Manager          { return f.serverMgr }
func (f *fakeContainer) Close()                                 {}

type fakeConfigWriter struct{}

func (f *fakeConfigWriter) SetDefaultAgent(agent string) error { return nil }
func (f *fakeConfigWriter) SetDefaultModel(model string) error { return nil }
func (f *fakeConfigWriter) SetDefaultVariant(v string) error   { return nil }
func (f *fakeConfigWriter) ConfigPath() string                 { return "/fake/config.toml" }
