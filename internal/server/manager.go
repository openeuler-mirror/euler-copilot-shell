package server

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	// lockRetryDelay is how long to wait before retrying discovery when
	// another process holds the spawn lock.
	lockRetryDelay = 500 * time.Millisecond

	// lockRetryAttempts is how many times to retry discovery when the
	// spawn lock is held by another process.
	lockRetryAttempts = 10

	// lockFileName is the name of the coalesce lock file in StateDir.
	lockFileName = "server.lock"
)

// manager implements Manager.
type manager struct {
	opts       Options
	stateStore *stateStore
	mu         sync.Mutex
	managedPID int // non-zero when this process started the server; guarded by mu
	idleCancel context.CancelFunc
}

// idleMonitorCheckInterval returns the interval at which the idle monitor
// checks the state. It is a fraction of the idle timeout, capped at 5
// minutes to avoid excessive wait time for long timeouts.
func idleMonitorCheckInterval(timeout time.Duration) time.Duration {
	interval := timeout / 6
	if interval < 100*time.Millisecond {
		interval = 100 * time.Millisecond
	}
	if interval > 5*time.Minute {
		interval = 5 * time.Minute
	}
	return interval
}

// NewManager creates a new server lifecycle Manager. If opts.IdleTimeout is
// positive, a background goroutine monitors idle state and automatically
// stops the server when the timeout is exceeded.
func NewManager(opts Options) (Manager, error) {
	stateDir := opts.StateDir
	if stateDir == "" {
		return nil, fmt.Errorf("StateDir is required")
	}
	store, err := newStateStore(stateDir)
	if err != nil {
		return nil, fmt.Errorf("create server state store: %w", err)
	}
	m := &manager{
		opts:       opts,
		stateStore: store,
	}
	if opts.IdleTimeout > 0 {
		ctx, cancel := context.WithCancel(context.Background())
		m.idleCancel = cancel
		go m.idleMonitor(ctx)
	}
	return m, nil
}

// Ensure implements Manager.
func (m *manager) Ensure(ctx context.Context) (Connection, error) {
	if err := ctx.Err(); err != nil {
		return Connection{}, err
	}

	host := m.hostname()
	preferredPort := m.opts.PreferredPort
	if preferredPort <= 0 {
		preferredPort = defaultPort
	}
	defaultConn := Connection{URL: fmt.Sprintf("http://%s:%d", host, preferredPort)}

	// Resolve the password: load from state or generate a new one.
	password, err := m.resolvePassword()
	if err != nil {
		return Connection{}, fmt.Errorf("resolve server password: %w", err)
	}

	// 1. Fast path: recover from existing state file with auth verification.
	state, err := m.stateStore.load()
	if err != nil {
		return Connection{}, fmt.Errorf("load server state: %w", err)
	}

	// Lazy idle cleanup: if an idle timeout is configured and the recorded
	// last_used has expired, stop the stale server before continuing. The
	// transport layer now refreshes last_used on each request, so this check
	// only fires when the server has genuinely been idle (e.g. CLI mode where
	// each invocation is a separate process). A failure to stop the old server
	// is non-fatal: we warn and proceed with normal startup.
	if m.opts.IdleTimeout > 0 && state.Port > 0 && !state.LastUsed.IsZero() {
		if time.Since(state.LastUsed) > m.opts.IdleTimeout {
			_ = m.Stop(ctx)
			// Reload state after stop (it removes the state file on success).
			state, err = m.stateStore.load()
			if err != nil {
				return Connection{}, fmt.Errorf("load server state after idle cleanup: %w", err)
			}
		}
	}

	if state.Port > 0 && isPIDAlive(state.PID) {
		if probePortWithAuth(ctx, host, state.Port, password) == authProbeMine {
			baseURL := fmt.Sprintf("http://%s:%d", host, state.Port)
			return Connection{URL: baseURL, Password: password}, nil
		}
		// PID is alive but auth check failed (401 or unreachable).
		// State is stale; remove it.
		_ = m.stateStore.remove()
	} else if state.Port > 0 {
		// PID is dead → stale state.
		_ = m.stateStore.remove()
	}

	// 2. Scan for an existing server with auth awareness.
	// Try the state's saved port first, then the preferred port, then scan.
	if state.Port > 0 && state.Port != preferredPort {
		if conn, ok := m.tryReusePort(ctx, host, state.Port, password); ok {
			return conn, nil
		}
	}

	if conn, ok := m.tryReusePort(ctx, host, preferredPort, password); ok {
		return conn, nil
	}

	// Scan remaining ports in range for an existing server (no spawn).
	if conn, ok := m.scanForExisting(ctx, host, preferredPort, password); ok {
		return conn, nil
	}

	// 3. No existing server found.
	if !m.opts.AutoStart {
		return Connection{}, fmt.Errorf(
			"no opencode server found on %s:%d and auto_start is disabled; "+
				"start one with 'opencode serve --port %d' or enable auto_start in config",
			host, preferredPort, preferredPort)
	}

	// 4. Auto-start: spawn with coalesce protection. If the opencode binary is
	// not in PATH, surface an explicit error (the user must install it). Other
	// startup failures (port conflict, health timeout) fall back to the default
	// URL for backward compatibility.
	conn, err := m.autoStart(ctx, host, preferredPort, password)
	if err != nil {
		// Distinguish "binary not found" (a configuration problem the user
		// must fix) from transient startup failures (port conflict, health
		// timeout) which fall back to the default URL.
		if errors.Is(err, exec.ErrNotFound) || errors.Is(err, fs.ErrNotExist) {
			return Connection{}, fmt.Errorf("auto-start opencode server: %w (install opencode or set server.auto_start=false and start it manually)", ErrOpenCodeBinaryNotFound)
		}
		return defaultConn, nil
	}
	return conn, nil
}

