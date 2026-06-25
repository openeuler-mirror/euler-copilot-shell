package server

import (
	"context"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
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
	managedPID int // non-zero when this process started the server
}

// NewManager creates a new server lifecycle Manager.
func NewManager(opts Options) (Manager, error) {
	stateDir := opts.StateDir
	if stateDir == "" {
		return nil, fmt.Errorf("StateDir is required")
	}
	store, err := newStateStore(stateDir)
	if err != nil {
		return nil, fmt.Errorf("create server state store: %w", err)
	}
	return &manager{
		opts:       opts,
		stateStore: store,
	}, nil
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

	if state.Port > 0 && isPIDAlive(state.PID) {
		if probePortWithAuth(ctx, host, state.Port, password) == authProbeMine {
			baseURL := fmt.Sprintf("http://%s:%d", host, state.Port)
			m.touchLastUsed(state)
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

	// 4. Auto-start: spawn with coalesce protection. If spawning fails
	// (e.g. binary not found, port conflict), fall back to the default URL
	// for backward compatibility.
	conn, err := m.autoStart(ctx, host, preferredPort, password)
	if err != nil {
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

		m.managedPID = proc.Pid
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

// Stop implements Manager.
func (m *manager) Stop(ctx context.Context) error {
	if m.managedPID <= 0 {
		return nil
	}
	proc, err := os.FindProcess(m.managedPID)
	if err != nil {
		return fmt.Errorf("find managed process %d: %w", m.managedPID, err)
	}
	if err := proc.Signal(syscall.SIGTERM); err != nil {
		return fmt.Errorf("stop server process %d: %w", m.managedPID, err)
	}
	m.managedPID = 0
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

	return Status{
		Running:   running,
		Port:      state.Port,
		PID:       state.PID,
		Managed:   state.PID == m.managedPID && m.managedPID > 0,
		StartedAt: state.StartedAt.Format(time.RFC3339),
	}
}

// touchLastUsed updates the last_used timestamp without changing other fields.
func (m *manager) touchLastUsed(state State) {
	state.LastUsed = time.Now()
	_ = m.stateStore.save(state)
}
