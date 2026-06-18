package event

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net"
	"net/url"
	"strings"
	"time"

	"atomgit.com/openeuler/witty-cli/internal/transport"
)

const (
	// maxSSERetries is the maximum number of reconnection attempts.
	maxSSERetries = 3
	// sseBackoffBase is the initial backoff duration for SSE reconnection.
	sseBackoffBase = 1 * time.Second
	// sseBackoffMax caps the backoff between retries.
	sseBackoffMax = 10 * time.Second
)

type Source interface {
	SubscribeEvents(ctx context.Context, filter transport.EventFilter) (<-chan transport.RawEvent, <-chan error)
}

type Router interface {
	Normalize(raw transport.RawEvent) (AppEvent, bool)
	Subscribe(ctx context.Context, targetSessionID string, filter transport.EventFilter) (<-chan AppEvent, <-chan error)
}

type router struct {
	source      Source
	partTypes   map[string]string
	seenCallIDs map[string]bool
	lastErr     error
}

func NewRouter(source Source) Router {
	return &router{
		source:      source,
		partTypes:   make(map[string]string),
		seenCallIDs: make(map[string]bool),
	}
}

func (r *router) Normalize(raw transport.RawEvent) (AppEvent, bool) {
	var env rawEnvelope
	if err := json.Unmarshal(raw.Data, &env); err != nil {
		return AppEvent{
			Kind: EventUnknown,
			Payload: UnknownPayload{
				Type:    raw.Type,
				Summary: fmt.Sprintf("invalid event json: %v", err),
				Raw:     append(json.RawMessage(nil), raw.Data...),
			},
		}, true
	}
	if env.Type == "" {
		env.Type = raw.Type
	}

	switch env.Type {
	case "message.part.updated":
		return r.normalizeMessagePartUpdated(env)
	case "message.part.delta":
		return r.normalizeMessagePartDelta(env)
	case "permission.asked":
		return normalizePermissionAsked(env)
	case "question.asked":
		return normalizeQuestionAsked(env)
	case "session.idle":
		return normalizeSessionIdle(env)
	case "session.next.text.delta":
		return normalizeSessionNextTextDelta(env, EventTextDelta)
	case "session.next.reasoning.delta":
		return normalizeSessionNextTextDelta(env, EventReasoningDelta)
	case "session.next.tool.called":
		return r.normalizeSessionNextToolCalled(env)
	case "session.next.tool.success":
		return normalizeSessionNextToolResult(env, EventToolSucceeded)
	case "session.next.tool.failed":
		return normalizeSessionNextToolResult(env, EventToolFailed)
	case "session.next.agent.switched":
		return normalizeSessionNextAgentSwitched(env)
	case "session.next.model.switched":
		return normalizeSessionNextModelSwitched(env)
	case "server.connected", "server.heartbeat",
		"message.updated", "message.removed", "message.part.removed",
		"session.status", "session.updated", "session.diff", "session.created", "session.deleted",
		"session.next.prompted",
		"session.next.step.started", "session.next.step.ended",
		"plugin.added", "plugin.removed",
		"catalog.updated",
		"integration.updated",
		"reference.updated",
		"file.edited", "file.watcher.updated",
		"permission.replied":
		return AppEvent{}, false
	default:
		return AppEvent{
			Kind:      EventUnknown,
			SessionID: sessionIDFromProperties(env.Properties),
			Payload: UnknownPayload{
				Type:    env.Type,
				Summary: summarizeRaw(raw.Data),
				Raw:     append(json.RawMessage(nil), raw.Data...),
			},
		}, true
	}
}

