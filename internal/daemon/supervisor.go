// Package daemon implements the wittyd background service that manages the
// opencode server lifecycle: startup, health monitoring, idle timeout, and
// configuration-triggered restarts.
package daemon

import (
	"context"
	"fmt"
	"sync"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/server"
)

// Supervisor wraps a server.Manager and provides the daemon with a
// consistent interface for managing the opencode server lifecycle.
type Supervisor struct {
	mu       sync.RWMutex
	mgr      server.Manager
	conn     server.Connection
	running  bool
	lastUsed time.Time
}

// SupervisorOptions configures the Supervisor.
type SupervisorOptions struct {
	// StateDir is the directory where server-state.json resides.
	StateDir string
	// Hostname is the bind address for the opencode server.
	Hostname string
	// PreferredPort is the preferred listening port (0 = auto-select).
	PreferredPort int
	// StartupTimeout is how long to wait for the server to become healthy.
	StartupTimeout time.Duration
}

// NewSupervisor creates a Supervisor. It does not start the server; call
// Start() to begin managing the opencode server.
func NewSupervisor(opts SupervisorOptions) (*Supervisor, error) {
	mgr, err := server.NewManager(server.Options{
		StateDir:           opts.StateDir,
		AutoStart:          true,
		PreferredPort:      opts.PreferredPort,
		Hostname:           opts.Hostname,
		StartupTimeout:     opts.StartupTimeout,
		IdleTimeout:        0, // daemon handles idle timeout itself
		OpenCodeBinaryPath: "opencode",
	})
	if err != nil {
		return nil, fmt.Errorf("create server manager: %w", err)
	}
	return &Supervisor{mgr: mgr}, nil
}

// Start ensures the opencode server is running. It is idempotent.
func (s *Supervisor) Start(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.running {
		return nil
	}

	conn, err := s.mgr.Ensure(ctx)
	if err != nil {
		return fmt.Errorf("start opencode server: %w", err)
	}
	s.conn = conn
	s.running = true
	return nil
}

// Stop shuts down the opencode server gracefully (via /global/dispose) with
// SIGTERM fallback. It is idempotent.
func (s *Supervisor) Stop(ctx context.Context) error {
	s.mu.Lock()
	if !s.running {
		s.mu.Unlock()
		return nil
	}
	s.running = false
	s.mu.Unlock()

	if err := s.mgr.Stop(ctx); err != nil {
		return fmt.Errorf("stop opencode server: %w", err)
	}
	return nil
}

// Restart stops the current server and starts a fresh one. Use this after
// configuration changes so the server picks up new settings.
func (s *Supervisor) Restart(ctx context.Context) (server.Connection, error) {
	if err := s.Stop(ctx); err != nil {
		return server.Connection{}, fmt.Errorf("restart: stop: %w", err)
	}
	if err := s.Start(ctx); err != nil {
		return server.Connection{}, fmt.Errorf("restart: start: %w", err)
	}
	return s.Connection(), nil
}

// Connection returns the current server connection info. Returns zero value
// if the server has not been started.
func (s *Supervisor) Connection() server.Connection {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.conn
}

// Status returns the current server runtime status from the state file.
func (s *Supervisor) Status(ctx context.Context) server.Status {
	return s.mgr.Status(ctx)
}

// TouchLastUsed refreshes the last_used timestamp in the state file so that
// idle timeout does not fire during active use.
func (s *Supervisor) TouchLastUsed() {
	s.mgr.TouchLastUsed()
	s.mu.Lock()
	s.lastUsed = time.Now()
	s.mu.Unlock()
}

// LastUsed returns the time of the last activity, or the zero value if
// TouchLastUsed has never been called.
func (s *Supervisor) LastUsed() time.Time {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastUsed
}

// Close releases resources held by the underlying server manager.
func (s *Supervisor) Close() {
	s.mgr.Close()
}