// resolvePassword returns the password to use. When no password exists in the
// saved state, it generates a new one and persists it immediately. This ensures
// the password survives across Ensure calls even before a server is spawned.
func (m *manager) resolvePassword() (string, error) {
	state, err := m.stateStore.load()
	if err != nil {
		return "", err
	}
	if state.Password != "" {
		return state.Password, nil
	}
	password, err := GeneratePassword()
	if err != nil {
		return "", err
	}
	// Persist the password immediately.
	state.Password = password
	_ = m.stateStore.save(state)
	return password, nil
}

// tryReusePort probes a single port. If the server there accepts our password
// (or requires none), it reuses it and persists the state.
func (m *manager) tryReusePort(ctx context.Context, host string, port int, password string) (Connection, bool) {
	result := probePortWithAuth(ctx, host, port, password)
	if result != authProbeMine {
		return Connection{}, false
	}
	baseURL := fmt.Sprintf("http://%s:%d", host, port)
	newState := State{
		Port:      port,
		Password:  password,
		StartedAt: time.Now(),
		LastUsed:  time.Now(),
	}
	_ = m.stateStore.save(newState)
	return Connection{URL: baseURL, Password: password}, true
}

// scanForExisting probes ports in [startPort+1..endPort] for an existing
// opencode server that accepts our password. It does NOT spawn new servers.
// When it encounters a port with a foreign server (401), it skips it.
func (m *manager) scanForExisting(ctx context.Context, host string, startPort int, password string) (Connection, bool) {
	endPort := portRangeEnd(startPort)

	for port := startPort + 1; port <= endPort; port++ {
		select {
		case <-ctx.Done():
			return Connection{}, false
		default:
		}

		result := probePortWithAuth(ctx, host, port, password)
		if result == authProbeMine {
			baseURL := fmt.Sprintf("http://%s:%d", host, port)
			newState := State{
				Port:      port,
				Password:  password,
				StartedAt: time.Now(),
				LastUsed:  time.Now(),
			}
			_ = m.stateStore.save(newState)
			return Connection{URL: baseURL, Password: password}, true
		}
		// authProbeForeign → someone else's server, skip
		// authProbeAbsent → port closed or not opencode, skip
	}

	return Connection{}, false
}

// acquireSpawnLock tries to create the lock file with O_EXCL, writing the
// current PID into it so other processes can detect stale locks. It returns
// the open file handle (caller must Close + Remove it) or an error.
func acquireSpawnLock(lockPath string) (*os.File, error) {
	f, err := os.OpenFile(lockPath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0o600)
	if err != nil {
		return nil, err
	}
	// Write our PID so holders can be liveness-checked.
	if _, werr := f.WriteString(strconv.Itoa(os.Getpid())); werr != nil {
		_ = f.Close()
		_ = os.Remove(lockPath)
		return nil, fmt.Errorf("write spawn lock pid: %w", werr)
	}
	return f, nil
}

