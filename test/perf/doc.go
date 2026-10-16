//go:build perf

// Package perf holds performance regression tests for the Bash Shell Adapter.
//
// They drive a real interactive Bash (readline) through a PTY, because the cost
// the Shell Adapter adds to a TAB press only exists in a real terminal: the
// adapter installs a DEBUG trap together with `shopt -s extdebug`, and extdebug
// makes the trap inherited by shell functions, command substitutions and
// subshells.  A command-heavy completion such as bash-completion's ssh host
// scan therefore runs the trap thousands of times per key press.
//
// Run on openEuler (Bash 5.x + readline), like the PTY tests:
//
//	TERM=xterm-256color go test -v -count=1 -tags=perf ./test/perf/
//
// The tests are excluded from `go test ./...` by the build tag and are meant to
// be run before/after changes to internal/shellinit (trap, classifier) or to the
// completion contract.  Budgets are intentionally generous - several times the
// values measured on openEuler 24.03 aarch64 - so they only fail on real
// regressions.  Two environment variables help on slower machines:
//
//	WITTY_PERF_BUDGET_FACTOR=2   scale every latency budget
//	WITTY_PERF_REPORT_ONLY=1     log budget violations instead of failing
package perf
