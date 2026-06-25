package server

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

func TestGeneratePassword_Randomness(t *testing.T) {
	p1, err := GeneratePassword()
	if err != nil {
		t.Fatalf("GeneratePassword() error = %v", err)
	}
	if len(p1) != 64 {
		t.Fatalf("GeneratePassword() length = %d, want 64 (32 bytes hex)", len(p1))
	}

	p2, err := GeneratePassword()
	if err != nil {
		t.Fatalf("GeneratePassword() error = %v", err)
	}
	if p1 == p2 {
		t.Fatal("two consecutive GeneratePassword() calls produced the same password")
	}
}

func TestGeneratePassword_HexCharacters(t *testing.T) {
	p, err := GeneratePassword()
	if err != nil {
		t.Fatalf("GeneratePassword() error = %v", err)
	}
	for _, c := range p {
		if (c < '0' || c > '9') && (c < 'a' || c > 'f') {
			t.Fatalf("GeneratePassword() contains non-hex character: %c", c)
		}
	}
}

func TestBasicAuthHeader(t *testing.T) {
	header := basicAuthHeader("test-pass")
	if !strings.HasPrefix(header, "Basic ") {
		t.Fatalf("basicAuthHeader() = %q, want prefix 'Basic '", header)
	}
	if header != "Basic b3BlbmNvZGU6dGVzdC1wYXNz" {
		t.Fatalf("basicAuthHeader() = %q, want Basic b3BlbmNvZGU6dGVzdC1wYXNz", header)
	}
}

func TestHealthCheckWithAuth_NoAuthServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	_, url := mockHealthServer(t)

	code := healthCheckWithAuth(ctx, url, "")
	if code != 200 {
		t.Fatalf("healthCheckWithAuth(no auth) = %d, want 200", code)
	}

	// With a password, an unauthenticated server should still accept it (no auth required).
	code = healthCheckWithAuth(ctx, url, "some-password")
	if code != 200 {
		t.Fatalf("healthCheckWithAuth(with password) = %d, want 200", code)
	}
}

func TestHealthCheckWithAuth_CorrectPassword(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	password := "test-secret-123"
	_, url := mockAuthHealthServer(t, password)

	code := healthCheckWithAuth(ctx, url, password)
	if code != 200 {
		t.Fatalf("healthCheckWithAuth(correct) = %d, want 200", code)
	}
}

func TestHealthCheckWithAuth_WrongPassword(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	password := "test-secret-123"
	_, url := mockAuthHealthServer(t, password)

	code := healthCheckWithAuth(ctx, url, "wrong-password")
	if code != 401 {
		t.Fatalf("healthCheckWithAuth(wrong) = %d, want 401", code)
	}
}

func TestHealthCheckWithAuth_NoPasswordWhenRequired(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	password := "test-secret-123"
	_, url := mockAuthHealthServer(t, password)

	code := healthCheckWithAuth(ctx, url, "")
	if code != 401 {
		t.Fatalf("healthCheckWithAuth(empty, required) = %d, want 401", code)
	}
}

func TestHealthCheckWithAuth_NonOpenCodeServer(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	_, url := mockNonOpenCodeServer(t)

	code := healthCheckWithAuth(ctx, url, "")
	if code == 200 {
		t.Fatal("healthCheckWithAuth(non-opencode) = 200, want non-200")
	}
}

func TestProbePortWithAuth_Mine(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	password := "my-password"
	_, url := mockAuthHealthServer(t, password)
	host, port := parseHostPort(t, url)

	result := probePortWithAuth(ctx, host, port, password)
	if result != authProbeMine {
		t.Fatalf("probePortWithAuth() = %d, want authProbeMine", result)
	}
}

func TestProbePortWithAuth_Foreign(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()
	password := "my-password"
	_, url := mockAuthHealthServer(t, password)
	host, port := parseHostPort(t, url)

	result := probePortWithAuth(ctx, host, port, "different-password")
	if result != authProbeForeign {
		t.Fatalf("probePortWithAuth() = %d, want authProbeForeign", result)
	}
}

func TestProbePortWithAuth_Absent(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	result := probePortWithAuth(ctx, "127.0.0.1", 59998, "any-password")
	if result != authProbeAbsent {
		t.Fatalf("probePortWithAuth() = %d, want authProbeAbsent", result)
	}
}

