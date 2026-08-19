package daemon

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLoadConfig_DefaultsWhenFileMissing(t *testing.T) {
	cfg, err := LoadConfig(filepath.Join(t.TempDir(), "missing.toml"))
	if err != nil {
		t.Fatalf("LoadConfig() error = %v", err)
	}
	if cfg != DefaultConfig() {
		t.Fatalf("LoadConfig() = %+v, want defaults %+v", cfg, DefaultConfig())
	}
}

func TestLoadConfig_ParsesFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "daemon.toml")
	content := `socket_path = "/tmp/wittyd.sock"
idle_timeout_minutes = 5
config_watch_file = "/tmp/opencode.json"
config_watch_dir = "/tmp/config.d"
`
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}

	cfg, err := LoadConfig(path)
	if err != nil {
		t.Fatalf("LoadConfig() error = %v", err)
	}
	if cfg.SocketPath != "/tmp/wittyd.sock" {
		t.Fatalf("SocketPath = %q, want /tmp/wittyd.sock", cfg.SocketPath)
	}
	if cfg.IdleTimeout != 5*time.Minute {
		t.Fatalf("IdleTimeout = %v, want 5m", cfg.IdleTimeout)
	}
	if cfg.ConfigFile != "/tmp/opencode.json" {
		t.Fatalf("ConfigFile = %q, want /tmp/opencode.json", cfg.ConfigFile)
	}
	if cfg.ConfigDir != "/tmp/config.d" {
		t.Fatalf("ConfigDir = %q, want /tmp/config.d", cfg.ConfigDir)
	}
}

func TestLoadConfig_ZeroIdleTimeoutDisablesReaper(t *testing.T) {
	path := filepath.Join(t.TempDir(), "daemon.toml")
	if err := os.WriteFile(path, []byte("idle_timeout_minutes = 0\n"), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}

	cfg, err := LoadConfig(path)
	if err != nil {
		t.Fatalf("LoadConfig() error = %v", err)
	}
	if cfg.IdleTimeout != 0 {
		t.Fatalf("IdleTimeout = %v, want 0", cfg.IdleTimeout)
	}
}

func TestLoadConfig_InvalidFileReturnsContext(t *testing.T) {
	path := filepath.Join(t.TempDir(), "daemon.toml")
	if err := os.WriteFile(path, []byte("socket_path = ["), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}

	_, err := LoadConfig(path)
	if err == nil {
		t.Fatal("LoadConfig() error = nil, want error")
	}
	if !strings.Contains(err.Error(), "load daemon config") {
		t.Fatalf("LoadConfig() error = %q, want load daemon config context", err.Error())
	}
}