// stealStaleLock removes the lock file when its owning PID is no longer alive.
// It returns true when the stale lock was removed (caller may re-acquire).
func stealStaleLock(lockPath string) bool {
	data, err := os.ReadFile(lockPath)
	if err != nil {
		return false
	}
	pid, err := strconv.Atoi(string(data))
	if err != nil || pid <= 0 {
		// Corrupt lock file; treat as stale.
		_ = os.Remove(lockPath)
		return true
	}
	if isPIDAlive(pid) {
		return false // owner still running
	}
	_ = os.Remove(lockPath)
	return true
}

// autoStart attempts to start a new server with coalesce protection. It scans
// the port range for a free port, acquires the spawn lock, and starts the
// server. Returns an error if spawning fails (caller should fall back).
func (m *manager) autoStart(ctx context.Context, host string, preferredPort int, password string) (Connection, error) {
	lockPath := filepath.Join(m.opts.StateDir, lockFileName)
	f, err := acquireSpawnLock(lockPath)
	if err != nil {
		if !os.IsExist(err) {
			return Connection{}, fmt.Errorf("acquire spawn lock: %w", err)
		}
		// Another process holds the lock. It might be alive (coalesce) or
		// stale (crashed holder). Steal stale locks immediately.
		if stealStaleLock(lockPath) {
			f, err = acquireSpawnLock(lockPath)
			if err == nil {
				goto spawn
			}
			if !os.IsExist(err) {
				return Connection{}, fmt.Errorf("acquire spawn lock: %w", err)
			}
		}
		// Lock is held by a live process. Wait briefly and retry discovery
		// in case the other process started a server.
		for i := 0; i < lockRetryAttempts; i++ {
			select {
			case <-ctx.Done():
				return Connection{}, ctx.Err()
			case <-time.After(lockRetryDelay):
			}
			if conn, ok := m.tryReusePort(ctx, host, preferredPort, password); ok {
				return conn, nil
			}
			// Check if the lock was released or went stale.
			if stealStaleLock(lockPath) {
				f, err = acquireSpawnLock(lockPath)
				if err == nil {
					goto spawn
				}
				if !os.IsExist(err) {
					return Connection{}, fmt.Errorf("acquire spawn lock: %w", err)
				}
			} else if _, statErr := os.Stat(lockPath); os.IsNotExist(statErr) {
				// Lock released normally but no server found.
				f, err = acquireSpawnLock(lockPath)
				if err == nil {
					goto spawn
				}
			}
		}
		return Connection{}, fmt.Errorf("timed out waiting for another witty process to start the server")
	}

spawn:
	defer func() {
		name := f.Name()
		_ = f.Close()
		_ = os.Remove(name)
	}()

	// We hold the lock. Find a free port and spawn.
	endPort := portRangeEnd(preferredPort)
	for port := preferredPort; port <= endPort; port++ {
		select {
		case <-ctx.Done():
			return Connection{}, ctx.Err()
		default:
		}

		// Check port status under the lock.
		result := probePortWithAuth(ctx, host, port, password)
		switch result {
		case authProbeMine:
			// Someone started a server while we waited for the lock.
			baseURL := fmt.Sprintf("http://%s:%d", host, port)
			newState := State{
				Port:      port,
				Password:  password,
				StartedAt: time.Now(),
				LastUsed:  time.Now(),
			}
			_ = m.stateStore.save(newState)
			return Connection{URL: baseURL, Password: password}, nil
		case authProbeForeign:
			// Another user's server; skip this port.
			continue
		case authProbeAbsent:
			if portOpen(ctx, host, port) {
				// Port occupied by non-opencode; skip.
				continue
			}
		}

		// Port is free. Spawn the server.
		proc, err := m.startServer(ctx, port, password)
		if err != nil {
			return Connection{}, fmt.Errorf("start server on port %d: %w", port, err)
		}

		m.mu.Lock()
		m.managedPID = proc.Pid
		m.mu.Unlock()
		baseURL := fmt.Sprintf("http://%s:%d", host, port)

		newState := State{
			Port:      port,
			Password:  password,
			PID:       proc.Pid,
			StartedAt: time.Now(),
			LastUsed:  time.Now(),
		}
		// Non-fatal: the server is running; we just can't persist the
		// state. The next witty invocation will probe and rediscover it.
		_ = m.stateStore.save(newState)

		return Connection{URL: baseURL, Password: password}, nil
	}

	return Connection{}, fmt.Errorf("no free port in range %d-%d", preferredPort, endPort)
}

