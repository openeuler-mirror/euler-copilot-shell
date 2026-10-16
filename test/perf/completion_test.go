//go:build perf

package perf

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

const (
	// measurementRepeats is how often each scenario is completed per session.
	// The best run is compared: scheduling noise only ever adds latency.
	measurementRepeats = 3

	// syntheticCompletionIterations mirrors the order of magnitude of
	// bash-completion's host scan: a few commands for every entry.
	syntheticCompletionIterations = 400

	// sshFixtureHosts sizes the generated ~/.ssh fixtures.  200 entries is a
	// small-to-average developer machine; the cost grows linearly with it.
	sshFixtureHosts = 200

	// Budgets are the maximum overhead the witty integration may add to one
	// completion, compared to the identical session without witty.  They are
	// several times the openEuler 24.03 aarch64 values measured when the
	// adapter is healthy (trap limited to user-typed lines), so they only fail
	// on real regressions - such as the extdebug trap running inside
	// completion functions, which cost seconds per TAB press.
	filenameCompletionBudget = 100 * time.Millisecond
	functionCompletionBudget = 300 * time.Millisecond
	sshCompletionBudget      = 800 * time.Millisecond

	// bashCompletionLib is the entry point of the bash-completion package; the
	// ssh scenario is skipped when it is not installed.
	bashCompletionLib = "/usr/share/bash-completion/bash_completion"
)

// TestShellAdapterPerf_FilenameCompletion guards the cheap path: completing a
// plain filename runs no shell commands, so witty must not add measurable cost.
func TestShellAdapterPerf_FilenameCompletion(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "witty-perf-target.txt"), "perf\n", 0o644)

	runCompletionCase(t, completionCase{
		name:     "filename completion",
		keys:     "perfcmd witty-perf-tar\t",
		budget:   filenameCompletionBudget,
		setup:    []string{"cd '" + dir + "'"},
		sshHosts: 0,
	})
}

// TestShellAdapterPerf_FunctionCompletion measures a programmable completion.
// bash-completion runs a shell function for every TAB press; with extdebug the
// witty DEBUG trap is inherited by that function, so the function's own simple
// commands are intercepted one by one.
func TestShellAdapterPerf_FunctionCompletion(t *testing.T) {
	script := writeScript(t, "completion.bash", fmt.Sprintf(`# Mimics a command-heavy bash-completion function: a handful of simple
# commands per scanned entry.
_witty_perf_complete() {
  local i
  for ((i = 0; i < %d; i++)); do
    [[ $i -ge 0 ]] || continue
    : "$i"
  done
  COMPREPLY=(perf-target)
}
complete -F _witty_perf_complete perfcmd
`, syntheticCompletionIterations))

	runCompletionCase(t, completionCase{
		name:     "function completion",
		keys:     "perfcmd \t",
		budget:   functionCompletionBudget,
		setup:    []string{"source '" + script + "'"},
		sshHosts: 0,
	})
}

// TestShellAdapterPerf_SSHHostCompletion is the scenario users report: typing
// `ssh host<TAB>` scans ~/.ssh/known_hosts, ~/.ssh/config and /etc/hosts with
// bash-completion.  With the trap inherited by the completion function every
// scanned entry costs several subprocess forks, and the shell freezes for
// seconds instead of milliseconds.
func TestShellAdapterPerf_SSHHostCompletion(t *testing.T) {
	if _, err := os.Stat(bashCompletionLib); err != nil {
		t.Skipf("bash-completion not installed (%s): install it to enable this scenario", bashCompletionLib)
	}

	runCompletionCase(t, completionCase{
		name:     "ssh host completion",
		keys:     "ssh host-199\t",
		budget:   sshCompletionBudget,
		setup:    []string{"source " + bashCompletionLib},
		sshHosts: sshFixtureHosts,
	})
}

type completionCase struct {
	// name is used in logs and failure messages.
	name string
	// keys are typed into the terminal; "\t" is the completion being measured.
	keys string
	// budget caps the overhead witty may add over the same completion without it.
	budget time.Duration
	// setup runs in both the baseline and the adapter session (cd, source ...).
	setup []string
	// sshHosts > 0 generates ~/.ssh fixtures of that size.
	sshHosts int
}

