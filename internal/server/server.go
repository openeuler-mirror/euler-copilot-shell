// Package server manages the opencode serve process lifecycle: start, detect,
// reuse, and stop. It ensures a reachable opencode server is available before
// the Witty transport layer is initialized.
package server

import (
	"context"
	"time"
)

// Manager manages the opencode serve process lifecycle.
type Manager interface {
	// Ensure ensures a server is available. If an existing server is reachable,
	// it returns its connection info; otherwise it starts a new server process.
	Ensure(ctx context.Context) (Connection, error)

	// Stop stops the server process managed by this Manager. If the server was
	// not started by the current witty process (recovered from state file), it
	// is a no-op.
	Stop(ctx context.Context) error

	// Status returns the current server status for diagnostics.
	Status(ctx context.Context) Status
}

// Connection describes a reachable server.
type Connection struct {
	URL      string // full URL, e.g. http://127.0.0.1:4097
	Password string // HTTP Basic Auth password (auto-generated; empty when the server requires no auth)
}

// Status describes the server runtime state.
type Status struct {
	Running   bool   // whether the server is running
	Port      int    // listening port
	PID       int    // process ID (zero if not managed by this process)
	Managed   bool   // whether this witty process started the server
	StartedAt string // server start time
}

// Options configures the Manager.
type Options struct {
	// StateDir is the directory where server-state.json is stored.
	// Defaults to the Witty config directory under the user's home.
	StateDir string

	// AutoStart controls whether the Manager automatically starts a server
	// when none is found. When false, Ensure returns an error if no server
	// is reachable.
	AutoStart bool

	// PreferredPort is the preferred listening port. 0 means auto-select
	// (start from 4096).
	PreferredPort int

	// Hostname is the bind address for the server.
	Hostname string

	// StartupTimeout is the maximum time to wait for the server to become
	// healthy after starting it.
	StartupTimeout time.Duration

	// OpenCodeBinaryPath is the path to the opencode binary.
	// Defaults to "opencode" (look up in PATH).
	OpenCodeBinaryPath string
}
