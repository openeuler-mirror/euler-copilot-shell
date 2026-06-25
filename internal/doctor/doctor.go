// Package doctor runs environment diagnostics for witty.
package doctor

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

// Status is the severity level of a diagnostic check result.
type Status string

const (
	StatusOK   Status = "OK"
	StatusWARN Status = "WARN"
	StatusFAIL Status = "FAIL"
	StatusSKIP Status = "SKIP"
)

// Check is a single diagnostic result.
type Check struct {
	Name   string
	Status Status
	Detail string
	Hint   string
}

// HealthResult describes the opencode server health endpoint response.
type HealthResult struct {
	Healthy bool
	Version string
}

// Environment provides system/terminal context for diagnostics.
type Environment struct {
	// Config
	ConfigSearchPaths []string

	// Terminal
	StdoutIsTTY   bool
	StdinIsTTY    bool
	TerminalWidth int
	NoColor       bool
	SupportsColor bool

	// Shell
	Term           string
	ShellLoaded    bool
	InteractiveTTY bool
}

// ConfigSummary is the subset of config values shown by the doctor.
type ConfigSummary struct {
	ServerURL       string
	DefaultAgent    string
	DefaultModel    string
	Theme           string
	NoColor         bool
	ShellEnabled    bool
	RendererPhase   int
	TimeoutSeconds  int
	ServerAutoStart bool
	ServerManaged   bool
	ServerPort      int
	ServerPID       int
}

// ServerProbe checks opencode server endpoints.
type ServerProbe interface {
	Health(ctx context.Context) (HealthResult, error)
	ProbeEndpoint(ctx context.Context, endpoint string) (int, error)
}

// Options configures the diagnostic runner.
type Options struct {
	Config  ConfigSummary
	Env     Environment
	Server  ServerProbe
	Timeout time.Duration
}

// Runner runs all diagnostic checks and returns the results.
type Runner interface {
	Run(ctx context.Context) []Check
}

type runner struct {
	cfg     ConfigSummary
	env     Environment
	server  ServerProbe
	timeout time.Duration
}

// New creates a diagnostic runner from the given options.
func New(opts Options) Runner {
	timeout := opts.Timeout
	if timeout <= 0 {
		timeout = 5 * time.Second
	}
	return &runner{
		cfg:     opts.Config,
		env:     opts.Env,
		server:  opts.Server,
		timeout: timeout,
	}
}

// Run executes all diagnostic checks in order and returns the results.
func (r *runner) Run(ctx context.Context) []Check {
	var checks []Check
	checks = append(checks, r.checkConfig())

	serverOK, serverCheck := r.checkServerReachable(ctx)
	checks = append(checks, serverCheck)

	if serverOK {
		checks = append(checks, r.checkDocEndpoint(ctx))
		checks = append(checks, r.checkEventEndpoint(ctx))
	} else {
		checks = append(checks, Check{Name: "/doc endpoint", Status: StatusSKIP, Detail: "server unreachable"})
		checks = append(checks, Check{Name: "/event endpoint", Status: StatusSKIP, Detail: "server unreachable"})
	}

	checks = append(checks, r.checkServerManagement())
	checks = append(checks, r.checkShellIntegration())
	checks = append(checks, r.checkBashEnvironment())
	checks = append(checks, r.checkTerminal())
	return checks
}

func (r *runner) checkConfig() Check {
	const name = "config"
	var existing []string
	for _, path := range r.env.ConfigSearchPaths {
		if path == "" {
			continue
		}
		if _, err := os.Stat(path); err == nil {
			existing = append(existing, path)
		}
	}

	var detailParts []string
	if len(existing) > 0 {
		detailParts = append(detailParts, "loaded: "+strings.Join(existing, ", "))
	} else {
		detailParts = append(detailParts, "no config file found (using defaults)")
	}
	detailParts = append(detailParts, fmt.Sprintf("server=%s agent=%s model=%s shell=%s",
		r.cfg.ServerURL, r.cfg.DefaultAgent, maskModel(r.cfg.DefaultModel), shellEnabledLabel(r.cfg.ShellEnabled)))

	status := StatusOK
	if len(existing) == 0 {
		status = StatusWARN
	}
	return Check{
		Name:   name,
		Status: status,
		Detail: strings.Join(detailParts, "; "),
		Hint:   hintForConfig(existing),
	}
}

