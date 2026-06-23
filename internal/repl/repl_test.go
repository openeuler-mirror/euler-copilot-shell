package repl

import (
	"context"
	"errors"
	"io"
	"strings"
	"sync/atomic"
	"testing"
	"time"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/terminal"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

type fakeRunner struct {
	runFn func(ctx context.Context, req core.AskRequest) error
	calls atomic.Int64
}

func (f *fakeRunner) Run(ctx context.Context, req core.AskRequest) error {
	f.calls.Add(1)
	if f.runFn != nil {
		return f.runFn(ctx, req)
	}
	return nil
}

func (f *fakeRunner) callCount() int64 {
	return f.calls.Load()
}

type fakeSessions struct {
	resolveFn  func(ctx context.Context, cwd string, forceNew bool) (session.Context, error)
	continueFn func(ctx context.Context, id string) (session.Context, error)
	listFn     func(ctx context.Context, scope session.Scope) ([]session.Summary, error)
}

func (f *fakeSessions) Resolve(ctx context.Context, cwd string, forceNew bool) (session.Context, error) {
	if f.resolveFn != nil {
		return f.resolveFn(ctx, cwd, forceNew)
	}
	return session.Context{ID: "ses_default"}, nil
}

func (f *fakeSessions) Continue(ctx context.Context, id string) (session.Context, error) {
	if f.continueFn != nil {
		return f.continueFn(ctx, id)
	}
	if id == "" {
		return session.Context{}, errors.New("session id is required")
	}
	return session.Context{ID: id, Directory: "/work", Title: id}, nil
}

func (f *fakeSessions) List(ctx context.Context, scope session.Scope) ([]session.Summary, error) {
	if f.listFn != nil {
		return f.listFn(ctx, scope)
	}
	return nil, nil
}

type fakeTransport struct{}

func (f *fakeTransport) Health(ctx context.Context) (transport.Health, error) {
	return transport.Health{}, nil
}
func (f *fakeTransport) ProbeEndpoint(ctx context.Context, endpoint string) (int, error) {
	return 200, nil
}
func (f *fakeTransport) CreateSession(ctx context.Context, req transport.CreateSessionRequest) (transport.Session, error) {
	return transport.Session{}, nil
}
func (f *fakeTransport) GetSession(ctx context.Context, sessionID string) (transport.Session, error) {
	return transport.Session{}, nil
}
func (f *fakeTransport) ListSessions(ctx context.Context, filter transport.SessionFilter) ([]transport.Session, error) {
	return nil, nil
}
func (f *fakeTransport) ProviderDefaults(ctx context.Context, directory, workspace string) (transport.ProviderDefaults, error) {
	return transport.ProviderDefaults{}, nil
}
func (f *fakeTransport) ListProviders(ctx context.Context, directory, workspace string) (transport.ProviderList, error) {
	return transport.ProviderList{}, nil
}
func (f *fakeTransport) ListProviderAuthMethods(ctx context.Context, directory, workspace string) (transport.ProviderAuthMethods, error) {
	return nil, nil
}
func (f *fakeTransport) SetProviderAPIKey(ctx context.Context, providerID, apiKey string) error {
	return nil
}
func (f *fakeTransport) SendPromptAsync(ctx context.Context, sessionID string, req transport.PromptRequest) error {
	return nil
}
func (f *fakeTransport) ReplyPermission(ctx context.Context, requestID string, _ string, decision transport.PermissionDecision) (bool, error) {
	return false, nil
}

func (f *fakeTransport) ReplyQuestion(ctx context.Context, requestID string, _ string, answers [][]string) (bool, error) {
	return false, nil
}

func (f *fakeTransport) RejectQuestion(ctx context.Context, requestID string, _ string) (bool, error) {
	return false, nil
}
func (f *fakeTransport) SubscribeEvents(ctx context.Context, filter transport.EventFilter) (<-chan transport.RawEvent, <-chan error) {
	return nil, nil
}
func (f *fakeTransport) ListAgents(ctx context.Context, directory, workspace string) ([]transport.Agent, error) {
	return nil, nil
}

type fakeConfigWriter struct {
	path  string
	agent string
	model string
}

func (f *fakeConfigWriter) SetDefaultAgent(agent string) error {
	f.agent = agent
	return nil
}
func (f *fakeConfigWriter) SetDefaultModel(model string) error {
	f.model = model
	return nil
}
func (f *fakeConfigWriter) SetDefaultVariant(variant string) error {
	return nil
}
func (f *fakeConfigWriter) ConfigPath() string {
	if f.path == "" {
		return "/fake/config.toml"
	}
	return f.path
}

func defaultOptions(cfg config.Config) Options {
	return Options{
		Runner:       &fakeRunner{},
		Sessions:     &fakeSessions{},
		Transport:    &fakeTransport{},
		Config:       cfg,
		ConfigWriter: &fakeConfigWriter{},
		Stdin:        strings.NewReader(""),
		Stdout:       io.Discard,
		CWD:          "/tmp",
	}
}

func TestNew_ValidatesRunner(t *testing.T) {
	opts := defaultOptions(config.Default())
	opts.Runner = nil
	_, err := New(opts)
	if err == nil {
		t.Fatal("expected error when runner is nil")
	}
}

func TestNew_ValidatesSessionResolver(t *testing.T) {
	opts := defaultOptions(config.Default())
	opts.Sessions = nil
	_, err := New(opts)
	if err == nil {
		t.Fatal("expected error when session resolver is nil")
	}
}

func TestNew_ValidatesTransport(t *testing.T) {
	opts := defaultOptions(config.Default())
	opts.Transport = nil
	_, err := New(opts)
	if err == nil {
		t.Fatal("expected error when transport is nil")
	}
}

func TestNew_ValidatesConfigWriter(t *testing.T) {
	opts := defaultOptions(config.Default())
	opts.ConfigWriter = nil
	_, err := New(opts)
	if err == nil {
		t.Fatal("expected error when config writer is nil")
	}
}

func TestNew_Defaults(t *testing.T) {
	opts := defaultOptions(config.Default())
	loop, err := New(opts)
	if err != nil {
		t.Fatalf("New() error: %v", err)
	}
	if loop == nil {
		t.Fatal("loop is nil")
	}
}

func TestPrompt_WithModel(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	cfg.DefaultModel = "opencode/gpt-4"
	r := &repl{cfg: cfg}
	prompt := r.prompt()
	expected := "witty [build:opencode/gpt-4] > "
	if prompt != expected {
		t.Fatalf("prompt = %q, want %q", prompt, expected)
	}
}

func TestPrompt_WithoutModel(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	cfg.DefaultModel = ""
	r := &repl{cfg: cfg}
	prompt := r.prompt()
	expected := "witty [build] > "
	if prompt != expected {
		t.Fatalf("prompt = %q, want %q", prompt, expected)
	}
}

func TestPrompt_DefaultAgentFallback(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = ""
	r := &repl{cfg: cfg}
	prompt := r.prompt()
	if !strings.Contains(prompt, config.DefaultAgent) {
		t.Fatalf("prompt %q should contain default agent %q", prompt, config.DefaultAgent)
	}
}

func TestPrompt_AgentOverride(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	r := &repl{cfg: cfg, agentOverride: "dev"}
	prompt := r.prompt()
	expected := "witty [dev] > "
	if prompt != expected {
		t.Fatalf("prompt = %q, want %q", prompt, expected)
	}
}

func TestPrompt_ModelOverride(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	cfg.DefaultModel = "opencode/gpt"
	r := &repl{cfg: cfg, modelOverride: "custom/model"}
	prompt := r.prompt()
	expected := "witty [build:custom/model] > "
	if prompt != expected {
		t.Fatalf("prompt = %q, want %q", prompt, expected)
	}
}

func TestEffectiveAgent_OverrideWins(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = "build"
	r := &repl{cfg: cfg, agentOverride: "dev"}
	if r.effectiveAgent() != "dev" {
		t.Fatalf("effectiveAgent = %q, want dev", r.effectiveAgent())
	}
}

func TestEffectiveAgent_Fallback(t *testing.T) {
	cfg := config.Default()
	cfg.DefaultAgent = ""
	r := &repl{cfg: cfg}
	if r.effectiveAgent() != config.DefaultAgent {
		t.Fatalf("effectiveAgent = %q, want %q", r.effectiveAgent(), config.DefaultAgent)
	}
}

func TestRun_ExitOnEOF(t *testing.T) {
	opts := defaultOptions(config.Default())
	opts.Stdin = strings.NewReader("")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() returned error on EOF: %v", err)
	}
}

