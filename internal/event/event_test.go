package event

import (
	"context"
	"encoding/json"
	"errors"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/transport"
)

func TestRouter_NormalizeTextAndReasoningDelta(t *testing.T) {
	router := NewRouter(nil)
	if evt, ok := router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":   "prt_text",
			"type": "text",
		},
	})); ok {
		t.Fatalf("text part.updated produced %+v, want cache only", evt)
	}

	evt, ok := router.Normalize(rawEvent("message.part.delta", map[string]any{
		"sessionID": "ses_1",
		"messageID": "msg_1",
		"partID":    "prt_text",
		"field":     "text",
		"delta":     "hello",
	}))
	if !ok || evt.Kind != EventTextDelta || evt.SessionID != "ses_1" {
		t.Fatalf("text delta = %+v, %v; want text event", evt, ok)
	}
	payload := evt.Payload.(TextDeltaPayload)
	if payload.Delta != "hello" || payload.PartID != "prt_text" || payload.MessageID != "msg_1" {
		t.Fatalf("text payload = %+v", payload)
	}

	_, _ = router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":   "prt_reason",
			"type": "reasoning",
		},
	}))
	evt, ok = router.Normalize(rawEvent("message.part.delta", map[string]any{
		"sessionID": "ses_1",
		"partID":    "prt_reason",
		"field":     "text",
		"delta":     "thinking",
	}))
	if !ok || evt.Kind != EventReasoningDelta {
		t.Fatalf("reasoning delta = %+v, %v; want reasoning event", evt, ok)
	}
}

func TestRouter_NormalizeStepAndToolEvents(t *testing.T) {
	router := NewRouter(nil)

	evt, ok := router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":   "prt_step",
			"type": "step-start",
		},
	}))
	if !ok || evt.Kind != EventStepStarted {
		t.Fatalf("step-start = %+v, %v; want step started", evt, ok)
	}

	evt, ok = router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":     "prt_step",
			"type":   "step-finish",
			"cost":   1.25,
			"tokens": map[string]any{"input": 1, "output": 2, "reasoning": 3},
		},
	}))
	if !ok || evt.Kind != EventStepEnded {
		t.Fatalf("step-finish = %+v, %v; want step ended", evt, ok)
	}
	step := evt.Payload.(StepEndedPayload)
	if step.Cost != 1.25 || step.Tokens.Input != 1 || step.Tokens.Output != 2 || step.Tokens.Reasoning != 3 {
		t.Fatalf("step payload = %+v", step)
	}

	evt, ok = router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":     "prt_tool",
			"type":   "tool",
			"tool":   "bash",
			"callID": "call_1",
			"state":  map[string]any{"status": "running", "input": map[string]any{"cmd": "ls"}},
		},
	}))
	if !ok || evt.Kind != EventToolCalled {
		t.Fatalf("tool running = %+v, %v; want tool called", evt, ok)
	}
	called := evt.Payload.(ToolCalledPayload)
	if called.ToolName != "bash" || called.CallID != "call_1" || !strings.Contains(string(called.Input), "ls") {
		t.Fatalf("tool called payload = %+v", called)
	}

	evt, ok = router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":     "prt_tool",
			"type":   "tool",
			"callID": "call_1",
			"state":  map[string]any{"status": "completed", "output": "ok"},
		},
	}))
	if !ok || evt.Kind != EventToolSucceeded || evt.Payload.(ToolResultPayload).Output != "ok" {
		t.Fatalf("tool completed = %+v, %v; want success", evt, ok)
	}

	evt, ok = router.Normalize(rawEvent("message.part.updated", map[string]any{
		"sessionID": "ses_1",
		"part": map[string]any{
			"id":     "prt_tool",
			"type":   "tool",
			"callID": "call_1",
			"state":  map[string]any{"status": "error", "error": "failed"},
		},
	}))
	if !ok || evt.Kind != EventToolFailed || evt.Payload.(ToolResultPayload).Error != "failed" {
		t.Fatalf("tool error = %+v, %v; want failure", evt, ok)
	}
}

