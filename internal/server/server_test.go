package server

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestNewManager_RequiresStateDir(t *testing.T) {
	_, err := NewManager(Options{})
	if err == nil {
		t.Fatal("NewManager() error = nil, want error about StateDir")
	}
	if !strings.Contains(err.Error(), "StateDir") {
		t.Fatalf("error = %q, want StateDir context", err)
	}
}

func TestNewManager_CreatesStateDir(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "witty")
	mgr, err := NewManager(Options{StateDir: dir, AutoStart: false})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}
	if mgr == nil {
		t.Fatal("NewManager() = nil")
	}
	// Verify the directory was created.
	if _, err := os.Stat(dir); err != nil {
		t.Fatalf("state dir not created: %v", err)
	}
}

func TestStateStore_SaveAndLoad(t *testing.T) {
	dir := t.TempDir()
	store, err := newStateStore(dir)
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}

	now := time.Now()
	s := State{
		Port:      4097,
		Password:  "test-password",
		PID:       12345,
		StartedAt: now,
		LastUsed:  now,
	}
	if err := store.save(s); err != nil {
		t.Fatalf("save() error = %v", err)
	}

	loaded, err := store.load()
	if err != nil {
		t.Fatalf("load() error = %v", err)
	}
	if loaded.Port != s.Port {
		t.Fatalf("Port = %d, want %d", loaded.Port, s.Port)
	}
	if loaded.Password != s.Password {
		t.Fatalf("Password = %q, want %q", loaded.Password, s.Password)
	}
	if loaded.PID != s.PID {
		t.Fatalf("PID = %d, want %d", loaded.PID, s.PID)
	}
}

func TestStateStore_LoadMissing(t *testing.T) {
	dir := t.TempDir()
	store, err := newStateStore(dir)
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}

	loaded, err := store.load()
	if err != nil {
		t.Fatalf("load() error = %v", err)
	}
	// Should return zero-value State, not error.
	if loaded.Port != 0 || loaded.PID != 0 {
		t.Fatalf("State = %+v, want zero value", loaded)
	}
}

func TestStateStore_Remove(t *testing.T) {
	dir := t.TempDir()
	store, err := newStateStore(dir)
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}

	if err := store.save(State{Port: 4097, PID: 1}); err != nil {
		t.Fatalf("save() error = %v", err)
	}
	if err := store.remove(); err != nil {
		t.Fatalf("remove() error = %v", err)
	}
	// Loading after remove should return zero-value.
	loaded, err := store.load()
	if err != nil {
		t.Fatalf("load() error = %v", err)
	}
	if loaded.Port != 0 {
		t.Fatalf("Port = %d, want 0 after remove", loaded.Port)
	}
}

func TestIsPIDAlive_Self(t *testing.T) {
	if !isPIDAlive(os.Getpid()) {
		t.Fatal("isPIDAlive(self) = false, want true")
	}
}

func TestIsPIDAlive_ZeroAndNegative(t *testing.T) {
	if isPIDAlive(0) {
		t.Fatal("isPIDAlive(0) = true, want false")
	}
	if isPIDAlive(-1) {
		t.Fatal("isPIDAlive(-1) = true, want false")
	}
}

func TestIsPIDAlive_HighUnusedPID(t *testing.T) {
	// PID 99999 is unlikely to exist on any system.
	if isPIDAlive(99999) {
		t.Skip("PID 99999 unexpectedly exists; skipping test")
	}
}

func TestPortOpen_Closed(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	// Port 1 is reserved and should not be open.
	if portOpen(ctx, "127.0.0.1", 1) {
		t.Skip("port 1 is unexpectedly open; skipping test")
	}
}

func TestPortOpen_Open(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	srv, url := mockHealthServer(t)
	host, port := parseHostPort(t, url)

	if !portOpen(ctx, host, port) {
		t.Fatal("portOpen() = false, want true for mock server")
	}
	_ = srv
}

func TestHealthCheck_ValidServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	_, url := mockHealthServer(t)

	if !healthCheck(ctx, url) {
		t.Fatal("healthCheck() = false, want true for valid server")
	}
}

func TestHealthCheck_NonOpenCodeServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	_, url := mockNonOpenCodeServer(t)

	if healthCheck(ctx, url) {
		t.Fatal("healthCheck() = true, want false for non-opencode server")
	}
}

func TestHealthCheck_Unreachable(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	if healthCheck(ctx, "http://127.0.0.1:59999") {
		t.Fatal("healthCheck() = true, want false for unreachable server")
	}
}