// ErrOpenCodeBinaryNotFound is returned by Ensure when the opencode binary is
// not found in PATH and auto_start is enabled. Unlike other startup failures
// (port conflict, health timeout) this is a configuration problem the user
// must fix, so Ensure surfaces it as an error rather than silently degrading.
var ErrOpenCodeBinaryNotFound = errors.New("opencode binary not found")

// stopSignalTimeout is the maximum time Stop waits for a SIGTERM'd process
// to exit before giving up.
const stopSignalTimeout = 5 * time.Second

// Stop implements Manager. It reads the state file to obtain the server URL,
// password and PID, then prefers POST /global/dispose for graceful shutdown.
// Because some opencode versions acknowledge /global/dispose (200) without
// actually stopping the HTTP listener, Stop verifies the server is gone after
// dispose and falls back to SIGTERM if it is still reachable. When HTTP is
// unreachable it falls back to SIGTERM against the recorded PID, after
// verifying the PID's command line looks like an opencode server. The
// managedPID precondition is intentionally removed so any witty process that
// holds the state file password can stop the server.
func (m *manager) Stop(ctx context.Context) error {
	// Cancel the idle monitor so it doesn't race with us.
	m.mu.Lock()
	if m.idleCancel != nil {
		m.idleCancel()
		m.idleCancel = nil
	}
	m.managedPID = 0
	m.mu.Unlock()

	state, err := m.stateStore.load()
	if err != nil {
		return fmt.Errorf("load server state: %w", err)
	}
	// Nothing to stop: no recorded server.
	if state.Port == 0 && state.PID == 0 {
		return nil
	}

	baseURL := fmt.Sprintf("http://%s:%d", m.hostname(), state.Port)
	host := m.hostname()

	// 1. Prefer the graceful /global/dispose API. Some opencode versions
	// return 200 without actually stopping the listener, so verify the
	// server is unreachable afterwards; if it is still alive, fall through
	// to the SIGTERM fallback.
	if disposeErr := disposeViaHTTP(ctx, baseURL, state.Password); disposeErr == nil {
		// Give the server a brief moment to shut down its listener.
		time.Sleep(200 * time.Millisecond)
		if !serverStillReachable(ctx, host, state.Port, state.Password) {
			_ = m.stateStore.remove()
			return nil
		}
		// Dispose acknowledged but server is still reachable; fall back to
		// SIGTERM against the recorded PID.
	}

	// 2. Fallback: SIGTERM against the recorded PID.
	if state.PID <= 0 {
		// No PID to signal and dispose failed; the server is either foreign
		// or already gone. Clean up local state and report nothing to stop.
		_ = m.stateStore.remove()
		return nil
	}
	if !isPIDAlive(state.PID) {
		// Process already exited; clean up stale state.
		_ = m.stateStore.remove()
		return nil
	}
	if !pidIsOpenCodeServer(state.PID) {
		// PID reuse risk: the recorded PID now belongs to an unrelated process.
		_ = m.stateStore.remove()
		return fmt.Errorf("server stop: pid %d is no longer an opencode server (possible PID reuse); state file removed", state.PID)
	}

	proc, err := os.FindProcess(state.PID)
	if err != nil {
		return fmt.Errorf("find server process %d: %w", state.PID, err)
	}
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		return fmt.Errorf("stop server process %d: %w", state.PID, err)
	}
	if err := waitForProcessExit(state.PID, stopSignalTimeout); err != nil {
		return fmt.Errorf("wait for server process %d exit: %w", state.PID, err)
	}
	_ = m.stateStore.remove()
	return nil
}

// Status implements Manager.
func (m *manager) Status(ctx context.Context) Status {
	state, err := m.stateStore.load()
	if err != nil {
		return Status{}
	}
	host := m.hostname()
	var running bool
	if state.Port > 0 {
		if state.Password != "" {
			running = healthCheckWithAuth(ctx, fmt.Sprintf("http://%s:%d", host, state.Port), state.Password) == http.StatusOK
		} else {
			running = findOpenCodeOnPort(ctx, host, state.Port)
		}
	}

	m.mu.Lock()
	managedPID := m.managedPID
	m.mu.Unlock()

	return Status{
		Running:   running,
		Port:      state.Port,
		PID:       state.PID,
		Managed:   state.PID == managedPID && managedPID > 0,
		StartedAt: state.StartedAt.Format(time.RFC3339),
	}
}

