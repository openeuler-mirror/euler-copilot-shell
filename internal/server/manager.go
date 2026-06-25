package server

import (
	"context"
	"fmt"
	"os"
	"syscall"
	"time"
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

	// 1. Try to recover from existing state file.
	state, err := m.stateStore.load()
	if err != nil {
		return Connection{}, fmt.Errorf("load server state: %w", err)
	}

	if state.Port > 0 {
		// PID-based fast path: if the PID is alive, quickly verify the
		// server is still reachable.
		if isPIDAlive(state.PID) {
			baseURL := fmt.Sprintf("http://%s:%d", host, state.Port)
			if healthCheck(ctx, baseURL) {
				m.touchLastUsed(state)
				return Connection{URL: baseURL, Password: state.Password}, nil
			}
		}
		// State is stale: remove it and fall through to fresh discovery.
		_ = m.stateStore.remove()
	}

	// 2. Probe for an existing server on the preferred port (or default).
	if findOpenCodeOnPort(ctx, host, preferredPort) {
		baseURL := fmt.Sprintf("http://%s:%d", host, preferredPort)
		newState := State{
			Port:      preferredPort,
			StartedAt: time.Now(),
			LastUsed:  time.Now(),
		}
		_ = m.stateStore.save(newState)
		return Connection{URL: baseURL}, nil
	}

	// 3. No server found. If auto-start is disabled, report the error.
	if !m.opts.AutoStart {
		return Connection{}, fmt.Errorf(
			"no opencode server found on %s:%d and auto_start is disabled; "+
				"start one with 'opencode serve --port %d' or enable auto_start in config",
			host, preferredPort, preferredPort)
	}

	// 4. Auto-start: find an available port and spawn the server.
	port, err := findAvailablePort(ctx, host, preferredPort)
	if err != nil {
		// Cannot find a free port in range. Fall back to the default
		// URL so commands that don't need a server (like 'init bash')
		// still work. The caller will get a connection error when
		// actually using the transport.
		return defaultConn, nil
	}

	proc, err := m.startServer(ctx, port)
	if err != nil {
		// Failed to start the server (e.g. binary not in PATH).
		// Fall back to the default URL for backward compatibility.
		return defaultConn, nil
	}

	m.managedPID = proc.Pid
	baseURL := fmt.Sprintf("http://%s:%d", host, port)

	newState := State{
		Port:      port,
		PID:       proc.Pid,
		StartedAt: time.Now(),
		LastUsed:  time.Now(),
	}
	if err := m.stateStore.save(newState); err != nil {
		// Non-fatal: the server is running; we just can't persist the
		// state. The next witty invocation will probe and rediscover it.
	}

	return Connection{URL: baseURL}, nil
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
	running := state.Port > 0 && findOpenCodeOnPort(ctx, host, state.Port)

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