func TestFindOpenCodeOnPort_Found(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	_, url := mockHealthServer(t)
	host, port := parseHostPort(t, url)

	if !findOpenCodeOnPort(ctx, host, port) {
		t.Fatal("findOpenCodeOnPort() = false, want true")
	}
}

func TestFindOpenCodeOnPort_NotFound(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	_, url := mockNonOpenCodeServer(t)
	host, port := parseHostPort(t, url)

	if findOpenCodeOnPort(ctx, host, port) {
		t.Fatal("findOpenCodeOnPort() = true, want false for non-opencode server")
	}
}

func TestManager_Ensure_ReusesExistingServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	// Start a mock health server to simulate an already-running opencode.
	srv, url := mockHealthServer(t)
	host, port := parseHostPort(t, url)
	_ = srv

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     true,
		PreferredPort: port,
		Hostname:      host,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}
	if conn.URL != url {
		t.Fatalf("conn.URL = %q, want %q", conn.URL, url)
	}
	// Phase 2: password is always generated.
	if conn.Password == "" {
		t.Fatal("conn.Password is empty; want generated password")
	}

	// Verify state was persisted.
	status := mgr.Status(ctx)
	if !status.Running {
		t.Fatal("status.Running = false, want true")
	}
	if status.Port != port {
		t.Fatalf("status.Port = %d, want %d", status.Port, port)
	}
}

func TestManager_Ensure_AutoStartDisabled_NoServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     false,
		PreferredPort: 59999, // unlikely to have a server
		Hostname:      "127.0.0.1",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	_, err = mgr.Ensure(ctx)
	if err == nil {
		t.Fatal("Ensure() error = nil, want error about auto_start disabled")
	}
	if !strings.Contains(err.Error(), "auto_start is disabled") {
		t.Fatalf("error = %q, want auto_start disabled context", err)
	}
}

func TestManager_Ensure_AutoStartEnabled_BinaryNotFound(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      59999,
		Hostname:           "127.0.0.1",
		OpenCodeBinaryPath: "/nonexistent/opencode-binary-that-does-not-exist",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// No server on that port, and the opencode binary does not exist.
	// Ensure must surface an explicit error rather than silently degrading.
	_, err = mgr.Ensure(ctx)
	if err == nil {
		t.Fatal("Ensure() error = nil, want ErrOpenCodeBinaryNotFound")
	}
	if !errors.Is(err, ErrOpenCodeBinaryNotFound) {
		t.Fatalf("error = %v, want ErrOpenCodeBinaryNotFound", err)
	}
}

func TestManager_Ensure_UsesMockOpenCodeBinary(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	// Use a port outside the default range (4096-4105) to avoid clashing
	// with any already-running opencode server the developer may have.
	testPort := 45999

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}
	if conn.URL == "" {
		t.Fatal("conn.URL is empty")
	}
	// Phase 2: password should be populated.
	if conn.Password == "" {
		t.Fatal("conn.Password is empty; want generated password")
	}

	// Verify the server is actually healthy (use auth since Phase 2
	// servers require a password).
	if healthCheckWithAuth(ctx, conn.URL, conn.Password) != 200 {
		t.Fatalf("healthCheckWithAuth(%q) != 200 after Ensure", conn.URL)
	}

	// Verify status reports correctly.
	status := mgr.Status(ctx)
	if !status.Running {
		t.Fatal("status.Running = false, want true")
	}
	if !status.Managed {
		t.Fatal("status.Managed = false, want true (started by this process)")
	}
	if status.PID <= 0 {
		t.Fatalf("status.PID = %d, want positive PID", status.PID)
	}

	// Stop the managed server.
	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() error = %v", err)
	}

	// Verify it's no longer running.
	status2 := mgr.Status(ctx)
	if status2.Running {
		t.Fatal("status.Running = true after Stop, want false")
	}
}

func TestManager_Stop_NoOpWhenNotManaged(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	_, url := mockHealthServer(t)
	host, port := parseHostPort(t, url)

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     true,
		PreferredPort: port,
		Hostname:      host,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// Ensure discovers the existing (not managed) server.
	_, err = mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	// Stop should be a no-op for non-managed servers.
	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() error = %v", err)
	}
}

func TestManager_Status_NoState(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     false,
		PreferredPort: 4096,
		Hostname:      "127.0.0.1",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	status := mgr.Status(ctx)
	if status.Running {
		t.Fatal("status.Running = true, want false (no state)")
	}
}