// runCompletionCase compares one completion with and without the witty Bash
// integration in two identical sessions, then reports latency, trap calls and
// whether the integration leaked a call to the witty binary.
func runCompletionCase(t *testing.T, tc completionCase) {
	t.Helper()

	home := newTestHome(t, tc.sshHosts)
	stubBinary, stubLog := writeWittyStub(t)
	initPath := writeWittyInit(t, stubBinary)

	baseline := startSession(t, home, tc.setup...)
	baselineTimes := measureCompletionLatency(t, baseline, tc.keys)

	adapterSetup := append(append([]string{}, tc.setup...), "source '"+initPath+"'")
	adapter := startSession(t, home, adapterSetup...)
	requireWittyTrap(t, adapter)
	adapterTimes := measureCompletionLatency(t, adapter, tc.keys)

	overhead := Best(adapterTimes) - Best(baselineTimes)
	t.Logf("%s: without witty %s", tc.name, FormatDurations(baselineTimes))
	t.Logf("%s: with witty    %s", tc.name, FormatDurations(adapterTimes))
	t.Logf("%s: overhead %s", tc.name, overhead.Round(time.Millisecond))

	calls := trapCallsDuringCompletion(t, home, adapterSetup, tc.keys)
	t.Logf("%s: DEBUG trap calls during one completion: %d", tc.name, calls)

	assertNoWittyDispatch(t, stubLog)
	checkBudget(t, tc.name, overhead, budgetFor(t, tc.budget))
}

// measureCompletionLatency runs one warm-up completion (first completions pay
// one-off costs such as bash-completion caching) before measuring.
func measureCompletionLatency(t *testing.T, s *session, keys string) []time.Duration {
	t.Helper()
	s.MeasureCompletion(keys)
	return s.MeasureSeries(keys, measurementRepeats)
}

// requireWittyTrap fails loudly when the rendered integration script did not
// install its DEBUG trap, which would silently turn every perf test green.
func requireWittyTrap(t *testing.T, s *session) {
	t.Helper()
	out := s.Run("trap -p DEBUG")
	if !strings.Contains(out, "__witty_debug_hook") {
		t.Fatalf("witty DEBUG trap is not installed after sourcing the init script: %q", out)
	}
}

// assertNoWittyDispatch asserts that completing a line never invoked the witty
// binary: completions are not user commands, so nothing may be routed to the
// agent.  A non-empty log also means a completion command was silently skipped
// and replaced by `witty ask` (extdebug semantics).
func assertNoWittyDispatch(t *testing.T, stubLog string) {
	t.Helper()
	content, err := os.ReadFile(stubLog)
	if err != nil && !os.IsNotExist(err) {
		t.Fatalf("read witty stub log: %v", err)
	}
	if len(content) > 0 {
		t.Errorf("witty was invoked during a completion, which must never happen: %q", content)
	}
}

// budgetFor applies WITTY_PERF_BUDGET_FACTOR so the suite can be used on slower
// machines without editing the constants.
func budgetFor(t *testing.T, def time.Duration) time.Duration {
	t.Helper()
	raw := os.Getenv("WITTY_PERF_BUDGET_FACTOR")
	if raw == "" {
		return def
	}
	factor, err := strconv.ParseFloat(raw, 64)
	if err != nil || factor <= 0 {
		t.Fatalf("WITTY_PERF_BUDGET_FACTOR=%q is not a positive number", raw)
	}
	return time.Duration(float64(def) * factor)
}

// checkBudget fails the test when the adapter overhead exceeds the budget.
// WITTY_PERF_REPORT_ONLY=1 downgrades the failure to a log line, which is handy
// while investigating a regression.
func checkBudget(t *testing.T, label string, overhead, budget time.Duration) {
	t.Helper()
	if overhead <= budget {
		t.Logf("%s: overhead %s within budget %s",
			label, overhead.Round(time.Millisecond), budget.Round(time.Millisecond))
		return
	}
	msg := fmt.Sprintf("%s: witty adds %s to a single completion, budget is %s. "+
		"The DEBUG trap is most likely running inside the completion function again: "+
		"extdebug makes the trap inherited by shell functions, so every simple command "+
		"bash-completion executes is intercepted (see internal/shellinit/templates/witty.bash.tmpl).",
		label, overhead.Round(time.Millisecond), budget.Round(time.Millisecond))
	if os.Getenv("WITTY_PERF_REPORT_ONLY") == "1" {
		t.Log("REPORT ONLY (WITTY_PERF_REPORT_ONLY=1): " + msg)
		return
	}
	t.Error(msg)
}
