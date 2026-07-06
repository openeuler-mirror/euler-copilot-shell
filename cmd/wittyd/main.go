package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/daemon"
	"atomgit.com/openeuler/euler-copilot-shell/internal/server"
)

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelInfo}))

	// Resolve state directory. Try the standard paths first so wittyd
	// can adopt an existing server previously managed by the witty CLI.
	// When running as a systemd service without $HOME, try /root first,
	// then fall back to /var/lib/witty.
	stateDir, err := server.DefaultServerStateDir(os.LookupEnv, os.UserHomeDir)
	if err != nil {
		// systemd environment: try root user's state, then fall back.
		stateDir = resolveSystemdStateDir()
	}

	supervisor, err := daemon.NewSupervisor(daemon.SupervisorOptions{
		StateDir:       stateDir,
		Hostname:       "127.0.0.1",
		PreferredPort:  0,
		StartupTimeout: 10 * time.Second,
	})
	if err != nil {
		logger.Error("create supervisor", "error", err)
		os.Exit(1)
	}

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Start the opencode server.
	logger.Info("starting opencode server")
	if err := supervisor.Start(ctx); err != nil {
		logger.Error("start server", "error", err)
		os.Exit(1)
	}
	conn := supervisor.Connection()
	logger.Info("opencode server ready", "url", conn.URL)

	// Idle monitor (30 minutes, check every 60s).
	idleMonitor := daemon.NewIdleMonitor(supervisor, daemon.IdleMonitorOptions{
		IdleTimeout:   30 * time.Minute,
		CheckInterval: 60 * time.Second,
	})

	// Config watcher.
	configWatcher := daemon.NewConfigWatcher(supervisor, daemon.ConfigWatcherOptions{
		ConfigFile: "/etc/opencode/opencode.json",
		ConfigDir:  "/usr/share/witty/opencode/config.d",
		Debounce:   2 * time.Second,
		Logger:     logger,
	})

	// IPC server.
	ipcServer := daemon.NewIPCServer(supervisor, daemon.IPCOptions{
		SocketPath: "/run/wittyd/wittyd.sock",
		Logger:     logger,
	})

	// Run all components.
	errCh := make(chan error, 3)

	go func() {
		errCh <- idleMonitor.Run(ctx)
	}()
	go func() {
		errCh <- configWatcher.Run(ctx)
	}()
	go func() {
		errCh <- ipcServer.Listen(ctx)
	}()

	// Wait for first error or signal.
	var firstErr error
	select {
	case <-ctx.Done():
		logger.Info("shutting down")
	case firstErr = <-errCh:
		logger.Error("component exited", "error", firstErr)
		cancel()
	}

	// Graceful shutdown: stop the server.
	shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer shutdownCancel()

	if err := supervisor.Stop(shutdownCtx); err != nil {
		logger.Error("stop server during shutdown", "error", err)
	} else {
		logger.Info("server stopped")
	}
	supervisor.Close()

	if firstErr != nil {
		fmt.Fprintln(os.Stderr, "wittyd:", firstErr)
		os.Exit(1)
	}
}

// resolveSystemdStateDir tries known state file locations for the root user
// when running as a systemd service (no $HOME). It returns the first
// directory that already contains a server-state.json, or falls back to
// /var/lib/witty.
func resolveSystemdStateDir() string {
	candidates := []string{
		"/root/.local/state/witty",
		"/var/lib/witty",
	}
	for _, dir := range candidates {
		if _, err := os.Stat(dir + "/server-state.json"); err == nil {
			return dir
		}
	}
	return "/var/lib/witty"
}
