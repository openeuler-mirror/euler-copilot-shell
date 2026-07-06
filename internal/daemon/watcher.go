package daemon

import (
	"context"
	"fmt"
	"log/slog"
	"time"

	"github.com/fsnotify/fsnotify"
)

// ConfigWatcher watches the opencode configuration file and triggers a
// server restart when it changes. This ensures that agent/skill/MCP config
// changes installed via RPM take effect without manual intervention.
type ConfigWatcher struct {
	supervisor *Supervisor
	configFile string
	configDir  string
	debounce   time.Duration
	logger     *slog.Logger
}

// ConfigWatcherOptions configures the config file watcher.
type ConfigWatcherOptions struct {
	// ConfigFile is the path to /etc/opencode/opencode.json.
	ConfigFile string
	// ConfigDir is the path to the config drop-in directory.
	ConfigDir string
	// Debounce is the minimum interval between restart triggers (default: 2s).
	Debounce time.Duration
	// Logger receives operational messages.
	Logger *slog.Logger
}

// NewConfigWatcher creates a config watcher.
func NewConfigWatcher(supervisor *Supervisor, opts ConfigWatcherOptions) *ConfigWatcher {
	debounce := opts.Debounce
	if debounce <= 0 {
		debounce = 2 * time.Second
	}
	logger := opts.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &ConfigWatcher{
		supervisor: supervisor,
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
		// Config file may not exist yet (e.g. on macOS dev, or before
		// witty-agent-loader creates it). Log and continue without
		// watching the file; the directory watch may still catch changes.
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
			if !isRelevantEvent(event) {
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
			w.logger.Info("restarting server due to config change")
			if _, err := w.supervisor.Restart(ctx); err != nil {
				w.logger.Error("config-triggered restart failed", "error", err)
			}
		}
	}
}

// isRelevantEvent returns true for events that indicate a config file was
// created, modified, or removed.
func isRelevantEvent(e fsnotify.Event) bool {
	return e.Has(fsnotify.Create) || e.Has(fsnotify.Write) || e.Has(fsnotify.Remove) || e.Has(fsnotify.Rename)
}