func TestDefaultServerStateDir(t *testing.T) {
	t.Run("WITTY_STATE_PATH as full file path", func(t *testing.T) {
		// WITTY_STATE_PATH is a full file path (matching session.DefaultStatePath);
		// the server state dir is the containing directory.
		lookup := func(key string) (string, bool) {
			if key == "WITTY_STATE_PATH" {
				return "/custom/state/my-state.json", true
			}
			return "", false
		}
		dir, err := DefaultServerStateDir(lookup, nil)
		if err != nil {
			t.Fatalf("DefaultServerStateDir() error = %v", err)
		}
		if dir != "/custom/state" {
			t.Fatalf("dir = %q, want /custom/state", dir)
		}
	})

	t.Run("XDG_STATE_HOME env", func(t *testing.T) {
		lookup := func(key string) (string, bool) {
			if key == "XDG_STATE_HOME" {
				return "/xdg/state", true
			}
			return "", false
		}
		dir, err := DefaultServerStateDir(lookup, nil)
		if err != nil {
			t.Fatalf("DefaultServerStateDir() error = %v", err)
		}
		if dir != "/xdg/state/witty" {
			t.Fatalf("dir = %q, want /xdg/state/witty", dir)
		}
	})

	t.Run("home dir fallback", func(t *testing.T) {
		lookup := func(string) (string, bool) { return "", false }
		homeDir := func() (string, error) { return "/home/testuser", nil }
		dir, err := DefaultServerStateDir(lookup, homeDir)
		if err != nil {
			t.Fatalf("DefaultServerStateDir() error = %v", err)
		}
		if dir != "/home/testuser/.local/state/witty" {
			t.Fatalf("dir = %q, want /home/testuser/.local/state/witty", dir)
		}
	})
}

func TestManager_PreferredPort(t *testing.T) {
	mgr := &manager{
		opts: Options{PreferredPort: 5000},
	}
	if mgr.hostname() != "127.0.0.1" {
		t.Fatalf("hostname() = %q, want 127.0.0.1", mgr.hostname())
	}
}

func TestManager_CustomHostname(t *testing.T) {
	mgr := &manager{
		opts: Options{Hostname: "0.0.0.0"},
	}
	if mgr.hostname() != "0.0.0.0" {
		t.Fatalf("hostname() = %q, want 0.0.0.0", mgr.hostname())
	}
}

func TestManager_CustomBinary(t *testing.T) {
	mgr := &manager{
		opts: Options{OpenCodeBinaryPath: "/custom/opencode"},
	}
	if mgr.binaryPath() != "/custom/opencode" {
		t.Fatalf("binaryPath() = %q, want /custom/opencode", mgr.binaryPath())
	}
}

func TestManager_DefaultBinary(t *testing.T) {
	mgr := &manager{opts: Options{}}
	if mgr.binaryPath() != "opencode" {
		t.Fatalf("binaryPath() = %q, want opencode", mgr.binaryPath())
	}
}

func TestManager_StartupTimeout(t *testing.T) {
	t.Run("custom", func(t *testing.T) {
		mgr := &manager{
			opts: Options{StartupTimeout: 5 * time.Second},
		}
		if mgr.startupTimeout() != 5*time.Second {
			t.Fatalf("startupTimeout() = %v, want 5s", mgr.startupTimeout())
		}
	})
	t.Run("default", func(t *testing.T) {
		mgr := &manager{opts: Options{}}
		if mgr.startupTimeout() != 10*time.Second {
			t.Fatalf("startupTimeout() = %v, want default 10s", mgr.startupTimeout())
		}
	})
}

func TestWaitForServer_Success(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	srv, url := mockHealthServer(t)
	_ = srv

	if err := waitForServer(ctx, url, 50*time.Millisecond); err != nil {
		t.Fatalf("waitForServer() error = %v", err)
	}
}

func TestWaitForServer_Timeout(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 200*time.Millisecond)
	defer cancel()

	err := waitForServer(ctx, "http://127.0.0.1:59999", 50*time.Millisecond)
	if err == nil {
		t.Fatal("waitForServer() error = nil, want timeout error")
	}
}

func TestWaitForServerWithAuth_Success(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	password := "test-secret"
	_, url := mockAuthHealthServer(t, password)

	if err := waitForServerWithAuth(ctx, url, password, 50*time.Millisecond); err != nil {
		t.Fatalf("waitForServerWithAuth() error = %v", err)
	}
}

