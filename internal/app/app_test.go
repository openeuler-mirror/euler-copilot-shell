package app

import (
	"bytes"
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

func TestNew_LoadsConfigAndVersion(t *testing.T) {
	container, err := New(context.Background(), Options{
		Config:  config.LoadOptions{ConfigFiles: []string{}},
		Version: version.New("1.0.0", "abc", "today"),
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	if container.Config().ServerURL != config.DefaultServerURL {
		t.Fatalf("ServerURL = %q, want default", container.Config().ServerURL)
	}
	if container.Version().Version != "1.0.0" {
		t.Fatalf("Version = %q, want 1.0.0", container.Version().Version)
	}
	if container.Transport() == nil {
		t.Fatal("Transport() = nil, want wired transport client")
	}
	if container.Events() == nil {
		t.Fatal("Events() = nil, want wired event router")
	}
	if container.Sessions() == nil {
		t.Fatal("Sessions() = nil, want wired session resolver")
	}
}

func TestInitBash_ReturnsPlaceholder(t *testing.T) {
	container, err := New(context.Background(), Options{Config: config.LoadOptions{ConfigFiles: []string{}}})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	script, err := container.InitBash(context.Background())
	if err != nil {
		t.Fatalf("InitBash() error = %v", err)
	}
	if !strings.Contains(script, "Witty Bash integration placeholder") {
		t.Fatalf("InitBash() = %q, want placeholder", script)
	}
}

func TestSessionServices_UseWiredTransport(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/session":
			if r.Method != http.MethodGet {
				t.Fatalf("list method = %s, want GET", r.Method)
			}
			_, _ = w.Write([]byte(`[{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work","title":"One","version":"dev","time":{"created":0,"updated":0}}]`))
		case "/session/ses_1":
			if r.Method != http.MethodGet {
				t.Fatalf("get method = %s, want GET", r.Method)
			}
			_, _ = w.Write([]byte(`{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work","title":"One","version":"dev","time":{"created":0,"updated":0}}`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides:   config.Overrides{ServerURL: server.URL},
		},
		SessionStatePath: filepath.Join(t.TempDir(), "state.json"),
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	summaries, err := container.ListSessions(context.Background())
	if err != nil {
		t.Fatalf("ListSessions() error = %v", err)
	}
	if len(summaries) != 1 || summaries[0].ID != "ses_1" {
		t.Fatalf("ListSessions() = %+v, want ses_1", summaries)
	}
	ctx, err := container.ContinueSession(context.Background(), "ses_1")
	if err != nil {
		t.Fatalf("ContinueSession() error = %v", err)
	}
	if ctx.ID != "ses_1" {
		t.Fatalf("ContinueSession() ID = %q, want ses_1", ctx.ID)
	}
}

func TestAsk_NotImplemented(t *testing.T) {
	container, err := New(context.Background(), Options{Config: config.LoadOptions{ConfigFiles: []string{}}})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	err = container.Ask(context.Background(), "hello")
	if !errors.Is(err, ErrNotImplemented) {
		t.Fatalf("Ask() error = %v, want ErrNotImplemented", err)
	}
}

func TestLogger_DebugWritesToNonTTYStderr(t *testing.T) {
	debug := true
	var stderr bytes.Buffer
	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{
			ConfigFiles: []string{},
			Overrides: config.Overrides{
				Debug: &debug,
			},
		},
		Stderr: &stderr,
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	container.Logger().Debug("debug message")
	if !strings.Contains(stderr.String(), "debug message") {
		t.Fatalf("debug log = %q, want debug message", stderr.String())
	}
}
