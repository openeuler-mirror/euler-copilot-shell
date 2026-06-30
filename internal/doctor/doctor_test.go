package doctor

import (
	"context"
	"errors"
	"os"
	"strings"
	"testing"
	"time"
)

// fakeServerProbe is a test double for ServerProbe.
type fakeServerProbe struct {
	health      HealthResult
	healthErr   error
	probeStatus int
	probeErr    error
	probeCalls  []string
}

func (f *fakeServerProbe) Health(_ context.Context) (HealthResult, error) {
	return f.health, f.healthErr
}

func (f *fakeServerProbe) ProbeEndpoint(_ context.Context, endpoint string) (int, error) {
	f.probeCalls = append(f.probeCalls, endpoint)
	return f.probeStatus, f.probeErr
}

func baseEnv() Environment {
	return Environment{
		ConfigSearchPaths: []string{"/etc/witty/config.toml", "/home/user/.config/witty/config.toml"},
		StdoutIsTTY:       true,
		StdinIsTTY:        true,
		TerminalWidth:     120,
		SupportsColor:     true,
		Term:              "xterm-256color",
		InteractiveTTY:    true,
	}
}

func baseConfig() ConfigSummary {
	return ConfigSummary{
		ServerURL:       "http://127.0.0.1:4096",
		DefaultAgent:    "build",
		DefaultModel:    "opencode/gpt-5",
		ShellEnabled:    true,
		RendererPhase:   1,
		TimeoutSeconds:  5,
		ServerAutoStart: true,
		ServerManaged:   true,
		ServerPort:      4096,
		ServerPID:       12345,
	}
}

func TestRun_AllChecksPass(t *testing.T) {
	probe := &fakeServerProbe{
		health:      HealthResult{Healthy: true, Version: "1.0.0"},
		probeStatus: 200,
	}
	r := New(Options{
		Config: baseConfig(),
		Env:    baseEnv(),
		Server: probe,
	})

	checks := r.Run(context.Background())
	if len(checks) != 9 {
		t.Fatalf("Run() returned %d checks, want 9", len(checks))
	}

	for _, c := range checks {
		if c.Status == StatusFAIL {
			t.Errorf("check %q status = FAIL, want not FAIL; detail: %s", c.Name, c.Detail)
		}
	}

	if len(probe.probeCalls) != 2 {
		t.Errorf("probe calls = %v, want 2 endpoints probed", probe.probeCalls)
	}
}

func TestRun_ServerUnreachable_SkipsEndpointChecks(t *testing.T) {
	probe := &fakeServerProbe{
		healthErr: errors.New("connection refused"),
	}
	r := New(Options{
		Config: baseConfig(),
		Env:    baseEnv(),
		Server: probe,
	})

	checks := r.Run(context.Background())

	serverCheck := findCheck(checks, "server reachable")
	if serverCheck.Status != StatusFAIL {
		t.Errorf("server reachable status = %s, want FAIL", serverCheck.Status)
	}
	if !strings.Contains(serverCheck.Detail, "connection refused") {
		t.Errorf("server reachable detail = %q, want connection refused", serverCheck.Detail)
	}

	docCheck := findCheck(checks, "/doc endpoint")
	if docCheck.Status != StatusSKIP {
		t.Errorf("/doc endpoint status = %s, want SKIP", docCheck.Status)
	}
	eventCheck := findCheck(checks, "/event endpoint")
	if eventCheck.Status != StatusSKIP {
		t.Errorf("/event endpoint status = %s, want SKIP", eventCheck.Status)
	}

	if len(probe.probeCalls) != 0 {
		t.Errorf("probe calls = %v, want 0 when server is unreachable", probe.probeCalls)
	}
}

func TestRun_ServerUnreachable_PinpointsConnectionFailure(t *testing.T) {
	probe := &fakeServerProbe{
		healthErr: errors.New("dial tcp 127.0.0.1:4096: connect: connection refused"),
	}
	r := New(Options{
		Config: baseConfig(),
		Env:    baseEnv(),
		Server: probe,
	})

	checks := r.Run(context.Background())
	serverCheck := findCheck(checks, "server reachable")
	if serverCheck.Status != StatusFAIL {
		t.Fatalf("status = %s, want FAIL", serverCheck.Status)
	}
	if !strings.Contains(serverCheck.Detail, "connection refused") {
		t.Errorf("detail = %q, want to contain 'connection refused'", serverCheck.Detail)
	}
	if !strings.Contains(serverCheck.Hint, "opencode serve") {
		t.Errorf("hint = %q, want to contain 'opencode serve'", serverCheck.Hint)
	}
}

