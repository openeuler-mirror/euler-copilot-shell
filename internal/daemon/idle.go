package daemon

import (
	"context"
	"fmt"
	"time"
)

// IdleMonitor periodically checks whether the managed server has been idle
// longer than the configured timeout and stops it proactively.
type IdleMonitor struct {
	supervisor  *Supervisor
	idleTimeout time.Duration
	interval    time.Duration
}

// IdleMonitorOptions configures the idle monitor.
type IdleMonitorOptions struct {
	// IdleTimeout is the duration after which an idle server is stopped.
	// Set to 0 to disable idle monitoring.
	IdleTimeout time.Duration
	// CheckInterval is how often to check for idle state (default: 60s).
	CheckInterval time.Duration
}

// NewIdleMonitor creates an idle monitor.
func NewIdleMonitor(supervisor *Supervisor, opts IdleMonitorOptions) *IdleMonitor {
	interval := opts.CheckInterval
	if interval <= 0 {
		interval = 60 * time.Second
	}
	return &IdleMonitor{
		supervisor:  supervisor,
		idleTimeout: opts.IdleTimeout,
		interval:    interval,
	}
}

// Run starts the idle monitoring loop. It blocks until ctx is cancelled.
// When idle timeout is exceeded, it stops the server and returns.
func (m *IdleMonitor) Run(ctx context.Context) error {
	if m.idleTimeout <= 0 {
		<-ctx.Done()
		return nil
	}

	ticker := time.NewTicker(m.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}

		st := m.supervisor.Status(ctx)
		if !st.Running {
			continue
		}
		lastUsed := m.supervisor.LastUsed()
		if lastUsed.IsZero() {
			continue
		}

		if time.Since(lastUsed) > m.idleTimeout {
			if err := m.supervisor.Stop(ctx); err != nil {
				return fmt.Errorf("idle stop: %w", err)
			}
			return nil
		}
	}
}