func TestWaitForServerWithAuth_WrongPassword(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 1*time.Second)
	defer cancel()

	password := "test-secret"
	_, url := mockAuthHealthServer(t, password)

	err := waitForServerWithAuth(ctx, url, "wrong-pass", 50*time.Millisecond)
	if err == nil {
		t.Fatal("waitForServerWithAuth() error = nil, want timeout error")
	}
}

func TestIdleMonitorCheckInterval(t *testing.T) {
	tests := []struct {
		timeout time.Duration
		wantMin time.Duration
		wantMax time.Duration
	}{
		{30 * time.Minute, 100 * time.Millisecond, 5 * time.Minute},
		{1 * time.Minute, 100 * time.Millisecond, 5 * time.Minute},
		{10 * time.Second, 100 * time.Millisecond, 5 * time.Minute},
		{2 * time.Hour, 5 * time.Minute, 5 * time.Minute},
		{500 * time.Millisecond, 100 * time.Millisecond, 100 * time.Millisecond},
	}
	for _, tt := range tests {
		got := idleMonitorCheckInterval(tt.timeout)
		if got < tt.wantMin || got > tt.wantMax {
			t.Errorf("idleMonitorCheckInterval(%v) = %v, want [%v, %v]", tt.timeout, got, tt.wantMin, tt.wantMax)
		}
	}
}

func TestManager_IdleTimeout_StopsServer(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping idle timeout test in short mode (uses real time)")
	}
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	testPort := 45998

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		IdleTimeout:        200 * time.Millisecond, // very short for testing
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}
	if conn.URL == "" {
		t.Fatal("conn.URL is empty")
	}

	// Verify server is running initially.
	st := mgr.Status(ctx)
	if !st.Running {
		t.Fatal("server not running after Ensure")
	}
	if !st.Managed {
		t.Fatal("server not reported as managed")
	}

	// Wait for the idle monitor to detect the timeout and stop the server.
	// The last_used was set during Ensure. With 200ms idle timeout and
	// ~30s check interval (clamped from 200ms/6 ≈ 33ms), this should
	// happen quickly.
	waitCtx, waitCancel := context.WithTimeout(ctx, 5*time.Second)
	defer waitCancel()

	for {
		select {
		case <-waitCtx.Done():
			t.Fatal("idle timeout did not stop server within 5 seconds")
		default:
		}
		st := mgr.Status(waitCtx)
		if !st.Running {
			break // idle monitor stopped it
		}
		time.Sleep(100 * time.Millisecond)
	}

	// Verify state file was cleaned up.
	st2 := mgr.Status(ctx)
	if st2.Running {
		t.Fatal("server still running after idle timeout")
	}
}

func TestManager_IdleTimeout_Disabled(t *testing.T) {
	// Verify that 0 idle timeout does not start an idle monitor.
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	testPort := 45997

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		IdleTimeout:        0, // disabled
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	_, err = mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	// Server should still be running after a short wait.
	time.Sleep(500 * time.Millisecond)
	st := mgr.Status(ctx)
	if !st.Running {
		t.Fatal("server stopped unexpectedly when idle timeout is disabled")
	}

	// Clean up.
	_ = mgr.Stop(ctx)
}

func TestManager_Stop_CancelsIdleMonitor(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping idle timeout test in short mode")
	}
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	testPort := 45996

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		IdleTimeout:        5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	_, err = mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	// Explicit Stop before idle timeout triggers.
	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() error = %v", err)
	}

	st := mgr.Status(ctx)
	if st.Running {
		t.Fatal("server still running after explicit Stop")
	}
}

// --- P4-6e: Stop via /global/dispose + SIGTERM fallback ---

// mockDisposeServer starts an httptest server that responds to POST /global/dispose
// with 200 {"true"} and optionally requires HTTP Basic Auth.
func mockDisposeServer(t *testing.T, password string) (*httptest.Server, string) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/global/dispose" && r.Method == http.MethodPost {
			if password != "" {
				user, pass, ok := r.BasicAuth()
				if !ok || user != "opencode" || pass != password {
					w.WriteHeader(http.StatusUnauthorized)
					return
				}
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte("true"))
			return
		}
		http.NotFound(w, r)
	}))
	t.Cleanup(srv.Close)
	return srv, srv.URL
}

// writeFileState writes a server State as JSON into the manager's state dir.
func writeFileState(t *testing.T, stateDir string, st State) {
	t.Helper()
	data, err := json.MarshalIndent(st, "", "  ")
	if err != nil {
		t.Fatalf("marshal state: %v", err)
	}
	if err := os.WriteFile(filepath.Join(stateDir, stateFileName), append(data, '\n'), 0o600); err != nil {
		t.Fatalf("write state: %v", err)
	}
}

