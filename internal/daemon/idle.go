package daemon

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"
)

// Reaper periodically stops idle opencode servers, but only when they are
// not busy (no active agent sessions).
type Reaper struct {
	monitor     *Monitor
	idleTimeout time.Duration
	interval    time.Duration
	logger      *slog.Logger
}

// ReaperOptions configures the idle reaper.
type ReaperOptions struct {
	IdleTimeout   time.Duration
	CheckInterval time.Duration
	Logger        *slog.Logger
}

// NewReaper creates an idle reaper.
func NewReaper(monitor *Monitor, opts ReaperOptions) *Reaper {
	interval := opts.CheckInterval
	if interval <= 0 {
		interval = 60 * time.Second
	}
	logger := opts.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &Reaper{
		monitor:     monitor,
		idleTimeout: opts.IdleTimeout,
		interval:    interval,
		logger:      logger,
	}
}

// Run starts the reaper loop. It blocks until ctx is cancelled.
func (r *Reaper) Run(ctx context.Context) error {
	if r.idleTimeout <= 0 {
		<-ctx.Done()
		return nil
	}

	// Initial discovery before starting the ticker.
	r.monitor.Discover()

	ticker := time.NewTicker(r.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}

		r.monitor.Discover()

		for _, srv := range r.monitor.IdleServers(r.idleTimeout) {
			busy, err := isBusy(ctx, srv)
			if err != nil {
				r.logger.Warn("cannot check busy status", "port", srv.Port, "error", err)
				continue
			}
			if busy {
				r.logger.Info("server is idle but busy, skipping stop", "port", srv.Port, "pid", srv.PID)
				continue
			}

			r.logger.Info("stopping idle server", "port", srv.Port, "pid", srv.PID)
			if err := stopServer(ctx, srv); err != nil {
				r.logger.Error("failed to stop idle server", "port", srv.Port, "error", err)
			}
		}
	}
}

// isBusy checks whether an opencode server has active sessions (busy/retry).
// It queries GET /session/status with no auth (the endpoint does not require
// authentication when accessed from localhost).
func isBusy(ctx context.Context, info ServerInfo) (bool, error) {
	if info.Port == 0 {
		return false, fmt.Errorf("unknown port")
	}

	url := fmt.Sprintf("http://127.0.0.1:%d/session/status", info.Port)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return false, err
	}
	req.Header.Set("Accept", "application/json")
	if info.Password != "" {
		req.Header.Set("Authorization", "Basic "+basicAuth(info.Password))
	}

	client := &http.Client{Timeout: 3 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return false, err
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		return false, nil
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 65536))
	if err != nil {
		return false, err
	}

	var statuses map[string]struct {
		Type string `json:"type"`
	}
	if err := json.Unmarshal(body, &statuses); err != nil {
		return false, nil
	}

	for _, st := range statuses {
		if st.Type == "busy" || st.Type == "retry" {
			return true, nil
		}
	}
	return false, nil
}

// stopServer stops an opencode server via POST /global/dispose with
// SIGTERM fallback.
func stopServer(ctx context.Context, info ServerInfo) error {
	url := fmt.Sprintf("http://127.0.0.1:%d/global/dispose", info.Port)
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, nil)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json")
	if info.Password != "" {
		req.Header.Set("Authorization", "Basic "+basicAuth(info.Password))
	}

	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Do(req)
	if err == nil && resp.StatusCode == http.StatusOK {
		_ = resp.Body.Close()
		return nil
	}
	if resp != nil {
		_ = resp.Body.Close()
	}

	// Fallback: SIGTERM.
	if info.PID <= 0 {
		return fmt.Errorf("cannot stop server on port %d: dispose failed and no PID", info.Port)
	}
	proc, err := os.FindProcess(info.PID)
	if err != nil {
		return fmt.Errorf("find process %d: %w", info.PID, err)
	}
	return proc.Signal(os.Interrupt)
}

// basicAuth returns the Base64-encoded "opencode:<password>" value for
// an HTTP Basic Authorization header.
func basicAuth(password string) string {
	auth := "opencode:" + password
	return base64.StdEncoding.EncodeToString([]byte(auth))
}
