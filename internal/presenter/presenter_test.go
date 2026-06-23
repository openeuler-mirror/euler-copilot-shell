package presenter

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

var updatePresenterGolden = flag.Bool("update", false, "update presenter golden files")

func TestPresenter_Golden(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: true})
	ctx := context.Background()

	events := []event.AppEvent{
		// Step events now produce zero output (accumulate internally).
		{Kind: event.EventStepStarted},
		{Kind: event.EventStepEnded, Payload: event.StepEndedPayload{Cost: 1.25, Tokens: event.StepTokens{Input: 1, Output: 2, Reasoning: 3}, Duration: 3.5}},
		{Kind: event.EventAgentSwitched, Payload: event.AgentSwitchedPayload{AgentID: "code", AgentName: "Coder"}},
		{Kind: event.EventModelSwitched, Payload: event.ModelSwitchedPayload{ProviderID: "deepseek", ModelID: "deepseek-v4-flash"}},
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "bash", CallID: "call_1", Input: json.RawMessage(`{"cmd":"ls"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "call_1", Output: "ok"}},
		{Kind: event.EventToolFailed, Payload: event.ToolResultPayload{CallID: "call_2", Error: "permission denied"}},
		{Kind: event.EventPermissionAsked, Payload: event.PermissionAskedPayload{RequestID: "per_1", Permission: "tool", Patterns: []string{"bash", "read"}}},
		{Kind: event.EventQuestionAsked, Payload: event.QuestionAskedPayload{RequestID: "que_1", Questions: []event.QuestionInfo{{Question: "Continue?", Options: []event.QuestionOption{{Label: "yes", Description: "do it"}}, Multiple: false, Custom: true}}}},
		{Kind: event.EventUnknown, Payload: event.UnknownPayload{Type: "custom.event", Summary: "something happened"}},
		// SessionIdle outputs the accumulated summary.
		{Kind: event.EventSessionIdle},
	}
	for _, evt := range events {
		if err := p.PresentEvent(ctx, evt); err != nil {
			t.Fatalf("PresentEvent(%s) error = %v", evt.Kind, err)
		}
	}

	errs := []error{
		&UserError{Op: "ask", Err: errors.New("prompt is required")},
		&url.Error{Op: "Get", URL: "http://127.0.0.1:4096", Err: errors.New("connection refused")},
		&transport.HTTPError{StatusCode: 500, Endpoint: "/session", Summary: "boom"},
		&SchemaError{Op: "normalize event", Err: errors.New("invalid json")},
	}
	for _, err := range errs {
		if err := p.PresentError(ctx, err); err != nil {
			t.Fatalf("PresentError(%T) error = %v", err, err)
		}
	}

	assertGolden(t, filepath.Join("..", "..", "test", "testdata", "presenter", "basic_ansi.golden"), out.Bytes())
}

func TestPresenter_FullFlowGolden(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: true, GroupContextTools: true})
	ctx := context.Background()

	// Simulate a full event flow: reasoning step -> context tools -> bash -> task -> idle summary.
	// Note: reasoning and text deltas are handled by the renderer (not presenter),
	// so this golden test covers the presenter's event handling portion.
	events := []event.AppEvent{
		// Step 1: Reasoning step (agent/model switch, internal only).
		{Kind: event.EventStepStarted},
		{Kind: event.EventAgentSwitched, Payload: event.AgentSwitchedPayload{AgentID: "code", AgentName: "Coder"}},
		{Kind: event.EventModelSwitched, Payload: event.ModelSwitchedPayload{ProviderID: "deepseek", ModelID: "deepseek-v4-flash"}},

		// Step 1: Context tools (read, grep, glob) - should be grouped.
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "read", CallID: "ctx_1", Input: json.RawMessage(`{"filePath":"/src/main.go"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "ctx_1", Output: "package main"}},
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "grep", CallID: "ctx_2", Input: json.RawMessage(`{"pattern":"TODO"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "ctx_2", Output: "3 matches"}},
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "glob", CallID: "ctx_3", Input: json.RawMessage(`{"pattern":"*.go"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "ctx_3", Output: "main.go, util.go"}},

		{Kind: event.EventStepEnded, Payload: event.StepEndedPayload{Cost: 0.01, Tokens: event.StepTokens{Input: 200, Output: 50, Reasoning: 100}, Duration: 1.5}},

		// Step 2: Bash tool.
		{Kind: event.EventStepStarted},
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "bash", CallID: "bash_1", Input: json.RawMessage(`{"command":"go build ./...","description":"Build the project"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "bash_1", Output: "Build succeeded"}},

		{Kind: event.EventStepEnded, Payload: event.StepEndedPayload{Cost: 0.02, Tokens: event.StepTokens{Input: 150, Output: 300, Reasoning: 0}, Duration: 5.2}},

		// Step 3: Task tool.
		{Kind: event.EventStepStarted},
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "task", CallID: "task_1", Input: json.RawMessage(`{"description":"Fix all lint errors","subagent_type":"build"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "task_1", Output: "All lint errors fixed (3 files)"}},

		{Kind: event.EventStepEnded, Payload: event.StepEndedPayload{Cost: 0.15, Tokens: event.StepTokens{Input: 500, Output: 800, Reasoning: 200}, Duration: 12.0}},

		// Final: SessionIdle outputs the accumulated summary across all steps.
		{Kind: event.EventSessionIdle},
	}
	for _, evt := range events {
		if err := p.PresentEvent(ctx, evt); err != nil {
			t.Fatalf("PresentEvent(%s) error = %v", evt.Kind, err)
		}
	}

	assertGolden(t, filepath.Join("..", "..", "test", "testdata", "presenter", "full_flow_ansi.golden"), out.Bytes())
}

