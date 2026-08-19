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
)

func main() {
	cfg, err := daemon.LoadConfig("")
	if err != nil {
		fmt.Fprintln(os.Stderr, "wittyd:", err)
		os.Exit(1)
	}

	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelInfo}))

	// wittyd is a system-wide janitor: it does NOT start any opencode server.
	// It monitors all opencode processes, enforces idle timeout (stopping
	// only servers that are not busy), and watches config files so that
	// outdated servers get restarted on next use.

	monitor := daemon.NewMonitor()
	logger.Info("loaded daemon config",
		"socket", cfg.SocketPath,
		"idle_timeout_minutes", int(cfg.IdleTimeout.Minutes()),
		"config_watch_file", cfg.ConfigFile,
		"config_watch_dir", cfg.ConfigDir,
	)

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	// Idle reaper: stops servers idle > 30 min, but only if not busy.
	reaper := daemon.NewReaper(monitor, daemon.ReaperOptions{
		IdleTimeout:   cfg.IdleTimeout,
		CheckInterval: 60 * time.Second,
		Logger:        logger,
	})

	// Config watcher: stops all servers when config changes.
	configWatcher := daemon.NewConfigWatcher(monitor, daemon.ConfigWatcherOptions{
		ConfigFile: cfg.ConfigFile,
		ConfigDir:  cfg.ConfigDir,
		Debounce:   2 * time.Second,
		Logger:     logger,
	})

	// IPC server: receives TOUCH from witty CLI transport layer.
	ipcServer := daemon.NewIPCServer(monitor, daemon.IPCOptions{
		SocketPath: cfg.SocketPath,
		Logger:     logger,
	})

	errCh := make(chan error, 3)
	go func() { errCh <- reaper.Run(ctx) }()
	go func() { errCh <- configWatcher.Run(ctx) }()
	go func() { errCh <- ipcServer.Listen(ctx) }()

	var firstErr error
	select {
	case <-ctx.Done():
		logger.Info("shutting down")
	case firstErr = <-errCh:
		logger.Error("component exited", "error", firstErr)
		cancel()
	}

	if firstErr != nil {
		fmt.Fprintln(os.Stderr, "wittyd:", firstErr)
		os.Exit(1)
	}
}