func (r *router) Subscribe(ctx context.Context, targetSessionID string, filter transport.EventFilter) (<-chan AppEvent, <-chan error) {
	out := make(chan AppEvent, 32)
	errs := make(chan error, 1)
	if r.source == nil {
		close(out)
		errs <- fmt.Errorf("event source is nil")
		close(errs)
		return out, errs
	}

	go func() {
		defer close(out)
		defer close(errs)

		for attempt := 0; ; attempt++ {
			if err := ctx.Err(); err != nil {
				return
			}
			if attempt > 0 {
				backoff := time.Duration(math.Min(float64(sseBackoffBase)*float64(int(1)<<(attempt-1)), float64(sseBackoffMax)))
				select {
				case <-ctx.Done():
					return
				case <-time.After(backoff):
				}
			}

			rawEvents, rawErrs := r.source.SubscribeEvents(ctx, filter)
			done, retry := r.streamOnce(ctx, rawEvents, rawErrs, targetSessionID, out)
			if done {
				return
			}
			if !retry || attempt >= maxSSERetries {
				errs <- fmt.Errorf("sse connection failed after %d attempts: %w", attempt+1, r.lastErr)
				return
			}
		}
	}()
	return out, errs
}

// streamOnce reads from a single SSE connection until it ends or errors.
// It returns (done, retry) — done means the stream completed normally;
// retry indicates the error is transient and worth reconnecting.
func (r *router) streamOnce(ctx context.Context, rawEvents <-chan transport.RawEvent, rawErrs <-chan error, targetSessionID string, out chan<- AppEvent) (bool, bool) {
	// Reset seen call IDs so replayed events after reconnect are not
	// incorrectly dropped.
	r.seenCallIDs = make(map[string]bool)
	for {
		select {
		case <-ctx.Done():
			return true, false
		case err, ok := <-rawErrs:
			if !ok {
				rawErrs = nil
				if rawEvents == nil {
					return true, false
				}
				continue
			}
			if err != nil {
				r.lastErr = err
				return false, isRetryable(err)
			}
		case raw, ok := <-rawEvents:
			if !ok {
				rawEvents = nil
				if rawErrs == nil {
					return true, false
				}
				continue
			}
			evt, ok := r.Normalize(raw)
			if !ok {
				continue
			}
			if targetSessionID != "" && evt.SessionID != "" && evt.SessionID != targetSessionID {
				continue
			}
			select {
			case <-ctx.Done():
				return true, false
			case out <- evt:
			}
		}
	}
}

// isRetryable returns true for transient network errors that may succeed
// on reconnection. Schema errors and clean shutdowns are not retryable.
func isRetryable(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) {
		return false
	}
	var netErr net.Error
	if errors.As(err, &netErr) {
		return netErr.Timeout() || netErr.Temporary()
	}
	var urlErr *url.Error
	if errors.As(err, &urlErr) {
		return isRetryable(urlErr.Err)
	}
	var opErr *net.OpError
	if errors.As(err, &opErr) {
		return true
	}
	// Treat unknown errors as non-retryable to avoid infinite loops.
	return false
}

func (r *router) normalizeMessagePartUpdated(env rawEnvelope) (AppEvent, bool) {
	var props partUpdatedProps
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode message.part.updated properties: "+err.Error()), true
	}
	var part partBase
	if err := json.Unmarshal(props.Part, &part); err != nil {
		return unknownFromEnvelope(env, "decode message part: "+err.Error()), true
	}
	if part.ID != "" && part.Type != "" {
		r.partTypes[part.ID] = part.Type
	}
	return r.normalizePartUpdated(props.SessionID, part)
}

func (r *router) normalizeMessagePartDelta(env rawEnvelope) (AppEvent, bool) {
	var props partDeltaProps
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode message.part.delta properties: "+err.Error()), true
	}
	if props.Field != "text" {
		return AppEvent{}, false
	}
	kind := EventTextDelta
	if r.partTypes[props.PartID] == "reasoning" {
		kind = EventReasoningDelta
	}
	return AppEvent{
		Kind:      kind,
		SessionID: props.SessionID,
		Payload: TextDeltaPayload{
			Delta:     props.Delta,
			PartID:    props.PartID,
			MessageID: props.MessageID,
		},
	}, true
}