func TestPresenter_NonTTYOutputHasNoANSI(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false})
	ctx := context.Background()

	events := []event.AppEvent{
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "bash", CallID: "call_1", Input: json.RawMessage(`{"cmd":"pwd"}`)}},
		{Kind: event.EventAgentSwitched, Payload: event.AgentSwitchedPayload{AgentID: "code", AgentName: "Coder"}},
		{Kind: event.EventModelSwitched, Payload: event.ModelSwitchedPayload{ProviderID: "deepseek", ModelID: "v4"}},
		{Kind: event.EventUnknown, Payload: event.UnknownPayload{Type: "custom.event", Summary: "test"}},
	}
	for _, evt := range events {
		if err := p.PresentEvent(ctx, evt); err != nil {
			t.Fatalf("PresentEvent(%s) error = %v", evt.Kind, err)
		}
	}
	if err := p.PresentError(ctx, &transport.HTTPError{StatusCode: 500, Endpoint: "/event", Summary: "boom"}); err != nil {
		t.Fatalf("PresentError() error = %v", err)
	}

	got := out.String()
	if strings.Contains(got, "\x1b[") {
		t.Fatalf("non-TTY output = %q, want no ANSI", got)
	}
	if !strings.Contains(got, "[..] bash") {
		t.Fatalf("non-TTY output = %q, want tool line with running state", got)
	}
	if !strings.Contains(got, "[agent] switched to Coder") {
		t.Fatalf("non-TTY output = %q, want readable agent line", got)
	}
	if !strings.Contains(got, "[model] switched to deepseek/v4") {
		t.Fatalf("non-TTY output = %q, want readable model line", got)
	}
	if !strings.Contains(got, "[unknown] custom.event test") {
		t.Fatalf("non-TTY output = %q, want readable unknown line", got)
	}
	if !strings.Contains(got, "[server] http /event: status 500: boom") {
		t.Fatalf("non-TTY output = %q, want readable error line", got)
	}
}

func TestFormatDuration(t *testing.T) {
	t.Parallel()

	tests := []struct {
		seconds float64
		want    string
	}{
		{0.0001, "100µs"},
		{0.5, "500ms"},
		{1.5, "1.5s"},
		{30.0, "30.0s"},
		{90.0, "1m30s"},
		{125.7, "2m6s"},
	}
	for _, tt := range tests {
		got := formatDuration(tt.seconds)
		if got != tt.want {
			t.Errorf("formatDuration(%v) = %q, want %q", tt.seconds, got, tt.want)
		}
	}
}

func TestPresenter_LongOutputTruncation(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false})
	ctx := context.Background()

	longOutput := strings.Repeat("x", 500)
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventToolSucceeded,
		Payload: event.ToolResultPayload{CallID: "call_1", Output: longOutput},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	if strings.Contains(got, longOutput) {
		t.Fatalf("long output not truncated in presenter output")
	}
	if !strings.Contains(got, "...") {
		t.Fatalf("truncated output missing ellipsis: %q", got)
	}
}