func (r *runner) checkServerReachable(ctx context.Context) (bool, Check) {
	const name = "server reachable"
	if r.server == nil {
		return false, Check{Name: name, Status: StatusSKIP, Detail: "no server probe configured"}
	}

	probeCtx, cancel := context.WithTimeout(ctx, r.timeout)
	defer cancel()

	health, err := r.server.Health(probeCtx)
	if err != nil {
		return false, Check{
			Name:   name,
			Status: StatusFAIL,
			Detail: sanitizeErr(err),
			Hint:   "ensure opencode is running (try: opencode serve --port 4096)",
		}
	}
	if !health.Healthy {
		return true, Check{
			Name:   name,
			Status: StatusWARN,
			Detail: fmt.Sprintf("server reports unhealthy (version %s)", health.Version),
		}
	}
	return true, Check{
		Name:   name,
		Status: StatusOK,
		Detail: fmt.Sprintf("connected to %s (opencode %s)", r.cfg.ServerURL, health.Version),
	}
}

func (r *runner) checkDocEndpoint(ctx context.Context) Check {
	const name = "/doc endpoint"
	return r.probeEndpoint(ctx, name, "/doc")
}

func (r *runner) checkEventEndpoint(ctx context.Context) Check {
	const name = "/event endpoint"
	return r.probeEndpoint(ctx, name, "/event")
}

func (r *runner) probeEndpoint(ctx context.Context, name, endpoint string) Check {
	if r.server == nil {
		return Check{Name: name, Status: StatusSKIP, Detail: "no server probe configured"}
	}

	probeCtx, cancel := context.WithTimeout(ctx, r.timeout)
	defer cancel()

	code, err := r.server.ProbeEndpoint(probeCtx, endpoint)
	if err != nil {
		return Check{
			Name:   name,
			Status: StatusFAIL,
			Detail: sanitizeErr(err),
		}
	}
	if code >= 200 && code < 300 {
		return Check{Name: name, Status: StatusOK, Detail: fmt.Sprintf("HTTP %d", code)}
	}
	return Check{
		Name:   name,
		Status: StatusFAIL,
		Detail: fmt.Sprintf("HTTP %d", code),
	}
}

func (r *runner) checkShellIntegration() Check {
	const name = "shell integration"
	if r.env.ShellLoaded {
		return Check{Name: name, Status: StatusOK, Detail: "witty bash integration is loaded"}
	}
	if !r.env.InteractiveTTY {
		return Check{Name: name, Status: StatusSKIP, Detail: "non-interactive shell; integration not expected"}
	}
	return Check{
		Name:   name,
		Status: StatusWARN,
		Detail: "not loaded in current shell",
		Hint:   `run: eval "$(witty init bash)"`,
	}
}

func (r *runner) checkBashEnvironment() Check {
	const name = "bash environment"
	var details []string
	var hints []string
	hasIssue := false

	// TERM
	term := r.env.Term
	switch term {
	case "":
		details = append(details, "TERM is unset")
		hasIssue = true
		hints = append(hints, "set TERM (e.g. export TERM=xterm-256color)")
	case "dumb":
		details = append(details, "TERM=dumb (limited capability)")
		hasIssue = true
	default:
		details = append(details, "TERM="+term)
	}

	// Bash version
	if version, ok := detectBashVersion(); ok {
		details = append(details, "bash "+version)
		if !bashVersionOK(version) {
			hasIssue = true
			hints = append(hints, "witty requires bash >= 4.0")
		}
	} else {
		details = append(details, "bash not found on PATH")
		hasIssue = true
		hints = append(hints, "install bash >= 4.0")
	}

	status := StatusOK
	if hasIssue {
		status = StatusWARN
	}
	return Check{
		Name:   name,
		Status: status,
		Detail: strings.Join(details, "; "),
		Hint:   strings.Join(hints, "; "),
	}
}