func TestRun_NilServerProbe_SkipsServerChecks(t *testing.T) {
	r := New(Options{
		Config: baseConfig(),
		Env:    baseEnv(),
		Server: nil,
	})

	checks := r.Run(context.Background())

	serverCheck := findCheck(checks, "server reachable")
	if serverCheck.Status != StatusSKIP {
		t.Errorf("server reachable status = %s, want SKIP", serverCheck.Status)
	}
	docCheck := findCheck(checks, "/doc endpoint")
	if docCheck.Status != StatusSKIP {
		t.Errorf("/doc endpoint status = %s, want SKIP", docCheck.Status)
	}
}

func TestCheckShellIntegration_Loaded(t *testing.T) {
	r := &runner{
		env: Environment{ShellLoaded: true, InteractiveTTY: true},
	}
	c := r.checkShellIntegration()
	if c.Status != StatusOK {
		t.Errorf("status = %s, want OK", c.Status)
	}
}

func TestCheckShellIntegration_NotLoadedInteractive(t *testing.T) {
	r := &runner{
		env: Environment{ShellLoaded: false, InteractiveTTY: true},
	}
	c := r.checkShellIntegration()
	if c.Status != StatusWARN {
		t.Errorf("status = %s, want WARN", c.Status)
	}
	if !strings.Contains(c.Hint, "witty init bash") {
		t.Errorf("hint = %q, want to contain 'witty init bash'", c.Hint)
	}
}

func TestCheckShellIntegration_NotLoadedNonInteractive(t *testing.T) {
	r := &runner{
		env: Environment{ShellLoaded: false, InteractiveTTY: false},
	}
	c := r.checkShellIntegration()
	if c.Status != StatusSKIP {
		t.Errorf("status = %s, want SKIP for non-interactive shell", c.Status)
	}
}

func TestCheckConfig_FileExists(t *testing.T) {
	tmpDir := t.TempDir()
	configPath := tmpDir + "/config.toml"
	if err := writeFile(configPath, "server_url = \"http://localhost:4096\"\n"); err != nil {
		t.Fatalf("write file: %v", err)
	}

	r := &runner{
		cfg: baseConfig(),
		env: Environment{ConfigSearchPaths: []string{configPath}},
	}
	c := r.checkConfig()
	if c.Status != StatusOK {
		t.Errorf("status = %s, want OK", c.Status)
	}
	if !strings.Contains(c.Detail, "loaded:") {
		t.Errorf("detail = %q, want to contain 'loaded:'", c.Detail)
	}
}

func TestCheckConfig_NoFileFound(t *testing.T) {
	r := &runner{
		cfg: baseConfig(),
		env: Environment{ConfigSearchPaths: []string{"/nonexistent/path.toml"}},
	}
	c := r.checkConfig()
	if c.Status != StatusWARN {
		t.Errorf("status = %s, want WARN", c.Status)
	}
	if !strings.Contains(c.Detail, "using defaults") {
		t.Errorf("detail = %q, want to contain 'using defaults'", c.Detail)
	}
}

func TestCheckServerReachable_Healthy(t *testing.T) {
	probe := &fakeServerProbe{
		health: HealthResult{Healthy: true, Version: "1.2.3"},
	}
	r := &runner{
		cfg:     baseConfig(),
		server:  probe,
		timeout: 5 * time.Second,
	}
	ok, c := r.checkServerReachable(context.Background())
	if !ok {
		t.Error("ok = false, want true")
	}
	if c.Status != StatusOK {
		t.Errorf("status = %s, want OK", c.Status)
	}
	if !strings.Contains(c.Detail, "1.2.3") {
		t.Errorf("detail = %q, want version 1.2.3", c.Detail)
	}
}