func TestPresenter_SessionIdleSummary(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: "line"})
	ctx := context.Background()

	// StepEnded accumulates data silently (per OpenCode TUI: StepFinish produces
	// zero terminal output). Only SessionIdle outputs the summary line.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventStepEnded,
		Payload: event.StepEndedPayload{
			Cost:     0.05,
			Tokens:   event.StepTokens{Input: 100, Output: 50, Reasoning: 10},
			Duration: 2.3,
		},
	}); err != nil {
		t.Fatalf("PresentEvent(step ended) error = %v", err)
	}

	// StepEnded must produce no terminal output.
	if out.Len() != 0 {
		t.Fatalf("step ended should produce no output, got %q", out.String())
	}

	// SessionIdle outputs the accumulated summary.
	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventSessionIdle}); err != nil {
		t.Fatalf("PresentEvent(session idle) error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "2.3s") {
		t.Fatalf("session idle output = %q, want duration", got)
	}
	if !strings.Contains(got, "100 in · 50 out · 10 reasoning") {
		t.Fatalf("session idle output = %q, want token breakdown", got)
	}
	if !strings.Contains(got, "answered in") {
		t.Fatalf("session idle output = %q, want 'answered in'", got)
	}
}

func TestPresenter_SessionIdleSummaryWithoutDuration(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: "line"})
	ctx := context.Background()

	// StepEnded accumulates silently.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventStepEnded,
		Payload: event.StepEndedPayload{
			Cost:   1.0,
			Tokens: event.StepTokens{Input: 10, Output: 5, Reasoning: 2},
		},
	}); err != nil {
		t.Fatalf("PresentEvent(step ended) error = %v", err)
	}

	if out.Len() != 0 {
		t.Fatalf("step ended should produce no output, got %q", out.String())
	}

	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventSessionIdle}); err != nil {
		t.Fatalf("PresentEvent(session idle) error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "10 in · 5 out · 2 reasoning") {
		t.Fatalf("session idle without duration should contain token breakdown: %q", got)
	}
}

func TestPresenter_StepStartedNoOutput(t *testing.T) {
	t.Parallel()

	for _, style := range []string{"line", "minimal", "none"} {
		t.Run(style, func(t *testing.T) {
			var out bytes.Buffer
			p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: style})
			ctx := context.Background()

			// StepStarted must produce zero terminal output regardless of style.
			if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventStepStarted}); err != nil {
				t.Fatalf("PresentEvent(step started) error = %v", err)
			}

			if out.Len() > 0 {
				t.Fatalf("step started with style=%q should produce no output, got %q", style, out.String())
			}
		})
	}
}

func TestPresenter_SessionIdleMinimal(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: "minimal"})
	ctx := context.Background()

	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventStepEnded,
		Payload: event.StepEndedPayload{Cost: 0.1, Tokens: event.StepTokens{Input: 10, Output: 5, Reasoning: 2}, Duration: 1.5},
	}); err != nil {
		t.Fatalf("PresentEvent(step ended) error = %v", err)
	}

	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventSessionIdle}); err != nil {
		t.Fatalf("PresentEvent(session idle) error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "1.5s") {
		t.Fatalf("session idle minimal should contain duration: %q", got)
	}
	if !strings.Contains(got, "10 in · 5 out · 2 reasoning") {
		t.Fatalf("session idle minimal should contain token breakdown: %q", got)
	}
	if strings.Contains(got, "──") || strings.Contains(got, "---") {
		t.Fatalf("session idle minimal should not contain divider: %q", got)
	}
}

func TestPresenter_SessionIdleNone(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: "none"})
	ctx := context.Background()

	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventStepEnded,
		Payload: event.StepEndedPayload{Cost: 0.1, Tokens: event.StepTokens{Input: 10, Output: 5, Reasoning: 2}},
	}); err != nil {
		t.Fatalf("PresentEvent(step ended) error = %v", err)
	}

	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventSessionIdle}); err != nil {
		t.Fatalf("PresentEvent(session idle) error = %v", err)
	}

	// With step_style=none, session idle should also produce no output.
	if out.Len() > 0 {
		t.Fatalf("session idle with none style should produce no output, got %q", out.String())
	}
}