func (r *router) normalizePartUpdated(sessionID string, part partBase) (AppEvent, bool) {
	switch part.Type {
	case "step-start":
		return AppEvent{Kind: EventStepStarted, SessionID: sessionID}, true
	case "step-finish":
		payload := StepEndedPayload{Cost: part.Cost, Duration: part.Duration}
		if part.Tokens != nil {
			payload.Tokens = *part.Tokens
		}
		return AppEvent{Kind: EventStepEnded, SessionID: sessionID, Payload: payload}, true
	case "tool":
		if part.State == nil {
			return AppEvent{}, false
		}
		switch part.State.Status {
		case "running":
			if part.CallID != "" && r.seenCallIDs[part.CallID] {
				return AppEvent{}, false
			}
			if part.CallID != "" {
				r.seenCallIDs[part.CallID] = true
			}
			return AppEvent{
				Kind:      EventToolCalled,
				SessionID: sessionID,
				Payload: ToolCalledPayload{
					ToolName: part.Tool,
					CallID:   part.CallID,
					Input:    part.State.Input,
					PartID:   part.ID,
				},
			}, true
		case "completed":
			return AppEvent{
				Kind:      EventToolSucceeded,
				SessionID: sessionID,
				Payload:   ToolResultPayload{CallID: part.CallID, PartID: part.ID, Output: part.State.Output},
			}, true
		case "error":
			return AppEvent{
				Kind:      EventToolFailed,
				SessionID: sessionID,
				Payload:   ToolResultPayload{CallID: part.CallID, PartID: part.ID, Error: part.State.Error},
			}, true
		}
	}
	return AppEvent{}, false
}

func normalizePermissionAsked(env rawEnvelope) (AppEvent, bool) {
	var props permissionAskedProps
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode permission.asked properties: "+err.Error()), true
	}
	return AppEvent{
		Kind:      EventPermissionAsked,
		SessionID: props.SessionID,
		Payload: PermissionAskedPayload{
			RequestID:  firstNonEmpty(props.ID, props.RequestID),
			Permission: props.Permission,
			Patterns:   props.Patterns,
		},
	}, true
}

func normalizeQuestionAsked(env rawEnvelope) (AppEvent, bool) {
	var props questionAskedProps
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode question.asked properties: "+err.Error()), true
	}
	return AppEvent{
		Kind:      EventQuestionAsked,
		SessionID: props.SessionID,
		Payload: QuestionAskedPayload{
			RequestID: firstNonEmpty(props.ID, props.RequestID),
			Questions: props.Questions,
		},
	}, true
}

func normalizeSessionIdle(env rawEnvelope) (AppEvent, bool) {
	var props struct {
		SessionID string `json:"sessionID"`
	}
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode session.idle properties: "+err.Error()), true
	}
	return AppEvent{Kind: EventSessionIdle, SessionID: props.SessionID}, true
}

func normalizeSessionNextTextDelta(env rawEnvelope, kind AppEventKind) (AppEvent, bool) {
	var props struct {
		SessionID string `json:"sessionID"`
		Delta     string `json:"delta"`
		PartID    string `json:"partID"`
		MessageID string `json:"messageID"`
	}
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode "+env.Type+" properties: "+err.Error()), true
	}
	return AppEvent{
		Kind:      kind,
		SessionID: props.SessionID,
		Payload: TextDeltaPayload{
			Delta:     props.Delta,
			PartID:    props.PartID,
			MessageID: props.MessageID,
		},
	}, true
}

func (r *router) normalizeSessionNextToolCalled(env rawEnvelope) (AppEvent, bool) {
	var props struct {
		SessionID string          `json:"sessionID"`
		CallID    string          `json:"callID"`
		Tool      string          `json:"tool"`
		Input     json.RawMessage `json:"input"`
		PartID    string          `json:"partID"`
	}
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode session.next.tool.called properties: "+err.Error()), true
	}
	if props.CallID != "" && r.seenCallIDs[props.CallID] {
		return AppEvent{}, false
	}
	if props.CallID != "" {
		r.seenCallIDs[props.CallID] = true
	}
	return AppEvent{
		Kind:      EventToolCalled,
		SessionID: props.SessionID,
		Payload:   ToolCalledPayload{ToolName: props.Tool, CallID: props.CallID, Input: props.Input, PartID: props.PartID},
	}, true
}