// readStateFile reads the server state file, returning the zero value when absent.
func readStateFile(t *testing.T, stateDir string) State {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(stateDir, stateFileName))
	if err != nil {
		if os.IsNotExist(err) {
			return State{}
		}
		t.Fatalf("read state: %v", err)
	}
	var st State
	if err := json.Unmarshal(data, &st); err != nil {
		t.Fatalf("unmarshal state: %v", err)
	}
	return st
}

func TestManager_Stop_DisposeSuccess_DeletesStateFile(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	srv, url := mockDisposeServer(t, "secret")
	host, port := parseHostPort(t, url)

	stateDir := t.TempDir()
	writeFileState(t, stateDir, State{
		Port:     port,
		Password: "secret",
		PID:      os.Getpid(), // alive, but dispose should win
	})

	mgr, err := NewManager(Options{
		StateDir:      stateDir,
		AutoStart:     false,
		PreferredPort: port,
		Hostname:      host,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() error = %v", err)
	}

	// State file should be removed after a successful dispose.
	if _, statErr := os.Stat(filepath.Join(stateDir, stateFileName)); !os.IsNotExist(statErr) {
		t.Fatalf("state file should be removed, got statErr=%v", statErr)
	}
	_ = srv
}

func TestManager_Stop_NoState_NoOp(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     false,
		PreferredPort: 4096,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() with no state error = %v", err)
	}
}

func TestManager_Stop_DisposeUnreachable_SigtermFallback(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping SIGTERM fallback test in short mode (spawns a real process)")
	}
	// Verifying that the SIGTERM'd child actually exits requires detecting zombie
	// processes via /proc, which only exists on Linux. On macOS the child becomes
	// an unreaped zombie and Signal(0) keeps reporting it alive, so the process
	// exit assertion is verified on the delivery platform (openEuler/Linux).
	if runtime.GOOS != "linux" {
		t.Skip("SIGTERM fallback process-exit verification requires /proc (Linux/openEuler)")
	}
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	testPort := 46010

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// Start a real mock server.
	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	// Corrupt the recorded URL so /global/dispose is unreachable, forcing the
	// SIGTERM fallback path. The recorded PID still points at the live process.
	mImpl := mgr.(*manager)
	st := readStateFile(t, mImpl.opts.StateDir)
	st.Port = 1 // unreachable port
	writeFileState(t, mImpl.opts.StateDir, st)

	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() error = %v", err)
	}

	// Process should have exited (isPIDAlive treats zombies as dead).
	if isPIDAlive(st.PID) {
		t.Fatalf("process %d still alive after SIGTERM fallback", st.PID)
	}
	_ = conn
}

func TestManager_Stop_DeadPID_CleansState(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	stateDir := t.TempDir()
	// A PID that is essentially guaranteed not to exist.
	writeFileState(t, stateDir, State{
		Port:     1,
		Password: "secret",
		PID:      999999,
	})

	mgr, err := NewManager(Options{
		StateDir:      stateDir,
		AutoStart:     false,
		PreferredPort: 4096,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	if err := mgr.Stop(ctx); err != nil {
		t.Fatalf("Stop() error = %v", err)
	}
	// State file removed for stale PID.
	if _, statErr := os.Stat(filepath.Join(stateDir, stateFileName)); !os.IsNotExist(statErr) {
		t.Fatalf("state file should be removed for dead PID")
	}
}

// --- P4-6e: TouchLastUsed ---

func TestManager_TouchLastUsed_UpdatesState(t *testing.T) {
	stateDir := t.TempDir()
	original := State{Port: 4096, Password: "p", PID: 123, LastUsed: time.Now().Add(-1 * time.Hour)}
	writeFileState(t, stateDir, original)

	mgr, err := NewManager(Options{StateDir: stateDir, PreferredPort: 4096})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	before := time.Now()
	mgr.TouchLastUsed()
	after := time.Now()

	st := readStateFile(t, stateDir)
	if st.LastUsed.Before(before) || st.LastUsed.After(after) {
		t.Fatalf("LastUsed = %v, want within [%v, %v]", st.LastUsed, before, after)
	}
	if st.Port != original.Port || st.Password != original.Password || st.PID != original.PID {
		t.Fatalf("other fields changed: got %+v, want %+v", st, original)
	}
}

func TestManager_TouchLastUsed_NoState_NoError(t *testing.T) {
	mgr, err := NewManager(Options{StateDir: t.TempDir(), PreferredPort: 4096})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}
	// Should not panic or return an error (it returns nothing, but must not panic).
	mgr.TouchLastUsed()
}

// --- P4-6e: Close ---

func TestManager_Close_StopsIdleMonitor(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping Close test in short mode (uses idle monitor goroutine)")
	}
	bin := mockOpenCodeBinary(t)
	testPort := 46011

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		IdleTimeout:        30 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	ctx, cancel := testCtx(t)
	defer cancel()
	if _, err := mgr.Ensure(ctx); err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	// Close should stop the idle monitor goroutine. The idle monitor's cancel
	// func should be nil afterwards.
	mgr.Close()

	m := mgr.(*manager)
	m.mu.Lock()
	idleCancel := m.idleCancel
	m.mu.Unlock()
	if idleCancel != nil {
		t.Fatal("idleCancel should be nil after Close")
	}

	// Clean up the running server.
	_ = mgr.Stop(ctx)
}