func TestManager_Ensure_GeneratesPassword(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	mgr, err := NewManager(Options{
		StateDir:      t.TempDir(),
		AutoStart:     false,
		PreferredPort: 59999,
		Hostname:      "127.0.0.1",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// AutoStart disabled + no server → error, but password should
	// still be generated and persisted.
	_, err = mgr.Ensure(ctx)
	if err == nil {
		t.Fatal("Ensure() error = nil, want error (no server, auto_start disabled)")
	}

	// Verify the password was persisted.
	state, err := mgr.(*manager).stateStore.load()
	if err != nil {
		t.Fatalf("load state: %v", err)
	}
	if state.Password == "" {
		t.Fatal("state.Password is empty after first Ensure; want generated password")
	}
}

func TestManager_Ensure_ReusesPassword(t *testing.T) {
	stateDir := t.TempDir()

	// First call: pre-populate a state with a known password.
	store, err := newStateStore(stateDir)
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}
	knownPassword, err := GeneratePassword()
	if err != nil {
		t.Fatalf("GeneratePassword() error = %v", err)
	}
	if err := store.save(State{
		Port:      4096,
		Password:  knownPassword,
		PID:       1,
		StartedAt: time.Now(),
		LastUsed:  time.Now(),
	}); err != nil {
		t.Fatalf("save state: %v", err)
	}

	// Second call: should reuse the password from state.
	mgr, err := NewManager(Options{
		StateDir:      stateDir,
		AutoStart:     false,
		PreferredPort: 59999,
		Hostname:      "127.0.0.1",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	// resolvePassword is called internally, which reuses from state.
	password, err := mgr.(*manager).resolvePassword()
	if err != nil {
		t.Fatalf("resolvePassword() error = %v", err)
	}
	if password != knownPassword {
		t.Fatalf("resolvePassword() = %q, want %q (reused from state)", password, knownPassword)
	}
}

func TestManager_Ensure_IdentityIsolation(t *testing.T) {
	// Simulate two users by using different state directories.
	// User A starts a server with auth. User B tries to probe the same port
	// but with a different password — it should detect this as "foreign"
	// and move to another port.
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)

	// User A: start on test port with password.
	dirA := t.TempDir()
	mgrA, err := NewManager(Options{
		StateDir:           dirA,
		AutoStart:          true,
		PreferredPort:      45990,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager(A) error = %v", err)
	}

	connA, err := mgrA.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure(A) error = %v", err)
	}
	if connA.Password == "" {
		t.Fatal("connA.Password is empty")
	}
	defer func() { _ = mgrA.Stop(ctx) }()

	_, portA := parseHostPort(t, connA.URL)

	// User B: different state dir, same preferred port. Should detect A's
	// server as "foreign" and try the next port (45991).
	dirB := t.TempDir()
	mgrB, err := NewManager(Options{
		StateDir:           dirB,
		AutoStart:          true,
		PreferredPort:      portA,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager(B) error = %v", err)
	}

	connB, err := mgrB.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure(B) error = %v", err)
	}
	defer func() { _ = mgrB.Stop(ctx) }()

	if connB.Password == "" {
		t.Fatal("connB.Password is empty")
	}

	// B should get a different port than A.
	_, portB := parseHostPort(t, connB.URL)
	if portB == portA {
		t.Fatalf("B got port %d, want different from A's port %d", portB, portA)
	}

	// B should NOT be able to use A's password.
	if connB.Password == connA.Password {
		t.Fatal("B's password matches A's; want different")
	}

	// B should NOT be able to auth against A's server.
	code := healthCheckWithAuth(ctx, connA.URL, connB.Password)
	if code == 200 {
		t.Fatal("B's password successfully authenticated against A's server; want 401")
	}
}

func TestManager_Ensure_ReusesExistingWithAuth(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	stateDir := t.TempDir()

	// Start a managed server.
	mgr1, err := NewManager(Options{
		StateDir:           stateDir,
		AutoStart:          true,
		PreferredPort:      45991,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	conn1, err := mgr1.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}
	if conn1.Password == "" {
		t.Fatal("conn1.Password is empty")
	}
	defer func() { _ = mgr1.Stop(ctx) }()

	// A second manager with the same state dir should detect and reuse the
	// server using the stored password.
	mgr2, err := NewManager(Options{
		StateDir:           stateDir,
		AutoStart:          true,
		PreferredPort:      45991,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}

	conn2, err := mgr2.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure() error = %v", err)
	}

	if conn2.URL != conn1.URL {
		t.Fatalf("conn2.URL = %q, want %q", conn2.URL, conn1.URL)
	}
	if conn2.Password != conn1.Password {
		t.Fatalf("conn2.Password = %q, want %q", conn2.Password, conn1.Password)
	}

	// Verify the second manager thinks the server is not managed by it.
	status := mgr2.Status(ctx)
	if status.Managed {
		t.Fatal("status.Managed = true, want false (reused, not spawned)")
	}
}

func TestManager_Ensure_StateRecoveryWithAuth(t *testing.T) {
	// When the server PID dies but the state file remains, Ensure should
	// detect the stale state and restart.
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	stateDir := t.TempDir()
	testPort := 45992

	// Pre-populate a stale state file pointing to a dead PID.
	store, err := newStateStore(stateDir)
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}
	oldPassword, err := GeneratePassword()
	if err != nil {
		t.Fatalf("GeneratePassword() error = %v", err)
	}
	if err := store.save(State{
		Port:      testPort,
		Password:  oldPassword,
		PID:       99998, // dead PID
		StartedAt: time.Now(),
		LastUsed:  time.Now(),
	}); err != nil {
		t.Fatalf("save state: %v", err)
	}

	mgr, err := NewManager(Options{
		StateDir:           stateDir,
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
	defer func() { _ = mgr.Stop(ctx) }()

	if conn.URL == "" {
		t.Fatal("conn.URL is empty")
	}
	// Password should have been reused from the stale state.
	if conn.Password != oldPassword {
		t.Fatalf("conn.Password = %q, want %q (reused from stale state)", conn.Password, oldPassword)
	}

	// The server should be healthy.
	if healthCheckWithAuth(ctx, conn.URL, conn.Password) != 200 {
		t.Fatal("recovered server is not healthy with auth")
	}
}

func TestManager_Ensure_ForeignPortSkip(t *testing.T) {
	// User A has a server on port 45993 with password-A.
	// User B has preferred port 45993 but different password.
	// B should skip 45993 (foreign) and start on 45994.
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)

	// User A starts on 45993.
	dirA := t.TempDir()
	mgrA, err := NewManager(Options{
		StateDir:           dirA,
		AutoStart:          true,
		PreferredPort:      45993,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager(A) error = %v", err)
	}

	connA, err := mgrA.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure(A) error = %v", err)
	}
	defer func() { _ = mgrA.Stop(ctx) }()
	_, portA := parseHostPort(t, connA.URL)

	// User B starts with preferred port = A's port.
	dirB := t.TempDir()
	mgrB, err := NewManager(Options{
		StateDir:           dirB,
		AutoStart:          true,
		PreferredPort:      portA,
		Hostname:           "127.0.0.1",
		StartupTimeout:     5 * time.Second,
		OpenCodeBinaryPath: bin,
	})
	if err != nil {
		t.Fatalf("NewManager(B) error = %v", err)
	}

	connB, err := mgrB.Ensure(ctx)
	if err != nil {
		t.Fatalf("Ensure(B) error = %v", err)
	}
	defer func() { _ = mgrB.Stop(ctx) }()

	_, portB := parseHostPort(t, connB.URL)
	if portB == portA {
		t.Fatalf("B's port = %d, want different from A's port %d (foreign skip)", portB, portA)
	}
	if connB.Password == connA.Password {
		t.Fatal("B's password matches A's; want different")
	}
}

func TestAutoStart_CoalesceLock(t *testing.T) {
	// Verify that the spawn lock file is created and cleaned up around
	// server spawning. Use a non-existent binary path to ensure autoStart
	// fails predictably.
	ctx, cancel := testCtx(t)
	defer cancel()

	stateDir := t.TempDir()
	mgr, err := NewManager(Options{
		StateDir:           stateDir,
		AutoStart:          true,
		PreferredPort:      59998,
		Hostname:           "127.0.0.1",
		StartupTimeout:     2 * time.Second,
		OpenCodeBinaryPath: "/nonexistent/opencode-binary",
	})
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}
	m := mgr.(*manager)

	// autoStart should fail (no binary) and clean up the lock.
	_, err = m.autoStart(ctx, "127.0.0.1", 59998, "test-pass")
	if err == nil {
		t.Fatal("autoStart() error = nil, want error (no binary)")
	}

	// Verify the lock file was cleaned up.
	lockPath := filepath.Join(stateDir, "server.lock")
	if _, statErr := os.Stat(lockPath); !os.IsNotExist(statErr) {
		t.Fatal("lock file still exists after autoStart returned")
	}
}

func TestManager_Ensure_PasswordInConnection(t *testing.T) {
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	stateDir := t.TempDir()

	mgr, err := NewManager(Options{
		StateDir:           stateDir,
		AutoStart:          true,
		PreferredPort:      45995,
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
	defer func() { _ = mgr.Stop(ctx) }()

	if conn.Password == "" {
		t.Fatal("conn.Password is empty; want non-empty password")
	}

	// Verify the password actually works for auth.
	code := healthCheckWithAuth(ctx, conn.URL, conn.Password)
	if code != 200 {
		t.Fatalf("healthCheckWithAuth() = %d, want 200", code)
	}

	// Wrong password should get 401.
	code = healthCheckWithAuth(ctx, conn.URL, "wrong-password")
	if code != 401 {
		t.Fatalf("healthCheckWithAuth(wrong) = %d, want 401", code)
	}
}

func TestStealStaleLock_DeadPID(t *testing.T) {
	// A lock file whose PID is no longer alive should be stolen (removed).
	stateDir := t.TempDir()
	lockPath := filepath.Join(stateDir, lockFileName)
	// Write a PID that is guaranteed to not exist.
	if err := os.WriteFile(lockPath, []byte("999989"), 0o600); err != nil {
		t.Fatalf("write stale lock: %v", err)
	}
	if !stealStaleLock(lockPath) {
		t.Fatal("stealStaleLock() = false, want true (dead PID)")
	}
	if _, err := os.Stat(lockPath); !os.IsNotExist(err) {
		t.Fatal("stale lock file still exists after steal")
	}
}

func TestStealStaleLock_LivePID(t *testing.T) {
	// A lock file whose PID is alive should NOT be stolen.
	stateDir := t.TempDir()
	lockPath := filepath.Join(stateDir, lockFileName)
	if err := os.WriteFile(lockPath, []byte(strconv.Itoa(os.Getpid())), 0o600); err != nil {
		t.Fatalf("write live lock: %v", err)
	}
	if stealStaleLock(lockPath) {
		t.Fatal("stealStaleLock() = true, want false (live PID)")
	}
	if _, err := os.Stat(lockPath); err != nil {
		t.Fatalf("live lock file removed unexpectedly: %v", err)
	}
}

func TestStealStaleLock_CorruptContent(t *testing.T) {
	// A corrupt lock file (non-numeric content) should be treated as stale.
	stateDir := t.TempDir()
	lockPath := filepath.Join(stateDir, lockFileName)
	if err := os.WriteFile(lockPath, []byte("not-a-pid"), 0o600); err != nil {
		t.Fatalf("write corrupt lock: %v", err)
	}
	if !stealStaleLock(lockPath) {
		t.Fatal("stealStaleLock() = false, want true (corrupt content)")
	}
}

func TestAutoStart_RecoversFromStaleLock(t *testing.T) {
	// When a stale lock file (dead PID) is present, autoStart should detect
	// it, steal the lock, and proceed to spawn the server normally.
	ctx, cancel := testCtx(t)
	defer cancel()

	bin := mockOpenCodeBinary(t)
	stateDir := t.TempDir()
	lockPath := filepath.Join(stateDir, lockFileName)

	// Pre-create a stale lock with a dead PID.
	if err := os.WriteFile(lockPath, []byte("999989"), 0o600); err != nil {
		t.Fatalf("write stale lock: %v", err)
	}

	mgr, err := NewManager(Options{
		StateDir:           stateDir,
		AutoStart:          true,
		PreferredPort:      45996,
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
	defer func() { _ = mgr.Stop(ctx) }()

	if conn.Password == "" {
		t.Fatal("conn.Password is empty")
	}
	if healthCheckWithAuth(ctx, conn.URL, conn.Password) != 200 {
		t.Fatal("server not healthy after stale-lock recovery")
	}

	// The lock file should have been cleaned up after successful spawn.
	if _, err := os.Stat(lockPath); !os.IsNotExist(err) {
		t.Fatal("lock file still exists after successful autoStart")
	}
}
