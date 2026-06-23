package presenter

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/url"
	"os"
	"strings"

	"charm.land/lipgloss/v2"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

const summaryLimit = 120

// tool output constants
const (
	toolOutputMaxLines = 10
)

// tool state indicators
const (
	toolStateRunning      = "◌"
	toolStateOK           = "✓"
	toolStateErr          = "✗"
	toolStateRunningPlain = "[..]"
	toolStateOKPlain      = "[OK]"
	toolStateErrPlain     = "[FAIL]"
)

type ErrorKind string

const (
	ErrorUser    ErrorKind = "user"
	ErrorNetwork ErrorKind = "network"
	ErrorServer  ErrorKind = "server"
	ErrorSchema  ErrorKind = "schema"
)

// Presenter renders structured non-Markdown runtime events.
type Presenter interface {
	PresentEvent(ctx context.Context, evt event.AppEvent) error
	PresentStepStarted(ctx context.Context) error
	PresentStepEnded(ctx context.Context, payload event.StepEndedPayload) error
	PresentSessionIdle(ctx context.Context) error
	PresentAgentSwitched(ctx context.Context, payload event.AgentSwitchedPayload) error
	PresentModelSwitched(ctx context.Context, payload event.ModelSwitchedPayload) error
	PresentToolCalled(ctx context.Context, payload event.ToolCalledPayload) error
	PresentToolSucceeded(ctx context.Context, payload event.ToolResultPayload) error
	PresentToolFailed(ctx context.Context, payload event.ToolResultPayload) error
	PresentPermission(ctx context.Context, payload event.PermissionAskedPayload) error
	PresentQuestion(ctx context.Context, payload event.QuestionAskedPayload) error
	PresentUnknown(ctx context.Context, payload event.UnknownPayload) error
	PresentError(ctx context.Context, err error) error
}

// Options controls presenter construction.
type Options struct {
	Writer            io.Writer
	IsTTY             bool
	NoColor           bool
	StepStyle         string // "line", "minimal", "none"
	GroupContextTools bool   // group consecutive read/grep/glob/list calls
	Width             int    // terminal width, used for command word-wrapping; 0 = no wrap
}

type defaultPresenter struct {
	out          io.Writer
	isTTY        bool
	colorEnabled bool
	downsample   bool
	styles       styleSet
	stepStyle    string
	groupContext bool
	width        int
	// contextGroup accumulates consecutive read/grep/glob/list tool calls
	// for collapsed display. When a non-context tool or step boundary
	// arrives, the group is flushed.
	contextGroup []contextToolEntry
	// toolNames maps callID → toolName for result formatting.
	toolNames map[string]string
	// accumulatedCost, accumulatedTokens, accumulatedDuration aggregate
	// per-step-finish data for the final session.idle summary line.
	// StepStart/StepFinish produce zero terminal output (consistent
	// with OpenCode TUI which filters them entirely).
	accumulatedCost     float64
	accumulatedTokens   event.StepTokens
	accumulatedDuration float64
}

// contextToolEntry records a buffered context-gathering tool call.
type contextToolEntry struct {
	tool     string
	subtitle string
}

type styleSet struct {
	step       lipgloss.Style
	agent      lipgloss.Style
	model      lipgloss.Style
	toolRun    lipgloss.Style
	toolOK     lipgloss.Style
	toolErr    lipgloss.Style
	permission lipgloss.Style
	question   lipgloss.Style
	unknown    lipgloss.Style
	userErr    lipgloss.Style
	networkErr lipgloss.Style
	serverErr  lipgloss.Style
	schemaErr  lipgloss.Style
}

// NewPresenter creates a presenter suitable for ask/REPL/shared CLI flows.
func NewPresenter(opts Options) Presenter {
	out := opts.Writer
	if out == nil {
		out = io.Discard
	}
	colorEnabled := opts.IsTTY && !opts.NoColor
	_, isFile := out.(*os.File)
	stepStyle := opts.StepStyle
	if stepStyle == "" {
		stepStyle = "line"
	}
	return &defaultPresenter{
		out:          out,
		isTTY:        opts.IsTTY,
		colorEnabled: colorEnabled,
		downsample:   colorEnabled && isFile,
		styles:       newStyleSet(colorEnabled),
		stepStyle:    stepStyle,
		groupContext: opts.GroupContextTools,
		width:        opts.Width,
		toolNames:    make(map[string]string),
	}
}