func TestPresenter_SessionIdleAccumulatesMultipleSteps(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: "line"})
	ctx := context.Background()

	// Simulate two steps worth of data.
	for _, payload := range []event.StepEndedPayload{
		{Cost: 0.05, Tokens: event.StepTokens{Input: 50, Output: 25, Reasoning: 5}, Duration: 1.0},
		{Cost: 0.03, Tokens: event.StepTokens{Input: 30, Output: 15, Reasoning: 3}, Duration: 0.5},
	} {
		if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventStepEnded, Payload: payload}); err != nil {
			t.Fatalf("PresentEvent(step ended) error = %v", err)
		}
	}

	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventSessionIdle}); err != nil {
		t.Fatalf("PresentEvent(session idle) error = %v", err)
	}

	got := out.String()
	// Accumulated tokens: in=50+30=80, out=25+15=40, reasoning=5+3=8
	if !strings.Contains(got, "80 in · 40 out · 8 reasoning") {
		t.Fatalf("session idle should show token breakdown: %q", got)
	}
	// Accumulated duration: 1.0 + 0.5 = 1.5
	if !strings.Contains(got, "1.5s") {
		t.Fatalf("session idle should accumulate duration: %q", got)
	}
}

func TestToolDisplayInfo(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name      string
		tool      string
		input     string
		wantIcon  string
		wantTitle string
		wantSub   string
	}{
		{
			name:      "bash with command and description",
			tool:      "bash",
			input:     `{"command":"ls -la","description":"List files"}`,
			wantIcon:  "$",
			wantTitle: "bash",
			wantSub:   "ls -la — List files",
		},
		{
			name:      "bash with only command",
			tool:      "bash",
			input:     `{"command":"date"}`,
			wantIcon:  "$",
			wantTitle: "bash",
			wantSub:   "date",
		},
		{
			name:      "read with filePath",
			tool:      "read",
			input:     `{"filePath":"/home/user/main.go"}`,
			wantIcon:  "📖",
			wantTitle: "read",
			wantSub:   "main.go",
		},
		{
			name:      "edit with filePath",
			tool:      "edit",
			input:     `{"filePath":"/path/to/config.go"}`,
			wantIcon:  "✎",
			wantTitle: "edit",
			wantSub:   "config.go",
		},
		{
			name:      "write with filePath",
			tool:      "write",
			input:     `{"filePath":"/tmp/hello.txt"}`,
			wantIcon:  "✎",
			wantTitle: "write",
			wantSub:   "hello.txt",
		},
		{
			name:      "task with subagent and description",
			tool:      "task",
			input:     `{"subagent_type":"plan","description":"Plan the changes"}`,
			wantIcon:  "⚙",
			wantTitle: "plan",
			wantSub:   "Plan the changes",
		},
		{
			name:      "grep with pattern",
			tool:      "grep",
			input:     `{"pattern":"NewPresenter","include":"*.go"}`,
			wantIcon:  "🔍",
			wantTitle: "grep",
			wantSub:   "NewPresenter in *.go",
		},
		{
			name:      "glob with pattern",
			tool:      "glob",
			input:     `{"pattern":"**/*.go"}`,
			wantIcon:  "🔍",
			wantTitle: "glob",
			wantSub:   "**/*.go",
		},
		{
			name:      "list with path",
			tool:      "list",
			input:     `{"path":"/home/user"}`,
			wantIcon:  "📋",
			wantTitle: "list",
			wantSub:   "user",
		},
		{
			name:      "webfetch with url",
			tool:      "webfetch",
			input:     `{"url":"https://example.com"}`,
			wantIcon:  "🌐",
			wantTitle: "webfetch",
			wantSub:   "https://example.com",
		},
		{
			name:      "websearch with query",
			tool:      "websearch",
			input:     `{"query":"golang tutorial"}`,
			wantIcon:  "🌐",
			wantTitle: "websearch",
			wantSub:   "golang tutorial",
		},
		{
			name:      "apply_patch with files",
			tool:      "apply_patch",
			input:     `{"files":["a.go","b.go"]}`,
			wantIcon:  "✎",
			wantTitle: "patch",
			wantSub:   "2 files",
		},
		{
			name:      "unknown tool falls back to generic",
			tool:      "custom_tool",
			input:     `{"key":"value"}`,
			wantIcon:  "▪",
			wantTitle: "custom_tool",
			wantSub:   `{"key":"value"}`,
		},
		{
			name:      "empty input",
			tool:      "bash",
			input:     `{}`,
			wantIcon:  "$",
			wantTitle: "bash",
			wantSub:   "",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			icon, title, subtitle := toolDisplayInfo(tt.tool, json.RawMessage(tt.input))
			if icon != tt.wantIcon {
				t.Errorf("icon = %q, want %q", icon, tt.wantIcon)
			}
			if title != tt.wantTitle {
				t.Errorf("title = %q, want %q", title, tt.wantTitle)
			}
			if subtitle != tt.wantSub {
				t.Errorf("subtitle = %q, want %q", subtitle, tt.wantSub)
			}
		})
	}
}

