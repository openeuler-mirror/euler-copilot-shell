package server

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"time"
)

// healthResponse is the expected response from opencode's /global/health endpoint.
type healthResponse struct {
	Healthy bool   `json:"healthy"`
	Version string `json:"version"`
}

// portProbeTimeout is how long to wait for a TCP connection before giving up.
const portProbeTimeout = 2 * time.Second

// portOpen checks whether a TCP port is listening on the given host:port.
func portOpen(ctx context.Context, host string, port int) bool {
	d := net.Dialer{Timeout: portProbeTimeout}
	addr := fmt.Sprintf("%s:%d", host, port)
	conn, err := d.DialContext(ctx, "tcp", addr)
	if err != nil {
		return false
	}
	_ = conn.Close()
	return true
}

// healthCheck probes an opencode server at baseURL for the /global/health
// endpoint. It returns true when the server responds with healthy=true.
func healthCheck(ctx context.Context, baseURL string) bool {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, baseURL+"/global/health", nil)
	if err != nil {
		return false
	}
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: portProbeTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return false
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode != http.StatusOK {
		return false
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if err != nil {
		return false
	}

	var h healthResponse
	if err := json.Unmarshal(body, &h); err != nil {
		return false
	}
	return h.Healthy
}

// findOpenCodeOnPort checks whether there is an opencode server on the given
// host:port by first probing the TCP port then hitting /global/health.
func findOpenCodeOnPort(ctx context.Context, host string, port int) bool {
	if !portOpen(ctx, host, port) {
		return false
	}
	baseURL := fmt.Sprintf("http://%s:%d", host, port)
	return healthCheck(ctx, baseURL)
}

// waitForServer polls healthCheck until the server is healthy or the context
// is cancelled (via timeout).
func waitForServer(ctx context.Context, baseURL string, interval time.Duration) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		if healthCheck(ctx, baseURL) {
			return nil
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("server at %s did not become healthy: %w", baseURL, ctx.Err())
		case <-ticker.C:
		}
	}
}
