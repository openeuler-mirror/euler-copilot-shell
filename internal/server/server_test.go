package server

import (
	"context"
	"os"
	"path/filepath"
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

func TestManager_Ensure_AutoStartEnabled_NoServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     true,
		PreferredPort: 59999,
		Hostname:      "127.0.0.1",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// No server on that port, and opencode binary not found.
	// Should gracefully return the default connection without error.
	conn, err := mgr.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}
	if conn.URL != "http://127.0.0.1:59999" {
		t.Fatalf("conn.URL = %q, want default URL", conn.URL)
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

func TestDefaultServerStatePath(t *testing.T) {
	t.Run("WITTY_STATE_PATH env", func(t *testing.T) {
		lookup := func(key string) (string, bool) {
			if key == "WITTY_STATE_PATH" {
				return "/custom/state", true
			}
			return "", false
		}
		path, err := DefaultServerStatePath(lookup, nil)
		if err != nil {
			t.Fatalf("DefaultServerStatePath() error = %v", err)
		}
		if path != "/custom/state/witty/server-state.json" {
			t.Fatalf("path = %q, want /custom/state/witty/server-state.json", path)
		}
	})

	t.Run("XDG_STATE_HOME env", func(t *testing.T) {
		lookup := func(key string) (string, bool) {
			if key == "XDG_STATE_HOME" {
				return "/xdg/state", true
			}
			return "", false
		}
		path, err := DefaultServerStatePath(lookup, nil)
		if err != nil {
			t.Fatalf("DefaultServerStatePath() error = %v", err)
		}
		if path != "/xdg/state/witty/server-state.json" {
			t.Fatalf("path = %q, want /xdg/state/witty/server-state.json", path)
		}
	})

	t.Run("home dir fallback", func(t *testing.T) {
		lookup := func(string) (string, bool) { return "", false }
		homeDir := func() (string, error) { return "/home/testuser", nil }
		path, err := DefaultServerStatePath(lookup, homeDir)
		if err != nil {
			t.Fatalf("DefaultServerStatePath() error = %v", err)
		}
		if path != "/home/testuser/.local/state/witty/server-state.json" {
			t.Fatalf("path = %q, want /home/testuser/.local/state/witty/server-state.json", path)
		}
	})
}

func TestDefaultServerStateDir(t *testing.T) {
	lookup := func(string) (string, bool) { return "", false }
	homeDir := func() (string, error) { return "/home/testuser", nil }
	dir, err := DefaultServerStateDir(lookup, homeDir)
	if err != nil {
		t.Fatalf("DefaultServerStateDir() error = %v", err)
	}
	if dir != "/home/testuser/.local/state/witty" {
		t.Fatalf("dir = %q, want /home/testuser/.local/state/witty", dir)
	}
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