func normalizeSessionNextToolResult(env rawEnvelope, kind AppEventKind) (AppEvent, bool) {
	var props struct {
		SessionID string `json:"sessionID"`
		CallID    string `json:"callID"`
		PartID    string `json:"partID"`
		Output    string `json:"output"`
		Error     string `json:"error"`
	}
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode "+env.Type+" properties: "+err.Error()), true
	}
	payload := ToolResultPayload{CallID: props.CallID, PartID: props.PartID, Output: props.Output, Error: props.Error}
	return AppEvent{Kind: kind, SessionID: props.SessionID, Payload: payload}, true
}

func normalizeSessionNextAgentSwitched(env rawEnvelope) (AppEvent, bool) {
	var props struct {
		SessionID string `json:"sessionID"`
		AgentID   string `json:"agentID"`
		AgentName string `json:"agentName"`
	}
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode session.next.agent.switched properties: "+err.Error()), true
	}
	return AppEvent{
		Kind:      EventAgentSwitched,
		SessionID: props.SessionID,
		Payload: AgentSwitchedPayload{
			AgentID:   props.AgentID,
			AgentName: props.AgentName,
		},
	}, true
}

func normalizeSessionNextModelSwitched(env rawEnvelope) (AppEvent, bool) {
	var props struct {
		SessionID  string `json:"sessionID"`
		ProviderID string `json:"providerID"`
		ModelID    string `json:"modelID"`
	}
	if err := json.Unmarshal(env.Properties, &props); err != nil {
		return unknownFromEnvelope(env, "decode session.next.model.switched properties: "+err.Error()), true
	}
	return AppEvent{
		Kind:      EventModelSwitched,
		SessionID: props.SessionID,
		Payload: ModelSwitchedPayload{
			ProviderID: props.ProviderID,
			ModelID:    props.ModelID,
		},
	}, true
}

func unknownFromEnvelope(env rawEnvelope, summary string) AppEvent {
	return AppEvent{
		Kind:      EventUnknown,
		SessionID: sessionIDFromProperties(env.Properties),
		Payload: UnknownPayload{
			Type:    env.Type,
			Summary: summary,
			Raw:     append(json.RawMessage(nil), env.Properties...),
		},
	}
}

func sessionIDFromProperties(raw json.RawMessage) string {
	var props struct {
		SessionID string `json:"sessionID"`
	}
	if err := json.Unmarshal(raw, &props); err != nil {
		return ""
	}
	return props.SessionID
}

func summarizeRaw(raw []byte) string {
	const max = 512
	summary := strings.TrimSpace(string(raw))
	if len(summary) > max {
		return summary[:max] + "..."
	}
	return summary
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

type rawEnvelope struct {
	ID         string          `json:"id"`
	Type       string          `json:"type"`
	Properties json.RawMessage `json:"properties"`
}

type partUpdatedProps struct {
	SessionID string          `json:"sessionID"`
	Part      json.RawMessage `json:"part"`
}

type partBase struct {
	ID       string          `json:"id"`
	Type     string          `json:"type"`
	Tool     string          `json:"tool,omitempty"`
	CallID   string          `json:"callID,omitempty"`
	State    *toolState      `json:"state,omitempty"`
	Cost     float64         `json:"cost,omitempty"`
	Tokens   *StepTokens     `json:"tokens,omitempty"`
	Duration float64         `json:"duration,omitempty"`
	Raw      json.RawMessage `json:"-"`
}

type toolState struct {
	Status string          `json:"status"`
	Input  json.RawMessage `json:"input,omitempty"`
	Output string          `json:"output,omitempty"`
	Error  string          `json:"error,omitempty"`
}

type partDeltaProps struct {
	SessionID string `json:"sessionID"`
	MessageID string `json:"messageID"`
	PartID    string `json:"partID"`
	Field     string `json:"field"`
	Delta     string `json:"delta"`
}

type permissionAskedProps struct {
	ID         string   `json:"id"`
	RequestID  string   `json:"requestID"`
	SessionID  string   `json:"sessionID"`
	Permission string   `json:"permission"`
	Patterns   []string `json:"patterns"`
}

type questionAskedProps struct {
	ID        string         `json:"id"`
	RequestID string         `json:"requestID"`
	SessionID string         `json:"sessionID"`
	Questions []QuestionInfo `json:"questions"`
}
