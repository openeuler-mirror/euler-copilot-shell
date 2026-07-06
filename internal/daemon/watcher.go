package daemon

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/fsnotify/fsnotify"
)

// ConfigWatcher watches /etc/opencode/opencode.json and the config.d
// directory. When config changes are detected (after RPM agent/skill
// installs), it stops all tracked opencode servers so that the next
// witty CLI invocation auto-starts fresh servers with the new config.
type ConfigWatcher struct {
	monitor    *Monitor
	configFile string
	configDir  string
	debounce   time.Duration
	logger     *slog.Logger
}

// ConfigWatcherOptions configures the config file watcher.
type ConfigWatcherOptions struct {
	ConfigFile string
	ConfigDir  string
	Debounce   time.Duration
	Logger     *slog.Logger
}

// NewConfigWatcher creates a config watcher.
func NewConfigWatcher(monitor *Monitor, opts ConfigWatcherOptions) *ConfigWatcher {
	debounce := opts.Debounce
	if debounce <= 0 {
		debounce = 2 * time.Second
	}
	logger := opts.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &ConfigWatcher{
		monitor:    monitor,
		configFile: opts.ConfigFile,
		configDir:  opts.ConfigDir,
		debounce:   debounce,
		logger:     logger,
	}
}

// Run starts watching for config changes. It blocks until ctx is cancelled.
func (w *ConfigWatcher) Run(ctx context.Context) error {
	watcher, err := fsnotify.NewWatcher()
	if err != nil {
		return fmt.Errorf("create fsnotify watcher: %w", err)
	}
	defer watcher.Close()

	if err := watcher.Add(w.configFile); err != nil {
		w.logger.Warn("cannot watch config file, will retry on events from config dir",
			"path", w.configFile, "error", err)
	} else {
		w.logger.Info("watching config file", "path", w.configFile)
	}

	if w.configDir != "" {
		if err := watcher.Add(w.configDir); err != nil {
			w.logger.Warn("cannot watch config dir", "path", w.configDir, "error", err)
		} else {
			w.logger.Info("watching config dir", "path", w.configDir)
		}
	}

	var timer *time.Timer
	var timerC <-chan time.Time

	for {
		select {
		case <-ctx.Done():
			if timer != nil {
				timer.Stop()
			}
			return ctx.Err()

		case event, ok := <-watcher.Events:
			if !ok {
				return nil
			}
			if !isRelevant(event) {
				continue
			}
			w.logger.Debug("config change detected", "path", event.Name, "op", event.Op)
			if timer == nil {
				timer = time.NewTimer(w.debounce)
				timerC = timer.C
			} else {
				timer.Reset(w.debounce)
			}

		case err, ok := <-watcher.Errors:
			if !ok {
				return nil
			}
			w.logger.Warn("fsnotify error", "error", err)

		case <-timerC:
			timer = nil
			timerC = nil
			w.logger.Info("config changed, stopping all servers for restart on next use")
			w.monitor.Discover()
			for _, srv := range w.monitor.All() {
				if err := stopServer(ctx, srv); err != nil {
					w.logger.Error("failed to stop server after config change", "port", srv.Port, "error", err)
				} else {
					w.logger.Info("stopped server for config refresh", "port", srv.Port)
				}
			}
		}
	}
}

func isRelevant(e fsnotify.Event) bool {
	return e.Has(fsnotify.Create) || e.Has(fsnotify.Write) || e.Has(fsnotify.Remove) || e.Has(fsnotify.Rename)
}