func TestPresenter_ToolSucceededHasCheckmark(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false})
	ctx := context.Background()

	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventToolSucceeded,
		Payload: event.ToolResultPayload{CallID: "call_1", Output: "done"},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "[OK]") {
		t.Fatalf("tool succeeded output should contain [OK]: %q", got)
	}
	if strings.Contains(got, "success") {
		t.Fatalf("tool succeeded output should not contain 'success': %q", got)
	}
}

func TestPresenter_ToolFailedHasCross(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false})
	ctx := context.Background()

	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventToolFailed,
		Payload: event.ToolResultPayload{CallID: "call_1", Error: "boom"},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "[FAIL]") {
		t.Fatalf("tool failed output should contain [FAIL]: %q", got)
	}
	if strings.Contains(got, "failed") {
		t.Fatalf("tool failed output should not contain 'failed': %q", got)
	}
}

func TestPresenter_SessionIdleHasStats(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, StepStyle: "line"})
	ctx := context.Background()

	// Accumulate data via step ended (silent).
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventStepEnded,
		Payload: event.StepEndedPayload{
			Cost:     0.0001,
			Tokens:   event.StepTokens{Input: 100, Output: 50, Reasoning: 10},
			Duration: 1.5,
		},
	}); err != nil {
		t.Fatalf("PresentEvent(step ended) error = %v", err)
	}

	if out.Len() != 0 {
		t.Fatalf("step ended should produce no output, got %q", out.String())
	}

	// SessionIdle outputs the summary.
	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventSessionIdle}); err != nil {
		t.Fatalf("PresentEvent(session idle) error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "1.5s") {
		t.Fatalf("session idle should contain duration: %q", got)
	}
	if !strings.Contains(got, "100 in · 50 out · 10 reasoning") {
		t.Fatalf("session idle should contain token breakdown: %q", got)
	}
	if !strings.Contains(got, "──") {
		t.Fatalf("session idle with line style should contain divider: %q", got)
	}
}

