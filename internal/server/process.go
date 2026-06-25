package server

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"syscall"
	"time"
)

const (
	defaultPort         = 4096
	maxPort             = 4105 // 4096 + 10 - 1
	defaultHostname     = "127.0.0.1"
	defaultStartupWait  = 10 * time.Second
	healthCheckInterval = 200 * time.Millisecond
	openCodeBinary      = "opencode"
)

func (m *manager) binaryPath() string {
	if m.opts.OpenCodeBinaryPath != "" {
		return m.opts.OpenCodeBinaryPath
	}
	return openCodeBinary
}

func (m *manager) hostname() string {
	if m.opts.Hostname != "" {
		return m.opts.Hostname
	}
	return defaultHostname
}

func (m *manager) startupTimeout() time.Duration {
	if m.opts.StartupTimeout > 0 {
		return m.opts.StartupTimeout
	}
	return defaultStartupWait
}

// portRangeEnd returns the end of the port scanning range starting from
// startPort. It ensures at least (maxPort - defaultPort + 1) ports are
// scanned regardless of the starting port.
func portRangeEnd(startPort int) int {
	portRange := maxPort - defaultPort // 9, so 10 ports total with inclusive bounds
	if startPort <= maxPort {
		return maxPort
	}
	return startPort + portRange
}

// startServer spawns an opencode serve process on the given port. It returns
// the OS process handle. The process is detached from the parent so it
// outlives witty.
//
// The password is passed via the OPENCODE_SERVER_PASSWORD environment variable
// (never in command-line arguments, for /proc security).
func (m *manager) startServer(ctx context.Context, port int, password string) (*os.Process, error) {
	bin := m.binaryPath()
	if _, err := exec.LookPath(bin); err != nil {
		return nil, fmt.Errorf("opencode binary %q not found: %w", bin, err)
	}

	args := []string{"serve", "--port", fmt.Sprintf("%d", port), "--hostname", m.hostname()}

	cmd := exec.CommandContext(ctx, bin, args...)
	// Detach the child so it survives the parent (witty) exiting.
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid: true,
	}

	// Pass password via environment variable, not command-line args.
	if password != "" {
		cmd.Env = append(os.Environ(), "OPENCODE_SERVER_PASSWORD="+password)
	}

	// Discard stdout/stderr of the server process, since Witty communicates
	// with it only over HTTP.
	cmd.Stdout = nil
	cmd.Stderr = nil

	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("start opencode serve on port %d: %w", port, err)
	}

	baseURL := fmt.Sprintf("http://%s:%d", m.hostname(), port)
	healthCtx, cancel := context.WithTimeout(ctx, m.startupTimeout())
	defer cancel()

	if err := waitForServerWithAuth(healthCtx, baseURL, password, healthCheckInterval); err != nil {
		// The server didn't become healthy in time. Kill the process we
		// started and clean up.
		_ = cmd.Process.Kill()
		_ = cmd.Process.Release()
		return nil, fmt.Errorf("open code server failed to become healthy on %s: %w", baseURL, err)
	}

	return cmd.Process, nil
}

// isPIDAlive checks whether a process with the given PID exists.
func isPIDAlive(pid int) bool {
	if pid <= 0 {
		return false
	}
	process, err := os.FindProcess(pid)
	if err != nil {
		return false
	}
	// Signal 0 is a null signal used for existence checking on Unix.
	err = process.Signal(syscall.Signal(0))
	return err == nil
}
