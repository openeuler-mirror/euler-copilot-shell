//go:build pty

package pty

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync"
)

// mockOpenCode is an httptest server that simulates the opencode API
// just enough to test witty's rendering pipeline. It serves a predefined
// sequence of SSE events captured from a real opencode session.
type mockOpenCode struct {
	*httptest.Server
	sessionID string
	events    []sseEvent
	mu        sync.Mutex
}

// sseEvent is a single event to be sent on the SSE stream.
type sseEvent struct {
	Type       string          `json:"type"`
	Properties json.RawMessage `json:"properties"`
}

// newMockOpenCode creates a server that will replay the given events.
func newMockOpenCode(events []sseEvent) *mockOpenCode {
	m := &mockOpenCode{
		sessionID: "ses_mock_001",
		events:    events,
	}
	m.Server = httptest.NewServer(http.HandlerFunc(m.serveHTTP))
	return m
}

func (m *mockOpenCode) serveHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	switch r.URL.Path {
	case "/global/health":
		json.NewEncoder(w).Encode(map[string]any{"healthy": true, "version": "mock"})

	case "/session":
		if r.Method == http.MethodPost {
			json.NewEncoder(w).Encode(map[string]any{
				"id":        m.sessionID,
				"directory": "/mock",
				"title":     "mock session",
			})
			return
		}
		if r.URL.Query().Get("directory") != "" {
			json.NewEncoder(w).Encode([]map[string]any{{
				"id":        m.sessionID,
				"directory": "/mock",
				"model":     map[string]string{"id": "mock-model", "providerID": "mock"},
			}})
			return
		}
		w.WriteHeader(http.StatusMethodNotAllowed)

	case "/event":
		m.serveSSE(w, r)

	case "/session/provider-defaults":
		json.NewEncoder(w).Encode(map[string]any{
			"connected": []string{"mock"},
			"default":   map[string]string{"mock": "mock-model"},
		})

	default:
		// /session/{id}/prompt_async, /session/{id}, etc.
		if r.URL.Path == "/session/"+m.sessionID+"/prompt_async" && r.Method == http.MethodPost {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		if r.URL.Path == "/session/"+m.sessionID && r.Method == http.MethodGet {
			json.NewEncoder(w).Encode(map[string]any{
				"id":        m.sessionID,
				"directory": "/mock",
			})
			return
		}
		json.NewEncoder(w).Encode(map[string]any{})
	}
}

func (m *mockOpenCode) serveSSE(w http.ResponseWriter, r *http.Request) {
	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")

	// Send server.connected first.
	fmt.Fprintf(w, "data: {\"id\":\"evt_conn\",\"type\":\"server.connected\",\"properties\":{}}\n\n")
	flusher.Flush()

	for _, evt := range m.events {
		payload := map[string]any{
			"id":         fmt.Sprintf("evt_mock_%s", evt.Type),
			"type":       evt.Type,
			"properties": evt.Properties,
		}
		data, _ := json.Marshal(payload)
		fmt.Fprintf(w, "data: %s\n\n", data)
		flusher.Flush()
	}
}

// defaultRenderEvents returns a minimal event sequence that exercises
// reasoning, tools (read + bash), text, and session.idle.
func defaultRenderEvents() []sseEvent {
	return []sseEvent{
		// Step 1: reasoning. Register part type BEFORE deltas so the router
		// classifies them as reasoning (not plain text).
		{Type: "message.part.updated", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","part":{"id":"prt_think","type":"reasoning"}}`)},
		{Type: "message.part.delta", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","delta":"I need to check the file.\n\n","field":"text","partID":"prt_think","messageID":"msg_001"}`)},
		{Type: "message.part.updated", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","part":{"type":"step-finish","cost":0.001,"tokens":{"input":20,"output":30,"reasoning":10},"duration":0.5}}`)},

		// Step 2: tools + text answer
		{Type: "message.part.updated", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","part":{"id":"prt_bash","type":"tool","tool":"bash","callID":"call_01","state":{"status":"running","input":{"command":"ls /etc","description":"List files"}}}}`)},
		{Type: "message.part.updated", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","part":{"id":"prt_bash","type":"tool","tool":"bash","callID":"call_01","state":{"status":"completed","input":{"command":"ls /etc"},"output":"nsswitch.conf\npasswd\n","title":"List files"}}}`)},

		{Type: "message.part.updated", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","part":{"id":"prt_text","type":"text"}}`)},
		{Type: "message.part.delta", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","delta":"The file /etc/nsswitch.conf exists.\n\n","field":"text","partID":"prt_text","messageID":"msg_001"}`)},
		{Type: "message.part.updated", Properties: json.RawMessage(`{"sessionID":"ses_mock_001","part":{"type":"step-finish","cost":0.002,"tokens":{"input":30,"output":40,"reasoning":0},"duration":0.3}}`)},

		// Stream end
		{Type: "session.idle", Properties: json.RawMessage(`{"sessionID":"ses_mock_001"}`)},
	}
}