func newStyleSet(colorEnabled bool) styleSet {
	if !colorEnabled {
		return styleSet{}
	}
	label := func(color string) lipgloss.Style {
		return lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color(color))
	}
	return styleSet{
		step:       label("12"),
		agent:      label("13"),
		model:      label("14"),
		toolRun:    label("14"),
		toolOK:     label("10"),
		toolErr:    label("9"),
		permission: label("11"),
		question:   label("13"),
		unknown:    label("8"),
		userErr:    label("11"),
		networkErr: label("14"),
		serverErr:  label("9"),
		schemaErr:  label("13"),
	}
}

func (p *defaultPresenter) PresentEvent(ctx context.Context, evt event.AppEvent) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	switch evt.Kind {
	case event.EventStepStarted:
		return p.PresentStepStarted(ctx)
	case event.EventStepEnded:
		payload, ok := evt.Payload.(event.StepEndedPayload)
		if !ok {
			return &SchemaError{Op: "present step ended", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentStepEnded(ctx, payload)
	case event.EventSessionIdle:
		return p.PresentSessionIdle(ctx)
	case event.EventAgentSwitched:
		payload, ok := evt.Payload.(event.AgentSwitchedPayload)
		if !ok {
			return &SchemaError{Op: "present agent switched", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentAgentSwitched(ctx, payload)
	case event.EventModelSwitched:
		payload, ok := evt.Payload.(event.ModelSwitchedPayload)
		if !ok {
			return &SchemaError{Op: "present model switched", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentModelSwitched(ctx, payload)
	case event.EventToolCalled:
		payload, ok := evt.Payload.(event.ToolCalledPayload)
		if !ok {
			return &SchemaError{Op: "present tool called", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentToolCalled(ctx, payload)
	case event.EventToolSucceeded:
		payload, ok := evt.Payload.(event.ToolResultPayload)
		if !ok {
			return &SchemaError{Op: "present tool succeeded", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentToolSucceeded(ctx, payload)
	case event.EventToolFailed:
		payload, ok := evt.Payload.(event.ToolResultPayload)
		if !ok {
			return &SchemaError{Op: "present tool failed", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentToolFailed(ctx, payload)
	case event.EventPermissionAsked:
		payload, ok := evt.Payload.(event.PermissionAskedPayload)
		if !ok {
			return &SchemaError{Op: "present permission", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentPermission(ctx, payload)
	case event.EventQuestionAsked:
		payload, ok := evt.Payload.(event.QuestionAskedPayload)
		if !ok {
			return &SchemaError{Op: "present question", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentQuestion(ctx, payload)
	case event.EventUnknown:
		payload, ok := evt.Payload.(event.UnknownPayload)
		if !ok {
			return &SchemaError{Op: "present unknown", Err: fmt.Errorf("unexpected payload %T", evt.Payload)}
		}
		return p.PresentUnknown(ctx, payload)
	default:
		return nil
	}
}

func (p *defaultPresenter) PresentStepStarted(ctx context.Context) error {
	// Flush any pending context group before starting a new step.
	// Per OpenCode TUI: StepStart produces zero terminal output.
	// It is an internal boundary used only to flush buffers.
	return p.flushContextGroup(ctx)
}

func (p *defaultPresenter) PresentStepEnded(ctx context.Context, payload event.StepEndedPayload) error {
	// Flush any pending context group before ending the step.
	// Per OpenCode TUI: StepFinish produces zero terminal output.
	// Cost/tokens/duration are accumulated for the final session.idle
	// summary line.
	if err := p.flushContextGroup(ctx); err != nil {
		return err
	}
	p.accumulatedCost += payload.Cost
	p.accumulatedTokens.Input += payload.Tokens.Input
	p.accumulatedTokens.Output += payload.Tokens.Output
	p.accumulatedTokens.Reasoning += payload.Tokens.Reasoning
	p.accumulatedDuration += payload.Duration
	return nil
}

// PresentSessionIdle outputs the final answer summary line.
// Per OpenCode: cost/tokens are per-message (AssistantMessage), not per-step.
// This is the only place step stats are rendered.
func (p *defaultPresenter) PresentSessionIdle(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	// Flush any remaining context group before the summary.
	if err := p.flushContextGroup(ctx); err != nil {
		return err
	}

	// Build stats string.
	var stats []string
	if p.accumulatedTokens.Input > 0 {
		stats = append(stats, fmt.Sprintf("%d in", p.accumulatedTokens.Input))
	}
	if p.accumulatedTokens.Output > 0 {
		stats = append(stats, fmt.Sprintf("%d out", p.accumulatedTokens.Output))
	}
	if p.accumulatedTokens.Reasoning > 0 {
		stats = append(stats, fmt.Sprintf("%d reasoning", p.accumulatedTokens.Reasoning))
	}
	if p.accumulatedDuration > 0 {
		stats = append(stats, formatDuration(p.accumulatedDuration))
	}

	switch p.stepStyle {
	case "none":
		return nil
	case "minimal":
		if len(stats) == 0 {
			return nil
		}
		line := strings.Join(stats, " · ")
		if p.colorEnabled {
			line = p.styles.unknown.Render(line)
		}
		return p.writeRawLine(line)
	default: // "line"
		if len(stats) > 0 {
			statsStr := " answered in " + strings.Join(stats, " · ") + " "
			line := strings.Repeat("─", 4) + statsStr + strings.Repeat("─", 4)
			// Pad to terminal-like width for visual consistency.
			if len(line) < 60 {
				line = strings.Repeat("─", (60-len(line))/2+4) + statsStr + strings.Repeat("─", (60-len(line))/2+4)
			}
			if p.colorEnabled {
				line = p.styles.unknown.Render(line)
			}
			return p.writeRawLine(line)
		}
		return nil
	}
}

func (p *defaultPresenter) PresentAgentSwitched(ctx context.Context, payload event.AgentSwitchedPayload) error {
	name := payload.AgentName
	if name == "" {
		name = payload.AgentID
	}
	// Don't display when the server sends empty agent info.
	if name == "" || name == "unknown" {
		return nil
	}
	return p.writeLabelLine(ctx, p.styles.agent, "[agent]", "switched to "+name)
}

func (p *defaultPresenter) PresentModelSwitched(ctx context.Context, payload event.ModelSwitchedPayload) error {
	// Don't display when the server sends empty model info.
	if payload.ModelID == "" && payload.ProviderID == "" {
		return nil
	}
	label := payload.ModelID
	if payload.ProviderID != "" {
		label = payload.ProviderID + "/" + payload.ModelID
	}
	if label == "" {
		return nil
	}
	return p.writeLabelLine(ctx, p.styles.model, "[model]", "switched to "+label)
}

func (p *defaultPresenter) PresentToolCalled(ctx context.Context, payload event.ToolCalledPayload) error {
	// todowrite is never displayed (OpenCode HIDDEN_TOOLS).
	if payload.ToolName == "todowrite" {
		return nil
	}
	// question is hidden during pending/running (OpenCode renderable() filter).
	if payload.ToolName == "question" {
		return nil
	}

	// Track callID → toolName + input for result formatting.
	if payload.CallID != "" {
		p.toolNames[payload.CallID] = payload.ToolName
	}

	icon, title, subtitle := toolDisplayInfo(payload.ToolName, payload.Input, !p.isTTY)

	// If context grouping is enabled and this is a context tool, buffer it.
	if p.groupContext && isContextTool(payload.ToolName) {
		p.contextGroup = append(p.contextGroup, contextToolEntry{tool: title, subtitle: subtitle})
		return nil
	}

	// Flush any pending context group before showing a non-context tool.
	if err := p.flushContextGroup(ctx); err != nil {
		return err
	}

	// Bash: show command on indented line below the running indicator.
	if payload.ToolName == "bash" {
		cmd := extractBashCommand(payload.Input)
		// Running line: "◌ bash" (without leading $, since command has its own $ prefix).
		if err := p.presentToolLine(ctx, p.styles.toolRun, toolStateIndicator(payload.ToolName, p.colorEnabled, "running"), "", "bash", ""); err != nil {
			return err
		}
		// Command on indented line with code-like styling.
		if cmd != "" {
			return p.writeBashCommand(ctx, cmd)
		}
		return nil
	}

	return p.presentToolLine(ctx, p.styles.toolRun, toolStateIndicator(payload.ToolName, p.colorEnabled, "running"), icon, title, subtitle)
}

func (p *defaultPresenter) PresentToolSucceeded(ctx context.Context, payload event.ToolResultPayload) error {
	toolName := p.toolNames[payload.CallID]
	// If this is a context tool result and grouping is on, don't show individual result.
	if p.groupContext && isContextTool(toolName) {
		return nil
	}
	// todowrite never displayed.
	if toolName == "todowrite" {
		return nil
	}
	// Flush any pending context group.
	if err := p.flushContextGroup(ctx); err != nil {
		return err
	}

	_, title, _ := toolDisplayInfo(toolName, nil)

	// Bash: output is shown below indented; don't repeat it inline.
	if toolName == "bash" {
		msg := formatToolResult(toolStateIndicator(toolName, p.colorEnabled, "completed"), title, "", "")
		if err := p.writeToolLine(ctx, p.styles.toolOK, msg); err != nil {
			return err
		}
		if payload.Output != "" {
			return p.writeToolOutput(ctx, payload.Output)
		}
		return nil
	}

	// Non-bash tools: show output inline (typically short).
	msg := formatToolResult(toolStateIndicator(toolName, p.colorEnabled, "completed"), title, payload.Output, "")
	return p.writeToolLine(ctx, p.styles.toolOK, msg)
}

func (p *defaultPresenter) PresentToolFailed(ctx context.Context, payload event.ToolResultPayload) error {
	toolName := p.toolNames[payload.CallID]
	// If this is a context tool result and grouping is on, don't show individual result.
	if p.groupContext && isContextTool(toolName) {
		return nil
	}
	// todowrite never displayed.
	if toolName == "todowrite" {
		return nil
	}
	// Flush any pending context group.
	if err := p.flushContextGroup(ctx); err != nil {
		return err
	}

	_, title, _ := toolDisplayInfo(toolName, nil)
	msg := formatToolResult(toolStateIndicator(toolName, p.colorEnabled, "error"), title, "", payload.Error)
	return p.writeToolLine(ctx, p.styles.toolErr, msg)
}

// presentToolLine outputs a tool running line: "◌ icon title subtitle" without [tool] label.
func (p *defaultPresenter) presentToolLine(ctx context.Context, style lipgloss.Style, state, icon, title, subtitle string) error {
	msg := formatToolLine(icon, title, subtitle)
	if state != "" {
		msg = state + " " + msg
	}
	return p.writeToolLine(ctx, style, msg)
}

// writeToolLine writes a tool display line without a bracket label prefix.
func (p *defaultPresenter) writeToolLine(ctx context.Context, style lipgloss.Style, message string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if p.colorEnabled {
		message = style.Render(message)
	}
	if p.colorEnabled && p.downsample {
		if _, err := lipgloss.Fprintln(p.out, message); err != nil {
			return fmt.Errorf("write tool line: %w", err)
		}
		return nil
	}
	if _, err := fmt.Fprintln(p.out, message); err != nil {
		return fmt.Errorf("write tool line: %w", err)
	}
	return nil
}

// extractBashCommand pulls the shell command from a bash tool's JSON input.
func extractBashCommand(input json.RawMessage) string {
	var v struct {
		Command string `json:"command"`
	}
	if json.Unmarshal(input, &v) == nil && v.Command != "" {
		return strings.TrimSpace(v.Command)
	}
	return ""
}

// writeBashCommand outputs the shell command with code-like styling.
// First line gets "│ $ ", continuation lines get "│   ".
func (p *defaultPresenter) writeBashCommand(ctx context.Context, command string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if command == "" {
		return nil
	}
	return p.writeIndentedLines(ctx, p.styles.unknown, "$ ", strings.Split(command, "\n"))
}

// writeToolOutput writes indented tool output (e.g. bash stdout), truncated
// to toolOutputMaxLines. Output uses dimmed styling to distinguish it from
// the final answer text.
func (p *defaultPresenter) writeToolOutput(ctx context.Context, output string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if output == "" {
		return nil
	}

	lines := strings.Split(strings.TrimRight(output, "\n"), "\n")
	truncated := false
	totalLines := len(lines)
	if len(lines) > toolOutputMaxLines {
		lines = lines[:toolOutputMaxLines]
		truncated = true
	}

	if err := p.writeIndentedLines(ctx, p.styles.unknown, "", lines); err != nil {
		return err
	}

	if truncated {
		msg := fmt.Sprintf("... (%d total lines, showing first %d)", totalLines, toolOutputMaxLines)
		return p.writeIndentedLines(ctx, p.styles.unknown, "", []string{msg})
	}
	return nil
}

// writeIndentedLines prefixes every line with "│ " (TTY) or "  | " (non-TTY),
// applies the given lipgloss style, and writes to output. When leadPrefix is
// non-empty, the first line additionally gets that prefix (e.g. "$ " for
// bash commands). When width > 0, long lines are word-wrapped so every
// visual row carries the border prefix.
func (p *defaultPresenter) writeIndentedLines(ctx context.Context, style lipgloss.Style, leadPrefix string, lines []string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	prefix := "│ "
	contPrefix := "│   "
	if !p.colorEnabled {
		prefix = "  | "
		contPrefix = "  |   "
	}

	// How much space is left for content on each row.
	contentWidth := p.width - len(prefix)
	if contentWidth < 20 {
		contentWidth = 80 // fallback
	}

	firstLine := true
	for _, line := range lines {
		rows := p.wrapLine(line, contentWidth)
		for _, row := range rows {
			var formatted string
			if firstLine && leadPrefix != "" {
				formatted = prefix + leadPrefix + row
			} else if firstLine {
				formatted = prefix + row
			} else {
				// Continuation row or subsequent line: indent to align after border.
				formatted = contPrefix + row
			}
			firstLine = false
			if p.colorEnabled {
				formatted = style.Render(formatted)
			}
			if err := p.writeRawLine(formatted); err != nil {
				return err
			}
		}
	}
	return nil
}

// wrapLine splits a single line into rows that each fit within maxWidth.
// If maxWidth <= 0, the line is returned as-is.
func (p *defaultPresenter) wrapLine(line string, maxWidth int) []string {
	if maxWidth <= 0 || len(line) <= maxWidth {
		return []string{line}
	}
	var rows []string
	remaining := line
	for len(remaining) > maxWidth {
		// Try to break at a space.
		cut := maxWidth
		for cut > maxWidth/2 && remaining[cut] != ' ' {
			cut--
		}
		if cut <= maxWidth/2 {
			cut = maxWidth // hard break if no space found
		}
		rows = append(rows, remaining[:cut])
		// Skip leading space on next row.
		if cut < len(remaining) && remaining[cut] == ' ' {
			cut++
		}
		remaining = remaining[cut:]
	}
	if len(remaining) > 0 {
		rows = append(rows, remaining)
	}
	return rows
}

func (p *defaultPresenter) PresentPermission(ctx context.Context, payload event.PermissionAskedPayload) error {
	messageParts := []string{payload.Permission}
	if len(payload.Patterns) > 0 {
		messageParts = append(messageParts, formatField("patterns", strings.Join(payload.Patterns, ",")))
	}
	if payload.RequestID != "" {
		messageParts = append(messageParts, formatField("request", payload.RequestID))
	}
	return p.writeLabelLine(ctx, p.styles.permission, "[permission]", strings.Join(messageParts, " "))
}

func (p *defaultPresenter) PresentQuestion(ctx context.Context, payload event.QuestionAskedPayload) error {
	message := summarizeQuestions(payload.Questions)
	if payload.RequestID != "" {
		message = strings.TrimSpace(strings.Join([]string{message, formatField("request", payload.RequestID)}, " "))
	}
	return p.writeLabelLine(ctx, p.styles.question, "[question]", message)
}

func (p *defaultPresenter) PresentUnknown(ctx context.Context, payload event.UnknownPayload) error {
	message := payload.Type
	if payload.Summary != "" {
		message += " " + payload.Summary
	}
	return p.writeLabelLine(ctx, p.styles.unknown, "[unknown]", summarizeText(message))
}

func (p *defaultPresenter) PresentError(ctx context.Context, err error) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	info := classifyError(err)
	return p.writeLabelLine(ctx, p.styleForError(info.Kind), fmt.Sprintf("[%s]", info.Kind), info.Message)
}

func (p *defaultPresenter) writeLabelLine(ctx context.Context, style lipgloss.Style, label, message string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	line := label
	if p.colorEnabled {
		line = style.Render(label)
	}
	if message != "" {
		line += " " + message
	}
	if p.colorEnabled && p.downsample {
		if _, err := lipgloss.Fprintln(p.out, line); err != nil {
			return fmt.Errorf("write presenter line: %w", err)
		}
		return nil
	}
	if _, err := fmt.Fprintln(p.out, line); err != nil {
		return fmt.Errorf("write presenter line: %w", err)
	}
	return nil
}

// writeContextLine writes a line without a bracket label prefix.
// Used for context group summaries and other icon-led messages that
// do not need a [tool]/[agent]/etc. prefix.
func (p *defaultPresenter) writeContextLine(ctx context.Context, message string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if p.colorEnabled {
		message = p.styles.unknown.Render(message)
	}
	if p.colorEnabled && p.downsample {
		if _, err := lipgloss.Fprintln(p.out, message); err != nil {
			return fmt.Errorf("write context line: %w", err)
		}
		return nil
	}
	if _, err := fmt.Fprintln(p.out, message); err != nil {
		return fmt.Errorf("write context line: %w", err)
	}
	return nil
}

// writeRawLine writes a pre-formatted line to the output.
func (p *defaultPresenter) writeRawLine(line string) error {
	if p.colorEnabled && p.downsample {
		if _, err := lipgloss.Fprintln(p.out, line); err != nil {
			return fmt.Errorf("write presenter line: %w", err)
		}
		return nil
	}
	if _, err := fmt.Fprintln(p.out, line); err != nil {
		return fmt.Errorf("write presenter line: %w", err)
	}
	return nil
}

// isContextTool reports whether a tool is a context-gathering tool
// (read, grep, glob, list) that should be grouped for collapsed display.
func isContextTool(toolName string) bool {
	switch toolName {
	case "read", "grep", "glob", "list":
		return true
	}
	return false
}

// flushContextGroup writes any buffered context-gathering tool calls as a
// single collapsed summary line, then clears the buffer.
// The summary uses a clean icon prefix without the generic [tool] label,
// giving context tools a distinct visual identity from action tools.
func (p *defaultPresenter) flushContextGroup(ctx context.Context) error {
	if len(p.contextGroup) == 0 {
		return nil
	}
	if err := ctx.Err(); err != nil {
		return err
	}

	// Count by category (not raw tool name). grep + glob are both "searches".
	var reads, searches, lists int
	for _, entry := range p.contextGroup {
		switch entry.tool {
		case "read":
			reads++
		case "grep", "glob":
			searches++
		case "list":
			lists++
		}
	}

	// Build summary: "3 reads, 2 searches, 1 list"
	var parts []string
	if reads > 0 {
		parts = append(parts, fmt.Sprintf("%d read%s", reads, pluralS(reads)))
	}
	if searches > 0 {
		parts = append(parts, fmt.Sprintf("%d search%s", searches, searchPlural(searches)))
	}
	if lists > 0 {
		parts = append(parts, fmt.Sprintf("%d list%s", lists, pluralS(lists)))
	}

	summary := strings.Join(parts, ", ")
	// Non-TTY: use ASCII alternative for the context icon.
	icon := "🔍"
	if !p.isTTY {
		icon = "[context]"
	}
	message := icon + " context  " + summary
	p.contextGroup = nil

	// Output without the generic [tool] label — the icon already signals
	// this is a context tools summary.
	return p.writeContextLine(ctx, message)
}

func (p *defaultPresenter) styleForError(kind ErrorKind) lipgloss.Style {
	switch kind {
	case ErrorNetwork:
		return p.styles.networkErr
	case ErrorServer:
		return p.styles.serverErr
	case ErrorSchema:
		return p.styles.schemaErr
	default:
		return p.styles.userErr
	}
}

type errorInfo struct {
	Kind    ErrorKind
	Message string
}

func classifyError(err error) errorInfo {
	if err == nil {
		return errorInfo{Kind: ErrorUser, Message: "unknown error"}
	}

	var schemaErr *SchemaError
	if errors.As(err, &schemaErr) {
		return errorInfo{Kind: ErrorSchema, Message: schemaErr.Error()}
	}
	var userErr *UserError
	if errors.As(err, &userErr) {
		return errorInfo{Kind: ErrorUser, Message: userErr.Error()}
	}
	var httpErr *transport.HTTPError
	if errors.As(err, &httpErr) {
		kind := ErrorUser
		if httpErr.StatusCode >= 500 {
			kind = ErrorServer
		}
		return errorInfo{Kind: kind, Message: httpErr.Error()}
	}
	if errors.Is(err, context.Canceled) {
		return errorInfo{Kind: ErrorUser, Message: err.Error()}
	}
	if errors.Is(err, context.DeadlineExceeded) || isNetworkError(err) {
		return errorInfo{Kind: ErrorNetwork, Message: err.Error()}
	}
	return errorInfo{Kind: ErrorUser, Message: err.Error()}
}

func isNetworkError(err error) bool {
	var netErr net.Error
	if errors.As(err, &netErr) {
		return true
	}
	var urlErr *url.Error
	if errors.As(err, &urlErr) {
		return true
	}
	var opErr *net.OpError
	return errors.As(err, &opErr)
}

func summarizeQuestions(questions []event.QuestionInfo) string {
	parts := make([]string, 0, len(questions))
	for _, question := range questions {
		chunk := question.Question
		if question.Header != "" {
			chunk = strings.TrimSpace(question.Header + ": " + question.Question)
		}
		options := summarizeOptions(question.Options)
		if options != "" {
			chunk = strings.TrimSpace(chunk + " " + formatField("options", options))
		}
		if question.Multiple {
			chunk = strings.TrimSpace(chunk + " multiple=true")
		}
		if question.Custom {
			chunk = strings.TrimSpace(chunk + " custom=true")
		}
		parts = append(parts, summarizeText(chunk))
	}
	return strings.Join(parts, " | ")
}

func summarizeOptions(options []event.QuestionOption) string {
	parts := make([]string, 0, len(options))
	for _, option := range options {
		chunk := option.Label
		if option.Description != "" {
			chunk += " (" + summarizeText(option.Description) + ")"
		}
		parts = append(parts, chunk)
	}
	return strings.Join(parts, ", ")
}

func summarizeJSON(raw json.RawMessage) string {
	if len(raw) == 0 {
		return ""
	}
	var compact bytes.Buffer
	if err := json.Compact(&compact, raw); err == nil {
		return trimSummary(compact.String())
	}
	return trimSummary(string(raw))
}

func summarizeText(text string) string {
	return trimSummary(text)
}

func trimSummary(text string) string {
	text = strings.TrimSpace(strings.ReplaceAll(text, "\n", " "))
	for strings.Contains(text, "  ") {
		text = strings.ReplaceAll(text, "  ", " ")
	}
	if len(text) > summaryLimit {
		return text[:summaryLimit] + "..."
	}
	return text
}

// toolDisplayInfo extracts the icon, title, and subtitle for a tool call
// based on the tool type and its JSON input. This mirrors OpenCode's per-tool
// rendering strategy where each tool type has a human-readable title and
// a subtitle extracted from the tool's input parameters.
func toolDisplayInfo(toolName string, input json.RawMessage, asciiIcons ...bool) (icon, title, subtitle string) {
	ascii := len(asciiIcons) > 0 && asciiIcons[0]
	switch toolName {
	case "bash":
		icon = "$"
		title = "bash"
		var v struct {
			Command     string `json:"command"`
			Description string `json:"description"`
		}
		if json.Unmarshal(input, &v) == nil {
			if v.Command != "" {
				subtitle = trimSummary(v.Command)
			}
			if v.Description != "" {
				if subtitle != "" {
					subtitle += " — " + trimSummary(v.Description)
				} else {
					subtitle = trimSummary(v.Description)
				}
			}
		}
	case "read":
		icon = "📖"
		title = "read"
		var v struct {
			FilePath string `json:"filePath"`
		}
		if json.Unmarshal(input, &v) == nil && v.FilePath != "" {
			subtitle = baseName(v.FilePath)
		}
	case "edit":
		icon = "✎"
		title = "edit"
		var v struct {
			FilePath  string `json:"filePath"`
			OldString string `json:"oldString"`
			NewString string `json:"newString"`
		}
		if json.Unmarshal(input, &v) == nil && v.FilePath != "" {
			subtitle = baseName(v.FilePath)
		}
	case "write":
		icon = "✎"
		title = "write"
		var v struct {
			FilePath string `json:"filePath"`
		}
		if json.Unmarshal(input, &v) == nil && v.FilePath != "" {
			subtitle = baseName(v.FilePath)
		}
	case "task":
		icon = "⚙"
		title = "task"
		var v struct {
			Description string `json:"description"`
			SubAgent    string `json:"subagent_type"`
		}
		if json.Unmarshal(input, &v) == nil {
			if v.SubAgent != "" {
				title = v.SubAgent
			}
			if v.Description != "" {
				subtitle = trimSummary(v.Description)
			}
		}
	case "grep":
		icon = "🔍"
		title = "grep"
		var v struct {
			Pattern string `json:"pattern"`
			Include string `json:"include"`
		}
		if json.Unmarshal(input, &v) == nil {
			if v.Pattern != "" {
				subtitle = trimSummary(v.Pattern)
			}
			if v.Include != "" {
				if subtitle != "" {
					subtitle += " in " + v.Include
				} else {
					subtitle = "in " + v.Include
				}
			}
		}
	case "glob":
		icon = "🔍"
		title = "glob"
		var v struct {
			Pattern string `json:"pattern"`
		}
		if json.Unmarshal(input, &v) == nil && v.Pattern != "" {
			subtitle = trimSummary(v.Pattern)
		}
	case "list":
		icon = "📋"
		title = "list"
		var v struct {
			Path string `json:"path"`
		}
		if json.Unmarshal(input, &v) == nil && v.Path != "" {
			subtitle = baseName(v.Path)
		}
	case "webfetch":
		icon = "🌐"
		title = "webfetch"
		var v struct {
			URL string `json:"url"`
		}
		if json.Unmarshal(input, &v) == nil && v.URL != "" {
			subtitle = trimSummary(v.URL)
		}
	case "websearch":
		icon = "🌐"
		title = "websearch"
		var v struct {
			Query string `json:"query"`
		}
		if json.Unmarshal(input, &v) == nil && v.Query != "" {
			subtitle = trimSummary(v.Query)
		}
	case "apply_patch":
		icon = "✎"
		title = "patch"
		var v struct {
			Files []string `json:"files"`
		}
		if json.Unmarshal(input, &v) == nil && len(v.Files) > 0 {
			subtitle = fmt.Sprintf("%d file%s", len(v.Files), pluralS(len(v.Files)))
		}
	default:
		icon = "▪"
		title = toolName
		subtitle = summarizeJSON(input)
	}
	// Non-TTY: downgrade Unicode icons to ASCII equivalents.
	if ascii {
		icon = toolIconASCII(icon, title)
	}
	return icon, title, subtitle
}

// toolStateIndicator returns the display character or string for a tool's
// execution state. Uses Unicode icons on TTY and plain ASCII on non-TTY.
func toolStateIndicator(toolName string, colorEnabled bool, status string) string {
	switch status {
	case "running":
		if colorEnabled {
			return toolStateRunning
		}
		return toolStateRunningPlain
	case "completed":
		if colorEnabled {
			return toolStateOK
		}
		return toolStateOKPlain
	case "error":
		if colorEnabled {
			return toolStateErr
		}
		return toolStateErrPlain
	default:
		return ""
	}
}

// toolIconASCII returns an ASCII-safe icon for non-TTY output.
// Falls back to the title name in brackets when no mapping exists.
func toolIconASCII(icon, toolName string) string {
	switch icon {
	case "📖":
		return "[read]"
	case "✎":
		return "[write]"
	case "⚙":
		return "[task]"
	case "🔍":
		return "[search]"
	case "📋":
		return "[list]"
	case "🌐":
		return "[web]"
	case "🧠":
		return "[skill]"
	case "$":
		return "$"
	case "▪":
		return "[" + toolName + "]"
	default:
		return "[" + toolName + "]"
	}
}

// formatToolLine assembles the display string for a tool call.
// Format: "{icon} {title} {subtitle}"
func formatToolLine(icon, title, subtitle string) string {
	parts := []string{icon, title}
	if subtitle != "" {
		parts = append(parts, subtitle)
	}
	return strings.TrimSpace(strings.Join(parts, " "))
}

// formatToolResult assembles the display string for a tool result.
// Format: "{icon} {toolName} {detail}"
func formatToolResult(icon, toolName, output, errMsg string) string {
	parts := []string{icon}
	if toolName != "" {
		parts = append(parts, toolName)
	}
	if output != "" {
		parts = append(parts, summarizeText(output))
	}
	if errMsg != "" {
		parts = append(parts, summarizeText(errMsg))
	}
	return strings.TrimSpace(strings.Join(parts, " "))
}

// baseName extracts the filename from a path.
func baseName(path string) string {
	if path == "" {
		return ""
	}
	idx := strings.LastIndex(path, "/")
	if idx >= 0 {
		return path[idx+1:]
	}
	return path
}

// pluralS returns "s" for n != 1, "" for n == 1.
func pluralS(n int) string {
	if n == 1 {
		return ""
	}
	return "s"
}

// searchPlural returns "es" for n != 1, "" for n == 1.
// Used for words ending with "ch" where regular plural would be "es".
func searchPlural(n int) string {
	if n == 1 {
		return ""
	}
	return "es"
}

func formatField(name, value string) string {
	if value == "" {
		return ""
	}
	return name + "=" + value
}

func formatDuration(seconds float64) string {
	if seconds < 0.001 {
		return fmt.Sprintf("%.0fµs", seconds*1e6)
	}
	if seconds < 1 {
		return fmt.Sprintf("%.0fms", seconds*1e3)
	}
	if seconds < 60 {
		return fmt.Sprintf("%.1fs", seconds)
	}
	minutes := int(seconds / 60)
	secs := seconds - float64(minutes*60)
	return fmt.Sprintf("%dm%.0fs", minutes, secs)
}