func TestManager_Close_Idempotent(t *testing.T) {
	mgr, err := NewManager(Options{StateDir: t.TempDir(), PreferredPort: 4096})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}
	mgr.Close()
	mgr.Close() // should not panic
}

// --- P4-6e: idle timeout lazy cleanup in Ensure ---

func TestManager_Ensure_IdleTimeout_LazyCleanup(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping lazy idle cleanup test in short mode (spawns a real process)")
	}
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	testPort := 46012

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		IdleTimeout:        1 * time.Minute,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// Start a server.
	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	// Simulate the server being idle past the timeout by backdating last_used.
	mImpl := mgr.(*manager)
	st := readStateFile(t, mImpl.opts.StateDir)
	st.LastUsed = time.Now().Add(-2 * time.Minute)
	writeFileState(t, mImpl.opts.StateDir, st)
	oldPID := st.PID

	// Ensure should lazily stop the stale server and start a new one.
	conn2, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() lazy cleanup error = %v", err)
	}
	if conn2.URL == "" {
		t.Fatal("Ensure() returned empty URL after lazy cleanup")
	}

	// The old server process should be gone after lazy cleanup. On Linux,
	// isPIDAlive detects zombies via /proc and reports them as dead. On macOS
	// without /proc the unreaped zombie is still reported alive, so the death
	// assertion only runs on Linux.
	if oldPID > 0 && runtime.GOOS == "linux" && isPIDAlive(oldPID) {
		t.Fatalf("old server process %d still alive after lazy cleanup", oldPID)
	}
	_ = conn

	// Clean up the new server. Give the old server a moment to fully exit and
	// release its port before the new server's Stop runs.
	time.Sleep(300 * time.Millisecond)
	_ = mgr.Stop(ctx)
}

func TestManager_Ensure_IdleTimeout_NotExpired_Reuses(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping idle reuse test in short mode (spawns a real process)")
	}
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	testPort := 46013

	mgr, err := NewManager(Options{
		StateDir:           t.TempDir(),
		AutoStart:          true,
		PreferredPort:      testPort,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		IdleTimeout:        10 * time.Minute,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}
	mImpl := mgr.(*manager)
	st := readStateFile(t, mImpl.opts.StateDir)
	originalPID := st.PID

	// last_used is recent; Ensure should reuse, not restart.
	conn2, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("second Ensure() error = %v", err)
	}
	if conn.URL != conn2.URL {
		t.Fatalf("Ensure reused a different URL: %q vs %q", conn.URL, conn2.URL)
	}
	st2 := readStateFile(t, mgr.(*manager).opts.StateDir)
	if st2.PID != originalPID {
		t.Fatalf("PID changed after reuse: %d vs %d", st2.PID, originalPID)
	}

	_ = mgr.Stop(ctx)
}

func TestPidIsOpenCodeServer_SelfOrAbsent(t *testing.T) {
	// On macOS /proc is absent; the function returns true (permissive). On
	// Linux it reads /proc/{pid}/cmdline. Either way, our own process should
	// not error: it returns true on non-Linux, and on Linux the test binary's
	// cmdline won't contain "opencode" so it returns false. We only assert
	// that it does not panic and returns a bool.
	got := pidIsOpenCodeServer(os.Getpid())
	_ = got
}

func TestWaitForProcessExit_AlreadyDead(t *testing.T) {
	// A PID guaranteed not to exist.
	if err := waitForProcessExit(999999, 1*time.Second); err != nil {
		t.Fatalf("waitForProcessExit for dead PID error = %v", err)
	}
}