func TestCheckServerReachable_Unhealthy(t *testing.T) {
	probe := &fakeServerProbe{
		health: HealthResult{Healthy: false, Version: "1.0.0"},
	}
	r := &runner{
		cfg:     baseConfig(),
		server:  probe,
		timeout: 5 * time.Second,
	}
	ok, c := r.checkServerReachable(context.Background())
	if !ok {
		t.Error("ok = false, want true (server is reachable but unhealthy)")
	}
	if c.Status != StatusWARN {
		t.Errorf("status = %s, want WARN", c.Status)
	}
}

func TestCheckServerReachable_ConnectionError(t *testing.T) {
	probe := &fakeServerProbe{
		healthErr: errors.New("dial tcp 127.0.0.1:4096: connect: connection refused"),
	}
	r := &runner{
		cfg:     baseConfig(),
		server:  probe,
		timeout: 5 * time.Second,
	}
	ok, c := r.checkServerReachable(context.Background())
	if ok {
		t.Error("ok = true, want false")
	}
	if c.Status != StatusFAIL {
		t.Errorf("status = %s, want FAIL", c.Status)
	}
}

func TestProbeEndpoint_OK(t *testing.T) {
	probe := &fakeServerProbe{probeStatus: 200}
	r := &runner{
		server:  probe,
		timeout: 5 * time.Second,
	}
	c := r.probeEndpoint(context.Background(), "/doc", "/doc")
	if c.Status != StatusOK {
		t.Errorf("status = %s, want OK", c.Status)
	}
}

func TestProbeEndpoint_NonOK(t *testing.T) {
	probe := &fakeServerProbe{probeStatus: 404}
	r := &runner{
		server:  probe,
		timeout: 5 * time.Second,
	}
	c := r.probeEndpoint(context.Background(), "/doc", "/doc")
	if c.Status != StatusFAIL {
		t.Errorf("status = %s, want FAIL for HTTP 404", c.Status)
	}
}

func TestProbeEndpoint_Error(t *testing.T) {
	probe := &fakeServerProbe{probeErr: errors.New("timeout")}
	r := &runner{
		server:  probe,
		timeout: 5 * time.Second,
	}
	c := r.probeEndpoint(context.Background(), "/doc", "/doc")
	if c.Status != StatusFAIL {
		t.Errorf("status = %s, want FAIL", c.Status)
	}
}

func TestCheckTerminal_TTY(t *testing.T) {
	r := &runner{
		env: Environment{
			StdoutIsTTY:   true,
			TerminalWidth: 80,
			SupportsColor: true,
		},
	}
	c := r.checkTerminal()
	if c.Status != StatusOK {
		t.Errorf("status = %s, want OK", c.Status)
	}
}

func TestCheckTerminal_NonTTY(t *testing.T) {
	r := &runner{
		env: Environment{
			StdoutIsTTY:   false,
			TerminalWidth: 80,
			SupportsColor: false,
		},
	}
	c := r.checkTerminal()
	if c.Status != StatusWARN {
		t.Errorf("status = %s, want WARN for non-TTY", c.Status)
	}
}

func TestCheckBashEnvironment_TermUnset(t *testing.T) {
	r := &runner{
		env: Environment{Term: ""},
	}
	c := r.checkBashEnvironment()
	if c.Status != StatusWARN {
		t.Errorf("status = %s, want WARN for unset TERM", c.Status)
	}
	if !strings.Contains(c.Detail, "TERM is unset") {
		t.Errorf("detail = %q, want TERM is unset", c.Detail)
	}
}

func TestCheckBashEnvironment_TermDumb(t *testing.T) {
	r := &runner{
		env: Environment{Term: "dumb"},
	}
	c := r.checkBashEnvironment()
	if c.Status != StatusWARN {
		t.Errorf("status = %s, want WARN for TERM=dumb", c.Status)
	}
}

func TestFormat_ContainsAllStatuses(t *testing.T) {
	checks := []Check{
		{Name: "check1", Status: StatusOK, Detail: "all good"},
		{Name: "check2", Status: StatusWARN, Detail: "minor issue", Hint: "fix this"},
		{Name: "check3", Status: StatusFAIL, Detail: "broken"},
		{Name: "check4", Status: StatusSKIP, Detail: "skipped"},
	}
	output := Format(checks)
	for _, s := range []string{"OK", "WARN", "FAIL", "SKIP"} {
		if !strings.Contains(output, s) {
			t.Errorf("output does not contain %q", s)
		}
	}
	if !strings.Contains(output, "Summary:") {
		t.Error("output does not contain Summary")
	}
	if !strings.Contains(output, "1 OK, 1 WARN, 1 FAIL, 1 SKIP") {
		t.Errorf("output does not contain correct summary counts")
	}
	if !strings.Contains(output, "hint: fix this") {
		t.Errorf("output does not contain hint")
	}
}

