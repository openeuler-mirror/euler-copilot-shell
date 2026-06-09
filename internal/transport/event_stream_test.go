package transport

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestParseStream_SingleEvent(t *testing.T) {
	events, err := parseSSE("id: evt_1\nevent: custom\ndata: hello\n\n")
	if err != nil {
		t.Fatalf("ParseStream() error = %v", err)
	}
	if len(events) != 1 {
		t.Fatalf("events len = %d, want 1", len(events))
	}
	if events[0].ID != "evt_1" || events[0].Type != "custom" || events[0].Data != "hello" {
		t.Fatalf("event = %+v, want id/type/data", events[0])
	}
}

func TestParseStream_MultilineDataAndComment(t *testing.T) {
	events, err := parseSSE(": heartbeat\ndata: first\ndata: second\n\n")
	if err != nil {
		t.Fatalf("ParseStream() error = %v", err)
	}
	if len(events) != 1 || events[0].Data != "first\nsecond" {
		t.Fatalf("events = %+v, want joined data", events)
	}
}

func TestParseStream_EmptyDataDispatches(t *testing.T) {
	events, err := parseSSE("data:\n\n")
	if err != nil {
		t.Fatalf("ParseStream() error = %v", err)
	}
	if len(events) != 1 || events[0].Data != "" {
		t.Fatalf("events = %+v, want one empty-data event", events)
	}
}

func TestParseStream_EOFResidualDispatches(t *testing.T) {
	events, err := parseSSE("data: tail")
	if err != nil {
		t.Fatalf("ParseStream() error = %v", err)
	}
	if len(events) != 1 || events[0].Data != "tail" {
		t.Fatalf("events = %+v, want EOF residual", events)
	}
}

func TestParseStream_MalformedRetryIgnored(t *testing.T) {
	events, err := parseSSE("retry: nope\ndata: x\n\nretry: 1500\ndata: y\n\n")
	if err != nil {
		t.Fatalf("ParseStream() error = %v", err)
	}
	if len(events) != 2 {
		t.Fatalf("events len = %d, want 2", len(events))
	}
	if events[0].Retry != 0 {
		t.Fatalf("first retry = %s, want 0", events[0].Retry)
	}
	if events[1].Retry != 1500*time.Millisecond {
		t.Fatalf("second retry = %s, want 1500ms", events[1].Retry)
	}
}

func TestParseStream_ContextCanceled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	out := make(chan SSEEvent, 1)
	err := ParseStream(ctx, strings.NewReader("data: ignored\n\n"), out)
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("ParseStream() error = %v, want context.Canceled", err)
	}
}

func TestClient_SubscribeEvents(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/event" {
			t.Fatalf("path = %s, want /event", r.URL.Path)
		}
		if r.URL.Query().Get("directory") != "/work" {
			t.Fatalf("directory = %q, want /work", r.URL.Query().Get("directory"))
		}
		if r.Header.Get("Accept") != "text/event-stream" {
			t.Fatalf("Accept = %q, want text/event-stream", r.Header.Get("Accept"))
		}
		w.Header().Set("Content-Type", "text/event-stream")
		_, _ = w.Write([]byte("data: {\"id\":\"evt_json\",\"type\":\"session.idle\",\"properties\":{}}\n\n"))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL, SSEClient: server.Client()})
	events, errs := client.SubscribeEvents(context.Background(), EventFilter{Directory: "/work"})
	evt, ok := <-events
	if !ok {
		t.Fatal("events channel closed before event")
	}
	if evt.ID != "evt_json" || evt.Type != "session.idle" || !strings.Contains(string(evt.Data), "session.idle") {
		t.Fatalf("event = %+v, want session.idle raw event", evt)
	}
	if _, ok := <-events; ok {
		t.Fatal("events channel still open after test stream EOF")
	}
	if err, ok := <-errs; ok && err != nil {
		t.Fatalf("error channel got %v, want none", err)
	}
}

func parseSSE(input string) ([]SSEEvent, error) {
	out := make(chan SSEEvent, 8)
	err := ParseStream(context.Background(), strings.NewReader(input), out)
	close(out)
	var events []SSEEvent
	for evt := range out {
		events = append(events, evt)
	}
	return events, err
}