func TestRun_ExitOnExitSlash(t *testing.T) {
	for _, cmd := range []string{"/exit\n", "/quit\n", "/q\n", "/EXIT\n", " /exit \n"} {
		t.Run(cmd, func(t *testing.T) {
			opts := defaultOptions(config.Default())
			opts.Stdin = strings.NewReader(cmd)
			runner := &fakeRunner{}
			opts.Runner = runner
			loop, err := New(opts)
			if err != nil {
				t.Fatal(err)
			}
			if err := loop.Run(context.Background()); err != nil {
				t.Fatalf("Run() returned error on %s: %v", cmd, err)
			}
			if runner.callCount() != 0 {
				t.Fatalf("runner called %d times for exit command %s", runner.callCount(), cmd)
			}
		})
	}
}

func TestRun_DispatchesToRunner(t *testing.T) {
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("check memory\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("runner call count = %d, want 1", runner.callCount())
	}
}

func TestRun_SkipsBlankLines(t *testing.T) {
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("\n\n\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 0 {
		t.Fatalf("runner called %d times for blank lines", runner.callCount())
	}
}

func TestRun_MultiplePrompts(t *testing.T) {
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("first\nsecond\nthird\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 3 {
		t.Fatalf("runner call count = %d, want 3", runner.callCount())
	}
}

func TestRun_RespectsParentCancellation(t *testing.T) {
	opts := defaultOptions(config.Default())
	opts.Stdin = strings.NewReader("")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := loop.Run(ctx); err != nil {
		t.Fatalf("Run() returned unexpected error: %v", err)
	}
}

