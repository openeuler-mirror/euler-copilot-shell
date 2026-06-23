//go:build integration

package integration

import (
	"context"
	"fmt"
	"os"
	"testing"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/event"
	"atomgit.com/openeuler/euler-copilot-shell/internal/session"
	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
)

const serverURL = "http://127.0.0.1:4096"

// skipIfServerDown skips the test when opencode is unreachable.
func skipIfServerDown(t *testing.T, client transport.Client) {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	if _, err := client.Health(ctx); err != nil {
		t.Skipf("opencode server not reachable at %s: %v", serverURL, err)
	}
}

func newTransport(t *testing.T) transport.Client {
	t.Helper()
	client, err := transport.NewClient(transport.Options{BaseURL: serverURL})
	if err != nil {
		t.Fatalf("NewClient: %v", err)
	}
	return client
}

// ─── P1-1 Transport HTTP Client ───

func TestTransport_Health(t *testing.T) {
	client := newTransport(t)
	skipIfServerDown(t, client)

	health, err := client.Health(context.Background())
	if err != nil {
		t.Fatalf("Health: %v", err)
	}
	if !health.Healthy {
		t.Fatal("server not healthy")
	}
	if health.Version == "" {
		t.Fatal("version missing")
	}
	t.Logf("server version: %s", health.Version)
}

func TestTransport_SessionCreateListGet(t *testing.T) {
	client := newTransport(t)
	skipIfServerDown(t, client)

	cwd, _ := os.Getwd()

	// Create
	session, err := client.CreateSession(context.Background(), transport.CreateSessionRequest{
		Directory: cwd,
		Title:     "integration-test",
	})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}
	if session.ID == "" {
		t.Fatal("session ID empty")
	}
	t.Logf("created session %s", session.ID)

	// Get
	got, err := client.GetSession(context.Background(), session.ID)
	if err != nil {
		t.Fatalf("GetSession: %v", err)
	}
	if got.ID != session.ID {
		t.Fatalf("GetSession ID mismatch: got %q, want %q", got.ID, session.ID)
	}

	// List
	sessions, err := client.ListSessions(context.Background(), transport.SessionFilter{
		Directory: cwd,
		Limit:     float64Ptr(5),
	})
	if err != nil {
		t.Fatalf("ListSessions: %v", err)
	}
	found := false
	for _, s := range sessions {
		if s.ID == session.ID {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("created session %q not in list (%d results)", session.ID, len(sessions))
	}
	t.Logf("list returned %d sessions", len(sessions))
}

func TestTransport_SendPromptAsyncAndSubscribe(t *testing.T) {
	client := newTransport(t)
	skipIfServerDown(t, client)

	cwd, _ := os.Getwd()
	session, err := client.CreateSession(context.Background(), transport.CreateSessionRequest{
		Directory: cwd,
		Title:     "streaming-test",
	})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}
	t.Logf("session: %s", session.ID)

	// Subscribe first
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	rawEvents, rawErrs := client.SubscribeEvents(ctx, transport.EventFilter{Directory: cwd})

	// Send prompt
	err = client.SendPromptAsync(ctx, session.ID, transport.PromptRequest{
		Directory: cwd,
		Parts:     []transport.PromptPart{{Type: "text", Text: "say just the word hello"}},
	})
	if err != nil {
		t.Fatalf("SendPromptAsync: %v", err)
	}
	t.Log("prompt sent, waiting for events...")

	// Collect events until session.idle
	var gotTextDelta, gotSessionIdle bool
	for raw := range rawEvents {
		t.Logf("raw event type=%s data=%s", raw.Type, string(raw.Data)[:min(120, len(raw.Data))])
		if raw.Type == "session.idle" {
			gotSessionIdle = true
			break
		}
		// Check for text deltas via message.part.delta or session.next.text.delta
		if raw.Type == "message.part.delta" || raw.Type == "session.next.text.delta" {
			gotTextDelta = true
		}
	}
	for err := range rawErrs {
		if err != nil {
			t.Fatalf("stream error: %v", err)
		}
	}

	if !gotTextDelta {
		t.Error("no text delta events received")
	}
	if !gotSessionIdle {
		t.Error("no session.idle event received (stream may have ended without it)")
	}
}

// ─── P1-3 Event Normalization ───

