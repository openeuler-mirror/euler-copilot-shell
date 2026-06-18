package permission

import (
	"context"
	"errors"
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
	ReplyPermission(ctx context.Context, requestID string, directory string, decision transport.PermissionDecision) (bool, error)
	ReplyQuestion(ctx context.Context, requestID string, directory string, answers [][]string) (bool, error)
	RejectQuestion(ctx context.Context, requestID string, directory string) (bool, error)
}

type PromptUI interface {
	ReadLine(ctx context.Context, label string) (string, error)
}

// SelectOption represents a single selectable item in an interactive list.
type SelectOption struct {
	Label       string
	Description string
	Value       string
}

// SelectPrompter is an optional interface that prompts can implement to provide
// interactive arrow-key selection. When not implemented, the permission manager
// falls back to text-based ReadLine prompts.
type SelectPrompter interface {
	Select(ctx context.Context, title string, options []SelectOption) (int, error)
}

// Manager coordinates interactive permission/question requests.
type Manager interface {
	HandleEvent(ctx context.Context, evt event.AppEvent) error
	HandlePermission(ctx context.Context, payload event.PermissionAskedPayload) error
	HandleQuestion(ctx context.Context, payload event.QuestionAskedPayload) error
	// SetDirectory updates the working directory used to scope permission
	// replies to the correct server instance.
	SetDirectory(dir string)
}

type Options struct {
	Transport Transport
	Prompt    PromptUI
	// SelectFn is an optional interactive selector for arrow-key navigation.
	// When nil, the manager falls back to text-based ReadLine prompts.
	SelectFn    func(ctx context.Context, title string, options []SelectOption) (int, error)
	Writer      io.Writer
	Interactive bool
}

type manager struct {
	transport   Transport
	prompt      PromptUI
	selectFn    func(ctx context.Context, title string, options []SelectOption) (int, error)
	out         io.Writer
	interactive bool
	directory   string
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
		selectFn:    opts.SelectFn,
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

	// Try interactive arrow-key selector first.
	if m.selectFn != nil {
		decision, err := m.selectPermission(ctx, payload)
		if err != nil {
			return err
		}
		if decision == "" {
			// User cancelled — reject.
			return m.replyPermission(ctx, payload.RequestID, transport.PermissionDecision{Reply: permissionReplyReject})
		}
		return m.replyPermission(ctx, payload.RequestID, transport.PermissionDecision{Reply: decision})
	}

	// Fallback to text-based prompt.
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

// selectPermission uses the interactive arrow-key selector for permission decisions.
func (m *manager) selectPermission(ctx context.Context, payload event.PermissionAskedPayload) (string, error) {
	title := permissionSelectTitle(payload)
	options := []SelectOption{
		{Label: "Once", Description: "Allow this time only", Value: permissionReplyOnce},
		{Label: "Always", Description: "Allow all future requests of this type", Value: permissionReplyAlways},
		{Label: "Reject", Description: "Deny this request", Value: permissionReplyReject},
	}
	idx, err := m.selectFn(ctx, title, options)
	if err != nil {
		return "", fmt.Errorf("permission selection: %w", err)
	}
	if idx < 0 || idx >= len(options) {
		return "", nil // cancelled
	}
	return options[idx].Value, nil
}

func permissionSelectTitle(payload event.PermissionAskedPayload) string {
	target := payload.Permission
	if len(payload.Patterns) > 0 {
		target = strings.TrimSpace(target + " [" + strings.Join(payload.Patterns, ", ") + "]")
	}
	if target == "" {
		target = "requested action"
	}
	return "Allow " + target + "?"
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
		var labels []string
		var reject bool
		var err error

		// Use interactive selector for questions with predefined options and no custom input.
		if m.selectFn != nil && len(question.Options) > 0 && !question.Custom {
			labels, reject, err = m.selectQuestion(ctx, index, len(payload.Questions), question)
		} else {
			if err := m.writeQuestion(ctx, index, len(payload.Questions), question); err != nil {
				return err
			}
			labels, reject, err = m.promptQuestion(ctx, question)
		}
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

// selectQuestion uses the interactive selector for a single question.
func (m *manager) selectQuestion(ctx context.Context, index, total int, question event.QuestionInfo) ([]string, bool, error) {
	title := questionSelectTitle(index, total, question)
	options := make([]SelectOption, len(question.Options)+1)
	for i, opt := range question.Options {
		options[i] = SelectOption{Label: opt.Label, Description: opt.Description, Value: opt.Label}
	}
	options[len(options)-1] = SelectOption{Label: "Reject", Description: "Refuse to answer", Value: "__reject__"}

	idx, err := m.selectFn(ctx, title, options)
	if err != nil {
		return nil, false, fmt.Errorf("question selection: %w", err)
	}
	if idx < 0 || idx >= len(options) {
		return nil, true, nil // cancelled → reject
	}
	if options[idx].Value == "__reject__" {
		return nil, true, nil
	}
	return []string{options[idx].Value}, false, nil
}

func questionSelectTitle(index, total int, question event.QuestionInfo) string {
	title := strings.TrimSpace(question.Question)
	if question.Header != "" {
		title = strings.TrimSpace(question.Header + ": " + title)
	}
	if total > 1 {
		title = fmt.Sprintf("Q%d/%d: %s", index+1, total, title)
	}
	return title
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
	ok, err := m.transport.ReplyPermission(ctx, requestID, m.directory, decision)
	if err != nil {
		var httpErr *transport.HTTPError
		if errors.As(err, &httpErr) && httpErr.StatusCode == 404 {
			return fmt.Errorf("reply permission %q: request not found (may have timed out on the server)", requestID)
		}
		return fmt.Errorf("reply permission %q: %w", requestID, err)
	}
	if !ok {
		return fmt.Errorf("reply permission %q: server rejected", requestID)
	}
	return nil
}

func (m *manager) replyQuestion(ctx context.Context, requestID string, answers [][]string) error {
	ok, err := m.transport.ReplyQuestion(ctx, requestID, m.directory, answers)
	if err != nil {
		return fmt.Errorf("reply question %q: %w", requestID, err)
	}
	if !ok {
		return fmt.Errorf("reply question %q: server returned false", requestID)
	}
	return nil
}

func (m *manager) rejectQuestion(ctx context.Context, requestID string) error {
	ok, err := m.transport.RejectQuestion(ctx, requestID, m.directory)
	if err != nil {
		return fmt.Errorf("reject question %q: %w", requestID, err)
	}
	if !ok {
		return fmt.Errorf("reject question %q: server returned false", requestID)
	}
	return nil
}

// SetDirectory stores the session directory for scoping permission replies.
func (m *manager) SetDirectory(dir string) {
	m.directory = dir
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