func TestRouter_NormalizePermissionQuestionIdleUnknown(t *testing.T) {
	router := NewRouter(nil)

	evt, ok := router.Normalize(rawEvent("permission.asked", map[string]any{
		"id":         "per_1",
		"sessionID":  "ses_1",
		"permission": "tool",
		"patterns":   []string{"bash"},
	}))
	if !ok || evt.Kind != EventPermissionAsked || evt.Payload.(PermissionAskedPayload).RequestID != "per_1" {
		t.Fatalf("permission = %+v, %v", evt, ok)
	}

	evt, ok = router.Normalize(rawEvent("question.asked", map[string]any{
		"id":        "que_1",
		"sessionID": "ses_1",
		"questions": []map[string]any{{
			"question": "Continue?",
			"options":  []map[string]any{{"label": "yes", "description": "do it"}},
		}},
	}))
	if !ok || evt.Kind != EventQuestionAsked {
		t.Fatalf("question = %+v, %v", evt, ok)
	}
	question := evt.Payload.(QuestionAskedPayload)
	if question.RequestID != "que_1" || len(question.Questions) != 1 || question.Questions[0].Question != "Continue?" {
		t.Fatalf("question payload = %+v", question)
	}

	evt, ok = router.Normalize(rawEvent("session.idle", map[string]any{"sessionID": "ses_1"}))
	if !ok || evt.Kind != EventSessionIdle || evt.SessionID != "ses_1" {
		t.Fatalf("idle = %+v, %v", evt, ok)
	}

	evt, ok = router.Normalize(rawEvent("new.event", map[string]any{"sessionID": "ses_1", "value": 1}))
	if !ok || evt.Kind != EventUnknown || evt.SessionID != "ses_1" {
		t.Fatalf("unknown = %+v, %v", evt, ok)
	}
	if evt.Payload.(UnknownPayload).Type != "new.event" {
		t.Fatalf("unknown payload = %+v", evt.Payload)
	}
}

func TestRouter_NormalizeSessionNextCompatibility(t *testing.T) {
	router := NewRouter(nil)
	evt, ok := router.Normalize(rawEvent("session.next.text.delta", map[string]any{
		"sessionID": "ses_1",
		"delta":     "compat",
	}))
	if !ok || evt.Kind != EventTextDelta || evt.Payload.(TextDeltaPayload).Delta != "compat" {
		t.Fatalf("compat text = %+v, %v", evt, ok)
	}

	evt, ok = router.Normalize(rawEvent("session.next.tool.called", map[string]any{
		"sessionID": "ses_1",
		"callID":    "call_1",
		"tool":      "bash",
		"input":     map[string]any{"cmd": "pwd"},
	}))
	if !ok || evt.Kind != EventToolCalled || evt.Payload.(ToolCalledPayload).ToolName != "bash" {
		t.Fatalf("compat tool = %+v, %v", evt, ok)
	}
}

func TestRouter_SubscribeFiltersSessionID(t *testing.T) {
	source := &fakeSource{
		events: []transport.RawEvent{
			rawEvent("session.idle", map[string]any{"sessionID": "ses_other"}),
			rawEvent("session.idle", map[string]any{"sessionID": "ses_target"}),
		},
	}
	router := NewRouter(source)
	events, errs := router.Subscribe(context.Background(), "ses_target", transport.EventFilter{Directory: "/work"})

	var got []AppEvent
	for evt := range events {
		got = append(got, evt)
	}
	if len(got) != 1 || got[0].SessionID != "ses_target" {
		t.Fatalf("events = %+v, want only target session", got)
	}
	if source.filter.Directory != "/work" {
		t.Fatalf("filter = %+v, want directory", source.filter)
	}
	if err, ok := <-errs; ok && err != nil {
		t.Fatalf("errs got %v, want none", err)
	}
}

func TestRouter_SubscribeForwardsErrors(t *testing.T) {
	wantErr := errors.New("boom")
	router := NewRouter(&fakeSource{err: wantErr})
	events, errs := router.Subscribe(context.Background(), "ses_1", transport.EventFilter{})
	for range events {
	}
	if err, ok := <-errs; !ok || !errors.Is(err, wantErr) {
		t.Fatalf("err = %v, ok=%v; want boom", err, ok)
	}
}

func TestRouter_SchemaDriftReturnsUnknown(t *testing.T) {
	router := NewRouter(nil)
	evt, ok := router.Normalize(transport.RawEvent{Type: "broken", Data: []byte(`{not-json`)})
	if !ok || evt.Kind != EventUnknown {
		t.Fatalf("schema drift = %+v, %v; want unknown", evt, ok)
	}
}

func rawEvent(eventType string, properties any) transport.RawEvent {
	payload, err := json.Marshal(map[string]any{
		"id":         "evt_1",
		"type":       eventType,
		"properties": properties,
	})
	if err != nil {
		panic(err)
	}
	return transport.RawEvent{ID: "evt_1", Type: eventType, Data: payload}
}

type fakeSource struct {
	events []transport.RawEvent
	err    error
	filter transport.EventFilter
}

func (f *fakeSource) SubscribeEvents(_ context.Context, filter transport.EventFilter) (<-chan transport.RawEvent, <-chan error) {
	f.filter = filter
	events := make(chan transport.RawEvent, len(f.events))
	errs := make(chan error, 1)
	for _, evt := range f.events {
		events <- evt
	}
	close(events)
	if f.err != nil {
		errs <- f.err
	}
	close(errs)
	return events, errs
}
