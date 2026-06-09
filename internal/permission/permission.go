package permission

import (
	"context"
	"fmt"
	"io"
	"strconv"
	"strings"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

const (
	permissionReplyOnce   = "once"
	permissionReplyAlways = "always"
	permissionReplyReject = "reject"
)

type Transport interface {
	ReplyPermission(ctx context.Context, requestID string, decision transport.PermissionDecision) (bool, error)
	ReplyQuestion(ctx context.Context, requestID string, answers [][]string) (bool, error)
	RejectQuestion(ctx context.Context, requestID string) (bool, error)
}

type PromptUI interface {
	ReadLine(ctx context.Context, label string) (string, error)
}

// Manager coordinates interactive permission/question requests.
type Manager interface {
	HandleEvent(ctx context.Context, evt event.AppEvent) error
	HandlePermission(ctx context.Context, payload event.PermissionAskedPayload) error
	HandleQuestion(ctx context.Context, payload event.QuestionAskedPayload) error
}

type Options struct {
	Transport   Transport
	Prompt      PromptUI
	Writer      io.Writer
	Interactive bool
}

type manager struct {
	transport   Transport
	prompt      PromptUI
	out         io.Writer
	interactive bool
}

func NewManager(opts Options) (Manager, error) {
	if opts.Transport == nil {
		return nil, fmt.Errorf("permission transport is required")
	}
	if opts.Interactive && opts.Prompt == nil {
		return nil, fmt.Errorf("permission prompt is required when interactive")
	}
	out := opts.Writer
	if out == nil {
		out = io.Discard
	}
	return &manager{
		transport:   opts.Transport,
		prompt:      opts.Prompt,
		out:         out,
		interactive: opts.Interactive,
	}, nil
}

func (m *manager) HandleEvent(ctx context.Context, evt event.AppEvent) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	switch evt.Kind {
	case event.EventPermissionAsked:
		payload, ok := evt.Payload.(event.PermissionAskedPayload)
		if !ok {
			return fmt.Errorf("handle permission event: unexpected payload %T", evt.Payload)
		}
		return m.HandlePermission(ctx, payload)
	case event.EventQuestionAsked:
		payload, ok := evt.Payload.(event.QuestionAskedPayload)
		if !ok {
			return fmt.Errorf("handle question event: unexpected payload %T", evt.Payload)
		}
		return m.HandleQuestion(ctx, payload)
	default:
		return fmt.Errorf("handle interaction event: unsupported kind %q", evt.Kind)
	}
}

func (m *manager) HandlePermission(ctx context.Context, payload event.PermissionAskedPayload) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if payload.RequestID == "" {
		return fmt.Errorf("permission request id is required")
	}

	if !m.interactive {
		if err := m.writeLine(ctx, fmt.Sprintf("[permission] non-interactive mode: rejecting request %s", payload.RequestID)); err != nil {
			return err
		}
		return m.replyPermission(ctx, payload.RequestID, transport.PermissionDecision{Reply: permissionReplyReject})
	}

	for {
		answer, err := m.prompt.ReadLine(ctx, permissionPrompt(payload))
		if err != nil {
			return fmt.Errorf("prompt permission %q: %w", payload.RequestID, err)
		}
		decision, ok := parsePermissionDecision(answer)
		if !ok {
			if err := m.writeLine(ctx, "invalid response, enter once, always, or reject"); err != nil {
				return err
			}
			continue
		}
		return m.replyPermission(ctx, payload.RequestID, transport.PermissionDecision{Reply: decision})
	}
}

func (m *manager) HandleQuestion(ctx context.Context, payload event.QuestionAskedPayload) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if payload.RequestID == "" {
		return fmt.Errorf("question request id is required")
	}
	if len(payload.Questions) == 0 {
		return fmt.Errorf("question request %q has no questions", payload.RequestID)
	}

	if !m.interactive {
		if err := m.writeLine(ctx, fmt.Sprintf("[question] non-interactive mode: rejecting request %s", payload.RequestID)); err != nil {
			return err
		}
		return m.rejectQuestion(ctx, payload.RequestID)
	}

	answers := make([][]string, 0, len(payload.Questions))
	for index, question := range payload.Questions {
		if err := m.writeQuestion(ctx, index, len(payload.Questions), question); err != nil {
			return err
		}
		labels, reject, err := m.promptQuestion(ctx, question)
		if err != nil {
			return fmt.Errorf("prompt question %q: %w", payload.RequestID, err)
		}
		if reject {
			return m.rejectQuestion(ctx, payload.RequestID)
		}
		answers = append(answers, labels)
	}

	return m.replyQuestion(ctx, payload.RequestID, answers)
}

func (m *manager) promptQuestion(ctx context.Context, question event.QuestionInfo) ([]string, bool, error) {
	for {
		answer, err := m.prompt.ReadLine(ctx, questionPromptLabel(question))
		if err != nil {
			return nil, false, err
		}
		labels, reject, err := parseQuestionAnswer(answer, question)
		if err != nil {
			if err := m.writeLine(ctx, "invalid answer: "+err.Error()); err != nil {
				return nil, false, err
			}
			continue
		}
		return labels, reject, nil
	}
}