func TestEventRouter_WithRealEvents(t *testing.T) {
	client := newTransport(t)
	skipIfServerDown(t, client)

	cwd, _ := os.Getwd()
	session, err := client.CreateSession(context.Background(), transport.CreateSessionRequest{
		Directory: cwd,
		Title:     "event-test",
	})
	if err != nil {
		t.Fatalf("CreateSession: %v", err)
	}

	router := event.NewRouter(client)
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	appEvents, appErrs := router.Subscribe(ctx, session.ID, transport.EventFilter{Directory: cwd})

	// Send prompt
	if err := client.SendPromptAsync(ctx, session.ID, transport.PromptRequest{
		Directory: cwd,
		Parts:     []transport.PromptPart{{Type: "text", Text: "say just the word hello"}},
	}); err != nil {
		t.Fatalf("SendPromptAsync: %v", err)
	}

	// Collect normalized events until session.idle
	kindCount := map[event.AppEventKind]int{}
	var sessionIdleReceived bool
loop:
	for {
		select {
		case evt, ok := <-appEvents:
			if !ok {
				break loop
			}
			kindCount[evt.Kind]++
			t.Logf("AppEvent kind=%s sessionID=%s", evt.Kind, evt.SessionID)
			if evt.SessionID != session.ID && evt.SessionID != "" {
				t.Errorf("sessionID filter failed: got %q, want %q or empty", evt.SessionID, session.ID)
			}
			if evt.Kind == event.EventSessionIdle {
				sessionIdleReceived = true
				cancel() // stop the subscription
			}
		case err, ok := <-appErrs:
			if ok && err != nil {
				t.Fatalf("event error: %v", err)
			}
			if !ok {
				break loop
			}
		case <-ctx.Done():
			if sessionIdleReceived {
				break loop
			}
			t.Fatal("timeout waiting for events")
		}
	}

	t.Logf("event counts: %v", kindCount)
	if kindCount[event.EventTextDelta] == 0 {
		t.Error("no text delta events after normalization")
	}
	if kindCount[event.EventSessionIdle] == 0 {
		t.Error("no session.idle event after normalization")
	}
}

// ─── P1-4 Session Manager ───

func TestSessionResolver_ResolveAndList(t *testing.T) {
	client := newTransport(t)
	skipIfServerDown(t, client)

	resolver, err := session.NewService(session.Options{
		Transport: client,
		StatePath: fmt.Sprintf("%s/witty-integration-state.json", t.TempDir()),
	})
	if err != nil {
		t.Fatalf("NewService: %v", err)
	}

	cwd, _ := os.Getwd()

	// Resolve (auto-create or find existing)
	ctx, err := resolver.Resolve(context.Background(), cwd, false)
	if err != nil {
		t.Fatalf("Resolve: %v", err)
	}
	if ctx.ID == "" {
		t.Fatal("resolved session ID empty")
	}
	t.Logf("resolved session %s (dir=%s, title=%s)", ctx.ID, ctx.Directory, ctx.Title)

	// Force new
	newCtx, err := resolver.Resolve(context.Background(), cwd, true)
	if err != nil {
		t.Fatalf("Resolve(forceNew): %v", err)
	}
	if newCtx.ID == "" {
		t.Fatal("force-new session ID empty")
	}
	if newCtx.ID == ctx.ID {
		t.Errorf("force-new returned same session %q", newCtx.ID)
	}
	t.Logf("force-new session %s", newCtx.ID)

	// Continue
	cont, err := resolver.Continue(context.Background(), ctx.ID)
	if err != nil {
		t.Fatalf("Continue: %v", err)
	}
	if cont.ID != ctx.ID {
		t.Fatalf("Continue ID mismatch: got %q, want %q", cont.ID, ctx.ID)
	}
	t.Logf("continued session %s", cont.ID)

	// List
	summaries, err := resolver.List(context.Background(), session.Scope{Directory: cwd, Limit: float64Ptr(10)})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(summaries) == 0 {
		t.Fatal("no sessions listed")
	}
	t.Logf("listed %d sessions: first=%s", len(summaries), summaries[0].ID)
}

func TestSessionResolver_ContinueInvalidID(t *testing.T) {
	client := newTransport(t)
	skipIfServerDown(t, client)

	resolver, _ := session.NewService(session.Options{
		Transport: client,
		StatePath: fmt.Sprintf("%s/witty-integration-state.json", t.TempDir()),
	})

	_, err := resolver.Continue(context.Background(), "ses_nonexistent_12345")
	if err == nil {
		t.Fatal("expected error for nonexistent session, got nil")
	}
	t.Logf("expected error: %v", err)
}

func float64Ptr(v float64) *float64 { return &v }
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
