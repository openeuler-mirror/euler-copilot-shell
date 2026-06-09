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
	"strconv"
	"strings"

	"charm.land/lipgloss/v2"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

const summaryLimit = 120

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
	PresentToolCalled(ctx context.Context, payload event.ToolCalledPayload) error
	PresentToolSucceeded(ctx context.Context, payload event.ToolResultPayload) error
	PresentToolFailed(ctx context.Context, payload event.ToolResultPayload) error
	PresentPermission(ctx context.Context, payload event.PermissionAskedPayload) error
	PresentQuestion(ctx context.Context, payload event.QuestionAskedPayload) error
	PresentError(ctx context.Context, err error) error
}

// Options controls presenter construction.
type Options struct {
	Writer  io.Writer
	IsTTY   bool
	NoColor bool
}

type defaultPresenter struct {
	out          io.Writer
	colorEnabled bool
	downsample   bool
	styles       styleSet
}

type styleSet struct {
	step       lipgloss.Style
	toolRun    lipgloss.Style
	toolOK     lipgloss.Style
	toolErr    lipgloss.Style
	permission lipgloss.Style
	question   lipgloss.Style
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
	return &defaultPresenter{
		out:          out,
		colorEnabled: colorEnabled,
		downsample:   colorEnabled && isFile,
		styles:       newStyleSet(colorEnabled),
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
		toolRun:    label("14"),
		toolOK:     label("10"),
		toolErr:    label("9"),
		permission: label("11"),
		question:   label("13"),
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
	default:
		return nil
	}
}

func (p *defaultPresenter) PresentStepStarted(ctx context.Context) error {
	return p.writeLabelLine(ctx, p.styles.step, "[step]", "started")
}

func (p *defaultPresenter) PresentStepEnded(ctx context.Context, payload event.StepEndedPayload) error {
	message := fmt.Sprintf(
		"finished cost=%s tokens=input:%d output:%d reasoning:%d",
		strconv.FormatFloat(payload.Cost, 'f', -1, 64),
		payload.Tokens.Input,
		payload.Tokens.Output,
		payload.Tokens.Reasoning,
	)
	return p.writeLabelLine(ctx, p.styles.step, "[step]", message)
}

func (p *defaultPresenter) PresentToolCalled(ctx context.Context, payload event.ToolCalledPayload) error {
	message := strings.TrimSpace(strings.Join([]string{
		payload.ToolName,
		formatField("call", payload.CallID),
		formatField("input", summarizeJSON(payload.Input)),
	}, " "))
	return p.writeLabelLine(ctx, p.styles.toolRun, "[tool]", message)
}

func (p *defaultPresenter) PresentToolSucceeded(ctx context.Context, payload event.ToolResultPayload) error {
	message := strings.TrimSpace(strings.Join([]string{
		"success",
		formatField("call", payload.CallID),
		formatField("output", summarizeText(payload.Output)),
	}, " "))
	return p.writeLabelLine(ctx, p.styles.toolOK, "[tool]", message)
}

func (p *defaultPresenter) PresentToolFailed(ctx context.Context, payload event.ToolResultPayload) error {
	message := strings.TrimSpace(strings.Join([]string{
		"failed",
		formatField("call", payload.CallID),
		formatField("error", summarizeText(payload.Error)),
	}, " "))
	return p.writeLabelLine(ctx, p.styles.toolErr, "[tool]", message)
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

func formatField(name, value string) string {
	if value == "" {
		return ""
	}
	return name + "=" + value
}