func (m *manager) writeQuestion(ctx context.Context, index, total int, question event.QuestionInfo) error {
	title := strings.TrimSpace(question.Question)
	if question.Header != "" {
		title = strings.TrimSpace(question.Header + ": " + title)
	}
	if title == "" {
		title = "question"
	}
	if total > 1 {
		title = fmt.Sprintf("question %d/%d: %s", index+1, total, title)
	} else {
		title = "question: " + title
	}
	if err := m.writeLine(ctx, title); err != nil {
		return err
	}
	for optionIndex, option := range question.Options {
		line := fmt.Sprintf("  %d) %s", optionIndex+1, option.Label)
		if option.Description != "" {
			line += " — " + option.Description
		}
		if err := m.writeLine(ctx, line); err != nil {
			return err
		}
	}
	return m.writeLine(ctx, questionHint(question))
}

func (m *manager) writeLine(ctx context.Context, line string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if _, err := fmt.Fprintln(m.out, line); err != nil {
		return fmt.Errorf("write interaction prompt: %w", err)
	}
	return nil
}

func (m *manager) replyPermission(ctx context.Context, requestID string, decision transport.PermissionDecision) error {
	ok, err := m.transport.ReplyPermission(ctx, requestID, decision)
	if err != nil {
		return fmt.Errorf("reply permission %q: %w", requestID, err)
	}
	if !ok {
		return fmt.Errorf("reply permission %q: server returned false", requestID)
	}
	return nil
}

func (m *manager) replyQuestion(ctx context.Context, requestID string, answers [][]string) error {
	ok, err := m.transport.ReplyQuestion(ctx, requestID, answers)
	if err != nil {
		return fmt.Errorf("reply question %q: %w", requestID, err)
	}
	if !ok {
		return fmt.Errorf("reply question %q: server returned false", requestID)
	}
	return nil
}

func (m *manager) rejectQuestion(ctx context.Context, requestID string) error {
	ok, err := m.transport.RejectQuestion(ctx, requestID)
	if err != nil {
		return fmt.Errorf("reject question %q: %w", requestID, err)
	}
	if !ok {
		return fmt.Errorf("reject question %q: server returned false", requestID)
	}
	return nil
}

func permissionPrompt(payload event.PermissionAskedPayload) string {
	target := payload.Permission
	if len(payload.Patterns) > 0 {
		target = strings.TrimSpace(target + " [" + strings.Join(payload.Patterns, ", ") + "]")
	}
	if target == "" {
		target = "requested action"
	}
	return fmt.Sprintf("allow %s? [o]nce/[a]lways/[r]eject: ", target)
}

func parsePermissionDecision(input string) (string, bool) {
	switch strings.ToLower(strings.TrimSpace(input)) {
	case "1", "o", "once":
		return permissionReplyOnce, true
	case "2", "a", "always":
		return permissionReplyAlways, true
	case "3", "r", "reject":
		return permissionReplyReject, true
	default:
		return "", false
	}
}

func questionPromptLabel(question event.QuestionInfo) string {
	if question.Multiple {
		return "answers> "
	}
	return "answer> "
}

func questionHint(question event.QuestionInfo) string {
	instruction := "  enter one option number or label"
	if question.Multiple {
		instruction = "  enter one or more comma-separated option numbers or labels"
	}
	if question.Custom {
		instruction += "; custom answers allowed"
	}
	instruction += "; type 'reject' to refuse"
	return instruction
}

func parseQuestionAnswer(input string, question event.QuestionInfo) ([]string, bool, error) {
	trimmed := strings.TrimSpace(input)
	if trimmed == "" {
		return nil, false, fmt.Errorf("answer is required")
	}
	if isRejectInput(trimmed) {
		return nil, true, nil
	}

	tokens := []string{trimmed}
	if question.Multiple {
		tokens = strings.Split(trimmed, ",")
	}

	labels := make([]string, 0, len(tokens))
	seen := make(map[string]struct{}, len(tokens))
	for _, token := range tokens {
		token = strings.TrimSpace(token)
		if token == "" {
			continue
		}
		label, ok := resolveQuestionOption(token, question.Options)
		if !ok {
			if !question.Custom {
				return nil, false, fmt.Errorf("unknown option %q", token)
			}
			label = token
		}
		key := strings.ToLower(label)
		if _, exists := seen[key]; exists {
			continue
		}
		seen[key] = struct{}{}
		labels = append(labels, label)
	}
	if len(labels) == 0 {
		return nil, false, fmt.Errorf("answer is required")
	}
	if !question.Multiple && len(labels) > 1 {
		return nil, false, fmt.Errorf("only one answer is allowed")
	}
	return labels, false, nil
}

func resolveQuestionOption(token string, options []event.QuestionOption) (string, bool) {
	if index, err := strconv.Atoi(token); err == nil {
		if index >= 1 && index <= len(options) {
			return options[index-1].Label, true
		}
	}
	for _, option := range options {
		if strings.EqualFold(token, option.Label) {
			return option.Label, true
		}
	}
	return "", false
}

func isRejectInput(input string) bool {
	switch strings.ToLower(strings.TrimSpace(input)) {
	case "r", "reject", "cancel":
		return true
	default:
		return false
	}
}