func TestFormat_DoesNotLeakSensitiveData(t *testing.T) {
	checks := []Check{
		{Name: "server reachable", Status: StatusFAIL, Detail: sanitizeErr(errors.New(strings.Repeat("x", 300)))},
	}
	output := Format(checks)
	// Verify the error detail is truncated
	lines := strings.Split(output, "\n")
	for _, line := range lines {
		if strings.Contains(line, "server reachable") {
			if len(line) > 250 {
				t.Errorf("detail line too long (%d chars), potential data leak", len(line))
			}
		}
	}
}

func TestSanitizeErr_Truncates(t *testing.T) {
	long := strings.Repeat("a", 300)
	result := sanitizeErr(errors.New(long))
	if len(result) > 210 {
		t.Errorf("sanitizeErr result length = %d, want <= 210", len(result))
	}
	if !strings.HasSuffix(result, "...") {
		t.Errorf("sanitizeErr result should end with '...'")
	}
}

func TestSanitizeErr_NilErr(t *testing.T) {
	result := sanitizeErr(nil)
	if result != "" {
		t.Errorf("sanitizeErr(nil) = %q, want empty string", result)
	}
}

func TestMaskModel_Empty(t *testing.T) {
	if maskModel("") != "(none)" {
		t.Error("maskModel(\"\") should return (none)")
	}
	if maskModel("openai/gpt-4") != "openai/gpt-4" {
		t.Error("maskModel should return the model unchanged")
	}
}

func TestBashVersionOK(t *testing.T) {
	tests := []struct {
		version string
		want    bool
	}{
		{"5.2.15(1)-release", true},
		{"4.0.0", true},
		{"3.2.57(1)-release", false},
		{"0.1", false},
		{"", false},
	}
	for _, tt := range tests {
		if got := bashVersionOK(tt.version); got != tt.want {
			t.Errorf("bashVersionOK(%q) = %v, want %v", tt.version, got, tt.want)
		}
	}
}

func TestExtractMajorVersion(t *testing.T) {
	tests := []struct {
		version string
		want    int
	}{
		{"5.2.15", 5},
		{"4.0", 4},
		{"3.2", 3},
		{"", 0},
		{"abc", 0},
	}
	for _, tt := range tests {
		if got := extractMajorVersion(tt.version); got != tt.want {
			t.Errorf("extractMajorVersion(%q) = %d, want %d", tt.version, got, tt.want)
		}
	}
}

func TestNew_DefaultTimeout(t *testing.T) {
	r := New(Options{
		Config: baseConfig(),
		Env:    baseEnv(),
		Server: nil,
	})
	rr := r.(*runner)
	if rr.timeout != 5*time.Second {
		t.Errorf("default timeout = %v, want 5s", rr.timeout)
	}
}

func TestNew_CustomTimeout(t *testing.T) {
	r := New(Options{
		Config:  baseConfig(),
		Env:     baseEnv(),
		Server:  nil,
		Timeout: 10 * time.Second,
	})
	rr := r.(*runner)
	if rr.timeout != 10*time.Second {
		t.Errorf("timeout = %v, want 10s", rr.timeout)
	}
}

func TestNew_TimeoutFromConfig(t *testing.T) {
	cfg := baseConfig()
	cfg.TimeoutSeconds = 15
	r := New(Options{
		Config: cfg,
		Env:    baseEnv(),
		Server: nil,
	})
	rr := r.(*runner)
	// When Timeout is not set in Options, it defaults to 5s
	// (the doctor module doesn't read TimeoutSeconds from ConfigSummary,
	// the caller passes the timeout via Options.Timeout)
	if rr.timeout != 5*time.Second {
		t.Errorf("timeout = %v, want 5s (default)", rr.timeout)
	}
}

func findCheck(checks []Check, name string) Check {
	for _, c := range checks {
		if c.Name == name {
			return c
		}
	}
	return Check{}
}

func writeFile(path, content string) error {
	return os.WriteFile(path, []byte(content), 0o644)
}