func TestRun_RespectsParentCancellationBetweenAsks(t *testing.T) {
	r, w := io.Pipe()
	go func() {
		if _, werr := w.Write([]byte("first\n")); werr != nil {
			return
		}
	}()
	opts := defaultOptions(config.Default())
	opts.Stdin = r
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() {
		done <- loop.Run(ctx)
	}()
	time.Sleep(200 * time.Millisecond)
	cancel()
	_ = w.Close()
	select {
	case err := <-done:
		if err != nil {
			t.Fatalf("Run() returned unexpected error: %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("Run() did not return after parent cancellation")
	}
}

func TestRun_ErrorInRunner(t *testing.T) {
	runner := &fakeRunner{
		runFn: func(ctx context.Context, req core.AskRequest) error {
			return errors.New("something went wrong")
		},
	}
	var out strings.Builder
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("bad prompt\n/exit\n")
	opts.Stdout = &out
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	output := out.String()
	if !strings.Contains(output, "something went wrong") {
		t.Fatalf("output %q should contain error message", output)
	}
}

func TestRun_SlashHelp(t *testing.T) {
	var out strings.Builder
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("/help\n/exit\n")
	opts.Stdout = &out
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	output := out.String()
	if !strings.Contains(output, "/ask <prompt>") {
		t.Fatalf("help output should contain /ask: %q", output)
	}
	if runner.callCount() != 0 {
		t.Fatalf("runner should not be called for /help: %d calls", runner.callCount())
	}
}

func TestRun_SlashNew(t *testing.T) {
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("/new\ncheck memory\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("runner call count = %d, want 1", runner.callCount())
	}
}

func TestRun_SlashAsk(t *testing.T) {
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("/ask 检查系统内存\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("runner call count = %d, want 1", runner.callCount())
	}
}

func TestRun_SlashSessionList(t *testing.T) {
	var out strings.Builder
	sessions := &fakeSessions{
		listFn: func(ctx context.Context, scope session.Scope) ([]session.Summary, error) {
			return []session.Summary{
				{ID: "ses_1", Title: "Memory Check", Directory: "/work", Updated: 1718000000},
			}, nil
		},
	}
	opts := defaultOptions(config.Default())
	opts.Sessions = sessions
	opts.Stdin = strings.NewReader("/session list\n/exit\n")
	opts.Stdout = &out
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if !strings.Contains(out.String(), "ses_1\tMemory Check\t/work") {
		t.Fatalf("session list should contain ses_1: %q", out.String())
	}
}

func TestRun_SlashSessionContinue(t *testing.T) {
	var out strings.Builder
	opts := defaultOptions(config.Default())
	opts.Stdin = strings.NewReader("/session continue ses_123\ncheck memory\n/exit\n")
	opts.Stdout = &out
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if !strings.Contains(out.String(), "continued session ses_123") {
		t.Fatalf("session continue should show confirmation: %q", out.String())
	}
}

func TestRun_SlashUnknown_Suggestion(t *testing.T) {
	var out strings.Builder
	opts := defaultOptions(config.Default())
	opts.Stdin = strings.NewReader("/hel\n/exit\n")
	opts.Stdout = &out
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if !strings.Contains(out.String(), "did you mean /help") {
		t.Fatalf("unknown slash command should show suggestion: %q", out.String())
	}
}

func TestRun_SlashUnknown_NoSuggestion(t *testing.T) {
	runner := &fakeRunner{}
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("/usr/bin/ls\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("runner call count = %d, want 1 (fallback to agent)", runner.callCount())
	}
}

func TestRun_AutoResume_Disabled(t *testing.T) {
	runner := &fakeRunner{
		runFn: func(ctx context.Context, req core.AskRequest) error {
			if !req.ForceNew {
				return errors.New("expected ForceNew=true when auto_resume is disabled")
			}
			return nil
		},
	}
	cfg := config.Default()
	cfg.REPL.AutoResume = false
	opts := defaultOptions(cfg)
	opts.Runner = runner
	opts.Stdin = strings.NewReader("check memory\n/exit\n")
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("runner call count = %d, want 1", runner.callCount())
	}
}

func TestRun_SkippedValidation(t *testing.T) {
	runner := &fakeRunner{
		runFn: func(ctx context.Context, req core.AskRequest) error {
			if strings.TrimSpace(req.Prompt) == "" {
				return errors.New("prompt is required")
			}
			return nil
		},
	}
	var out strings.Builder
	opts := defaultOptions(config.Default())
	opts.Runner = runner
	opts.Stdin = strings.NewReader("valid\n/exit\n")
	opts.Stdout = &out
	loop, err := New(opts)
	if err != nil {
		t.Fatal(err)
	}
	if err := loop.Run(context.Background()); err != nil {
		t.Fatalf("Run() error: %v", err)
	}
	if runner.callCount() != 1 {
		t.Fatalf("call count = %d, want 1", runner.callCount())
	}
}

// Ensure the Loop interface is satisfied.
var _ Loop = (*repl)(nil)

// Ensure terminal.Prompter is not required (scanner-based REPL).
var _ = terminal.Prompter(nil)