func TestPresenter_ContextGrouping(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, GroupContextTools: true})
	ctx := context.Background()

	// Three context tools should be buffered, not displayed individually.
	for _, tc := range []struct {
		tool  string
		input string
	}{
		{"read", `{"filePath":"/a.go"}`},
		{"read", `{"filePath":"/b.go"}`},
		{"grep", `{"pattern":"foo"}`},
	} {
		if err := p.PresentEvent(ctx, event.AppEvent{
			Kind: event.EventToolCalled,
			Payload: event.ToolCalledPayload{
				ToolName: tc.tool,
				CallID:   tc.tool + "_1",
				Input:    json.RawMessage(tc.input),
			},
		}); err != nil {
			t.Fatalf("PresentEvent() error = %v", err)
		}
	}

	// Nothing should be output yet — tools are buffered.
	if out.Len() > 0 {
		t.Fatalf("context tools should be buffered, got output: %q", out.String())
	}

	// A non-context tool triggers flush.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "bash",
			CallID:   "bash_1",
			Input:    json.RawMessage(`{"command":"ls"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	// Should contain the context group summary.
	if !strings.Contains(got, "context") {
		t.Fatalf("output should contain context group summary: %q", got)
	}
	if !strings.Contains(got, "2 reads") {
		t.Fatalf("output should contain '2 reads': %q", got)
	}
	if !strings.Contains(got, "1 search") {
		t.Fatalf("output should contain '1 search' (grep → search): %q", got)
	}
	// Context group should NOT have the generic [tool] prefix (verify format).
	if !strings.Contains(got, "[context] context  2 reads, 1 search") {
		t.Fatalf("context group format mismatch: %q", got)
	}
	// Should also contain the bash tool (which still has [tool] label for now — P3-6C).
	if !strings.Contains(got, "bash") {
		t.Fatalf("output should contain bash tool: %q", got)
	}
}

func TestPresenter_ContextGroupingFlushOnStepEnd(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, GroupContextTools: true, StepStyle: "none"})
	ctx := context.Background()

	// Context tools buffered.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "read",
			CallID:   "read_1",
			Input:    json.RawMessage(`{"filePath":"/a.go"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "glob",
			CallID:   "glob_1",
			Input:    json.RawMessage(`{"pattern":"*.go"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	if out.Len() > 0 {
		t.Fatalf("context tools should be buffered, got output: %q", out.String())
	}

	// Step end triggers flush.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventStepEnded,
		Payload: event.StepEndedPayload{Cost: 0.01, Tokens: event.StepTokens{Input: 10, Output: 5, Reasoning: 0}},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "1 read") {
		t.Fatalf("output should contain '1 read': %q", got)
	}
	if !strings.Contains(got, "1 search") {
		t.Fatalf("output should contain '1 search' (glob → search): %q", got)
	}
	// Context group should NOT have [tool] label.
	if !strings.Contains(got, "[context] context  1 read, 1 search") {
		t.Fatalf("context group format mismatch: %q", got)
	}
}

func TestPresenter_ContextGroupingResultsSuppressed(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, GroupContextTools: true})
	ctx := context.Background()

	// Call a read tool.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "read",
			CallID:   "read_1",
			Input:    json.RawMessage(`{"filePath":"/a.go"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}
	// Success result for the read tool.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventToolSucceeded,
		Payload: event.ToolResultPayload{CallID: "read_1", Output: "file content"},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	// Both the call and result should be buffered/suppressed.
	if out.Len() > 0 {
		t.Fatalf("context tool call and result should be suppressed, got: %q", out.String())
	}

	// Flush with step end.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind:    event.EventStepEnded,
		Payload: event.StepEndedPayload{},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "1 read") {
		t.Fatalf("output should contain context group: %q", got)
	}
	// Should not have [tool] label on the context line.
	if !strings.Contains(got, "[context] context  1 read") {
		t.Fatalf("context group format mismatch: %q", got)
	}
	// Should not contain the raw file content.
	if strings.Contains(got, "file content") {
		t.Fatalf("context tool result should not show raw output: %q", got)
	}
}

func TestPresenter_NoCallIDInToolDisplay(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false})
	ctx := context.Background()

	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "bash",
			CallID:   "call_00_JEpLkuJo4T5yV7aq7l166427",
			Input:    json.RawMessage(`{"command":"ls"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	if strings.Contains(got, "call=") {
		t.Fatalf("tool display should not contain call ID: %q", got)
	}
	if strings.Contains(got, "call_00") {
		t.Fatalf("tool display should not contain call ID value: %q", got)
	}
}

func TestPresenter_ContextGroupingDisabled(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false, GroupContextTools: false})
	ctx := context.Background()

	// With grouping disabled, each context tool should be displayed individually.
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "read",
			CallID:   "read_1",
			Input:    json.RawMessage(`{"filePath":"/a.go"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}
	if err := p.PresentEvent(ctx, event.AppEvent{
		Kind: event.EventToolCalled,
		Payload: event.ToolCalledPayload{
			ToolName: "glob",
			CallID:   "glob_1",
			Input:    json.RawMessage(`{"pattern":"*.go"}`),
		},
	}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}

	got := out.String()
	// Each tool should appear individually (not grouped).
	if !strings.Contains(got, "read") {
		t.Fatalf("output should contain read tool: %q", got)
	}
	if !strings.Contains(got, "glob") {
		t.Fatalf("output should contain glob tool: %q", got)
	}
	// Should NOT contain context group summary.
	if strings.Contains(got, "context") {
		t.Fatalf("output should not contain context group when disabled: %q", got)
	}
}

func assertGolden(t *testing.T, path string, got []byte) {
	t.Helper()
	if *updatePresenterGolden {
		if err := os.WriteFile(path, got, 0o644); err != nil {
			t.Fatalf("write golden %s: %v", path, err)
		}
	}
	want, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read golden %s: %v", path, err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("golden mismatch for %s\n--- got ---\n%s\n--- want ---\n%s", path, got, want)
	}
}
