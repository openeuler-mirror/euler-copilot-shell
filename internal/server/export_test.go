package server

import (
	"context"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"testing"
	"time"
)

// mockOpenCodeBinary creates a temporary Go binary that acts as a minimal
// opencode server for testing. When invoked with "serve --port N", it starts
// an HTTP server on port N with a /global/health endpoint.
//
// When the OPENCODE_SERVER_PASSWORD environment variable is set, the server
// requires HTTP Basic Auth (username: "opencode") for all requests.
func mockOpenCodeBinary(t *testing.T) string {
	t.Helper()

	src := filepath.Join(t.TempDir(), "main.go")
	code := `package main

import (
	"crypto/subtle"
	"encoding/base64"
	"fmt"
	"net/http"
	"os"
	"strings"
)

func main() {
	if len(os.Args) < 2 || os.Args[1] != "serve" {
		fmt.Fprintln(os.Stderr, "usage: mockopencode serve --port PORT")
		os.Exit(1)
	}
	port := "4096"
	for i, a := range os.Args {
		if a == "--port" && i+1 < len(os.Args) {
			port = os.Args[i+1]
		}
	}

	serverPassword := os.Getenv("OPENCODE_SERVER_PASSWORD")

	mux := http.NewServeMux()
	mux.HandleFunc("/global/health", func(w http.ResponseWriter, r *http.Request) {
		if serverPassword != "" {
			auth := r.Header.Get("Authorization")
			expectedPrefix := "Basic "
			if !strings.HasPrefix(auth, expectedPrefix) {
				w.Header().Set("WWW-Authenticate", ` + "`" + `Basic realm="opencode"` + "`" + `)
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			decoded, err := base64.StdEncoding.DecodeString(auth[len(expectedPrefix):])
			if err != nil {
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
			parts := strings.SplitN(string(decoded), ":", 2)
			if len(parts) != 2 || parts[0] != "opencode" || subtle.ConstantTimeCompare([]byte(parts[1]), []byte(serverPassword)) != 1 {
				w.Header().Set("WWW-Authenticate", ` + "`" + `Basic realm="opencode"` + "`" + `)
				w.WriteHeader(http.StatusUnauthorized)
				return
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(` + "`" + `{"healthy":true,"version":"1.0.0-test"}` + "`" + `))
	})
	mux.HandleFunc("/global/dispose", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("true"))
		// Dispose shuts the server down gracefully.
		go os.Exit(0)
	})
	if err := http.ListenAndServe("127.0.0.1:"+port, mux); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
`
	if err := os.WriteFile(src, []byte(code), 0o600); err != nil {
		t.Fatalf("write mock opencode source: %v", err)
	}

	bin := filepath.Join(t.TempDir(), "opencode")
	cmd := exec.Command("go", "build", "-o", bin, src)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("build mock opencode: %v\n%s", err, out)
	}
	return bin
}

// mockHealthServer starts an httptest server responding to /global/health.
func mockHealthServer(t *testing.T) (*httptest.Server, string) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/global/health" {
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"healthy":true,"version":"1.0.0"}`))
			return
		}
		http.NotFound(w, r)
	}))
	t.Cleanup(srv.Close)
	return srv, srv.URL
}

// mockAuthHealthServer starts an httptest server that requires HTTP Basic Auth
// (username: "opencode") for the /global/health endpoint.
func mockAuthHealthServer(t *testing.T, password string) (*httptest.Server, string) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/global/health" {
			http.NotFound(w, r)
			return
		}
		user, pass, ok := r.BasicAuth()
		if !ok || user != "opencode" || pass != password {
			w.Header().Set("WWW-Authenticate", `Basic realm="opencode"`)
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"healthy":true,"version":"1.0.0"}`))
	}))
	t.Cleanup(srv.Close)
	return srv, srv.URL
}

// mockNonOpenCodeServer starts a server without /global/health.
func mockNonOpenCodeServer(t *testing.T) (*httptest.Server, string) {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.NotFound(w, r)
	}))
	t.Cleanup(srv.Close)
	return srv, srv.URL
}

// testCtx returns a context with a reasonable timeout for tests.
func testCtx(t *testing.T) (context.Context, context.CancelFunc) {
	t.Helper()
	return context.WithTimeout(context.Background(), 10*time.Second)
}

// parseHostPort extracts the host and port from a URL string like "http://127.0.0.1:1234".
func parseHostPort(t *testing.T, rawURL string) (string, int) {
	t.Helper()
	u, err := url.Parse(rawURL)
	if err != nil {
		t.Fatalf("parse URL %q: %v", rawURL, err)
	}
	port, err := strconv.Atoi(u.Port())
	if err != nil {
		t.Fatalf("parse port from %q: %v", rawURL, err)
	}
	return u.Hostname(), port
}
