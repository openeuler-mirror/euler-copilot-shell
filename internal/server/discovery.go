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
// This variant does not send authentication credentials.
func healthCheck(ctx context.Context, baseURL string) bool {
	return healthCheckWithAuth(ctx, baseURL, "") == http.StatusOK
}

// healthCheckWithAuth probes the health endpoint with optional HTTP Basic Auth.
// It returns the HTTP status code:
//   - 200: server is healthy and accepted our credentials (or required none)
//   - 401: server requires auth but our credentials were rejected (someone else's server)
//   - 0:   connection error, timeout, or invalid response
func healthCheckWithAuth(ctx context.Context, baseURL string, password string) int {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, baseURL+"/global/health", nil)
	if err != nil {
		return 0
	}
	req.Header.Set("Accept", "application/json")
	if password != "" {
		req.Header.Set("Authorization", basicAuthHeader(password))
	}

	client := &http.Client{Timeout: portProbeTimeout}
	resp, err := client.Do(req)
	if err != nil {
		return 0
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode == http.StatusUnauthorized {
		return http.StatusUnauthorized
	}
	if resp.StatusCode != http.StatusOK {
		return resp.StatusCode
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, 4096))
	if err != nil {
		return 0
	}

	var h healthResponse
	if err := json.Unmarshal(body, &h); err != nil || !h.Healthy {
		return 0
	}
	return http.StatusOK
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

// authProbeResult describes the outcome of probing a port with credentials.
type authProbeResult int

const (
	authProbeMine    authProbeResult = iota // 200 with our password → our server
	authProbeForeign                        // 401 → someone else's server
	authProbeAbsent                         // port closed or not opencode
)

// probePortWithAuth checks a port and determines whether the opencode server
// there accepts our password (mine), rejects it (foreign), or is absent.
func probePortWithAuth(ctx context.Context, host string, port int, password string) authProbeResult {
	if !portOpen(ctx, host, port) {
		return authProbeAbsent
	}
	baseURL := fmt.Sprintf("http://%s:%d", host, port)
	code := healthCheckWithAuth(ctx, baseURL, password)
	switch code {
	case http.StatusOK:
		return authProbeMine
	case http.StatusUnauthorized:
		return authProbeForeign
	default:
		return authProbeAbsent
	}
}

// waitForServer polls healthCheck until the server is healthy or the context
// is cancelled (via timeout). This variant does not use authentication.
func waitForServer(ctx context.Context, baseURL string, interval time.Duration) error {
	return waitForServerWithAuth(ctx, baseURL, "", interval)
}

// waitForServerWithAuth polls the health endpoint with optional Basic Auth
// until the server responds 200 or the context is cancelled.
func waitForServerWithAuth(ctx context.Context, baseURL string, password string, interval time.Duration) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		if healthCheckWithAuth(ctx, baseURL, password) == http.StatusOK {
			return nil
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("server at %s did not become healthy: %w", baseURL, ctx.Err())
		case <-ticker.C:
		}
	}
}
