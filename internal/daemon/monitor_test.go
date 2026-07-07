package daemon

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func mustPort(u string) int {
	var port int
	_, _ = fmt.Sscanf(u, "http://127.0.0.1:%d", &port)
	return port
}

func TestIsBusy_BusySession(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ses_1":{"type":"busy"},"ses_2":{"type":"idle"}}`))
	}))
	defer srv.Close()

	busy, err := isBusy(context.Background(), ServerInfo{Port: mustPort(srv.URL)})
	if err != nil {
		t.Fatalf("isBusy error: %v", err)
	}
	if !busy {
		t.Fatal("expected busy=true when session type is busy")
	}
}

func TestIsBusy_RetrySession(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ses_1":{"type":"retry"}}`))
	}))
	defer srv.Close()

	busy, err := isBusy(context.Background(), ServerInfo{Port: mustPort(srv.URL)})
	if err != nil {
		t.Fatalf("isBusy error: %v", err)
	}
	if !busy {
		t.Fatal("expected busy=true when session type is retry")
	}
}

func TestIsBusy_AllIdle(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ses_1":{"type":"idle"},"ses_2":{"type":"idle"}}`))
	}))
	defer srv.Close()

	busy, err := isBusy(context.Background(), ServerInfo{Port: mustPort(srv.URL)})
	if err != nil {
		t.Fatalf("isBusy error: %v", err)
	}
	if busy {
		t.Fatal("expected busy=false when all sessions are idle")
	}
}

func TestIsBusy_NoSessions(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{}`))
	}))
	defer srv.Close()

	busy, err := isBusy(context.Background(), ServerInfo{Port: mustPort(srv.URL)})
	if err != nil {
		t.Fatalf("isBusy error: %v", err)
	}
	if busy {
		t.Fatal("expected busy=false when no sessions")
	}
}

func TestReaper_SkipsBusyServer(t *testing.T) {
	monitor := NewMonitor()
	monitor.mu.Lock()
	monitor.servers[4099] = &serverRecord{
		info:     ServerInfo{PID: 1, Port: 4099},
		lastUsed: time.Now().Add(-time.Hour),
	}
	monitor.mu.Unlock()

	idle := monitor.IdleServers(30 * time.Minute)
	if len(idle) != 1 {
		t.Fatalf("expected 1 idle server, got %d", len(idle))
	}
	if idle[0].Port != 4099 {
		t.Fatalf("expected port 4099, got %d", idle[0].Port)
	}
}

func TestReaper_SkipsNeverTouched(t *testing.T) {
	monitor := NewMonitor()
	monitor.mu.Lock()
	monitor.servers[4099] = &serverRecord{
		info: ServerInfo{PID: 1, Port: 4099},
	}
	monitor.mu.Unlock()

	idle := monitor.IdleServers(30 * time.Minute)
	if len(idle) != 0 {
		t.Fatal("expected 0 idle servers when never touched")
	}
}