// TouchLastUsed implements Manager. It refreshes the state file's last_used
// timestamp so the idle timeout does not fire during active use. Errors are
// ignored (best-effort); a missing state file is a no-op.
func (m *manager) TouchLastUsed() {
	state, err := m.stateStore.load()
	if err != nil || state.Port == 0 {
		return
	}
	state.LastUsed = time.Now()
	_ = m.stateStore.save(state)
}

// Close implements Manager. It cancels the idle monitor context so the
// background goroutine exits. It is idempotent and safe to call multiple times.
func (m *manager) Close() {
	m.mu.Lock()
	if m.idleCancel != nil {
		m.idleCancel()
		m.idleCancel = nil
	}
	m.mu.Unlock()
}

// idleMonitor periodically checks whether the managed server has been idle
// longer than the configured timeout. When idle timeout is exceeded, it
// stops the server automatically.
func (m *manager) idleMonitor(ctx context.Context) {
	interval := idleMonitorCheckInterval(m.opts.IdleTimeout)
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
		}

		state, err := m.stateStore.load()
		if err != nil || state.LastUsed.IsZero() {
			continue
		}

		if time.Since(state.LastUsed) <= m.opts.IdleTimeout {
			continue
		}

		// Server has been idle too long. Stop it only if we manage it.
		m.mu.Lock()
		if m.managedPID <= 0 {
			m.mu.Unlock()
			return // no longer managing anything; exit
		}
		m.mu.Unlock()

		// Use a background context to stop; the idle monitor's ctx is
		// only for cancellation signaling, not Stop's timeout.
		_ = m.Stop(context.Background())
		return
	}
}

// disposeViaHTTP calls POST {baseURL}/global/dispose with HTTP Basic Auth.
// It returns nil on a 200 response and a non-nil error otherwise (connection
// refused, timeout, non-200 status). Callers use a nil error to decide the
// graceful shutdown succeeded and fall back to SIGTERM otherwise.
func disposeViaHTTP(ctx context.Context, baseURL, password string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+"/global/dispose", nil)
	if err != nil {
		return fmt.Errorf("build dispose request: %w", err)
	}
	req.Header.Set("Accept", "application/json")
	if password != "" {
		req.Header.Set("Authorization", basicAuthHeader(password))
	}
	client := &http.Client{Timeout: portProbeTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("dispose request: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("dispose returned status %d", resp.StatusCode)
	}
	return nil
}

// serverStillReachable reports whether an opencode server is still responding
// on the given host:port. It is used after /global/dispose to verify the
// server actually stopped, since some opencode versions acknowledge dispose
// without shutting down the HTTP listener.
func serverStillReachable(ctx context.Context, host string, port int, password string) bool {
	if password != "" {
		return healthCheckWithAuth(ctx, fmt.Sprintf("http://%s:%d", host, port), password) == http.StatusOK
	}
	return findOpenCodeOnPort(ctx, host, port)
}

// pidIsOpenCodeServer reports whether the process identified by pid appears
// to be an opencode server, by inspecting /proc/{pid}/cmdline. This mitigates
// PID-reuse risk before sending SIGTERM. On platforms without /proc (e.g.
// macOS used for development), the check cannot be performed and the function
// returns true so SIGTERM fallback remains usable; the delivery platform
// (openEuler/Linux) always has /proc and verifies the command line.
func pidIsOpenCodeServer(pid int) bool {
	data, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
	if err != nil {
		// /proc unavailable (non-Linux dev) or PID gone. Be permissive to
		// keep the fallback working outside Linux; openEuler always verifies.
		return true
	}
	// /proc/{pid}/cmdline is null-byte separated.
	cmdline := strings.ReplaceAll(string(data), "\x00", " ")
	return strings.Contains(cmdline, "opencode")
}

// waitForProcessExit polls isPIDAlive until the process exits or the timeout
// elapses. It returns nil when the process has exited and a context-style
// error when the timeout is reached.
func waitForProcessExit(pid int, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for {
		if !isPIDAlive(pid) {
			return nil
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("process %d did not exit within %s", pid, timeout)
		}
		time.Sleep(100 * time.Millisecond)
	}
}