func (r *runner) checkServerManagement() Check {
	const name = "server management"
	if !r.cfg.ServerAutoStart {
		return Check{
			Name:   name,
			Status: StatusSKIP,
			Detail: "auto_start is disabled; server lifecycle is not managed",
			Hint:   "set server.auto_start = true in config to enable automatic server management",
		}
	}
	if !r.cfg.ServerManaged {
		return Check{
			Name:   name,
			Status: StatusWARN,
			Detail: "server was discovered (not started by this process); limited lifecycle control",
		}
	}
	detail := fmt.Sprintf("managed by this process, port=%d, pid=%d", r.cfg.ServerPort, r.cfg.ServerPID)
	return Check{
		Name:   name,
		Status: StatusOK,
		Detail: detail,
	}
}

func (r *runner) checkTerminal() Check {
	const name = "terminal"
	var details []string
	hasIssue := false

	if r.env.StdoutIsTTY {
		details = append(details, "stdout is a terminal")
	} else {
		details = append(details, "stdout is piped (non-TTY)")
		hasIssue = true
	}

	if r.env.TerminalWidth > 0 {
		details = append(details, fmt.Sprintf("width=%d", r.env.TerminalWidth))
	} else {
		details = append(details, "width unknown")
	}

	if r.env.NoColor {
		details = append(details, "color disabled (NO_COLOR)")
	} else if r.env.SupportsColor {
		details = append(details, "color enabled")
	} else {
		details = append(details, "no color (non-TTY)")
	}

	status := StatusOK
	if hasIssue {
		status = StatusWARN
	}
	return Check{
		Name:   name,
		Status: status,
		Detail: strings.Join(details, "; "),
	}
}

// Format renders checks as a human-readable diagnostic report.
func Format(checks []Check) string {
	var b strings.Builder
	b.WriteString("witty doctor — environment diagnostics\n\n")

	var ok, warn, fail, skip int
	for _, c := range checks {
		switch c.Status {
		case StatusOK:
			ok++
		case StatusWARN:
			warn++
		case StatusFAIL:
			fail++
		case StatusSKIP:
			skip++
		}
		b.WriteString(formatCheck(c))
		b.WriteString("\n")
	}

	b.WriteString("\n")
	fmt.Fprintf(&b, "Summary: %d OK, %d WARN, %d FAIL, %d SKIP\n", ok, warn, fail, skip)
	return b.String()
}

func formatCheck(c Check) string {
	label := fmt.Sprintf("[%s]", c.Status)
	line := fmt.Sprintf("  %-6s %s: %s", label, c.Name, c.Detail)
	if c.Hint != "" {
		line += "\n         hint: " + c.Hint
	}
	return line
}

// sanitizeErr strips potentially sensitive information from error messages.
func sanitizeErr(err error) string {
	if err == nil {
		return ""
	}
	msg := err.Error()
	// Truncate long error bodies that may contain headers or response payloads.
	if len(msg) > 200 {
		msg = msg[:200] + "..."
	}
	return msg
}

func maskModel(model string) string {
	if model == "" {
		return "(none)"
	}
	return model
}

func shellEnabledLabel(enabled bool) string {
	if enabled {
		return "enabled"
	}
	return "disabled"
}

func hintForConfig(existing []string) string {
	if len(existing) > 0 {
		return ""
	}
	return "create ~/.config/witty/config.toml or use --config"
}

// detectBashVersion runs `bash --version` and extracts the version string.
func detectBashVersion() (string, bool) {
	cmd := exec.Command("bash", "--version")
	output, err := cmd.Output()
	if err != nil {
		return "", false
	}
	line := strings.SplitN(string(output), "\n", 2)[0]
	// Example: "GNU bash, version 5.2.15(1)-release"
	if idx := strings.Index(line, "version "); idx >= 0 {
		rest := line[idx+len("version "):]
		if sp := strings.IndexByte(rest, ','); sp >= 0 {
			rest = rest[:sp]
		}
		return strings.TrimSpace(rest), true
	}
	return strings.TrimSpace(line), true
}

// bashVersionOK checks if a bash version string is >= 4.0.
func bashVersionOK(version string) bool {
	major := extractMajorVersion(version)
	return major >= 4
}

func extractMajorVersion(version string) int {
	var major int
	for _, ch := range version {
		if ch >= '0' && ch <= '9' {
			major = major*10 + int(ch-'0')
		} else {
			break
		}
	}
	return major
}
