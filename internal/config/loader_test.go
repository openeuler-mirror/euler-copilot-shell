package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestLoad_DefaultsWhenConfigFilesMissing(t *testing.T) {
	cfg, err := Load(LoadOptions{ConfigFiles: []string{filepath.Join(t.TempDir(), "missing.toml")}})
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if cfg.ServerURL != DefaultServerURL {
		t.Fatalf("ServerURL = %q, want %q", cfg.ServerURL, DefaultServerURL)
	}
	if !cfg.REPL.AutoResume {
		t.Fatal("REPL.AutoResume = false, want true")
	}
	if !cfg.Shell.Enabled {
		t.Fatal("Shell.Enabled = false, want true")
	}
	if cfg.Doctor.TimeoutSeconds != DefaultDoctorTimeoutSeconds {
		t.Fatalf("Doctor.TimeoutSeconds = %d, want %d", cfg.Doctor.TimeoutSeconds, DefaultDoctorTimeoutSeconds)
	}
}

func TestLoad_FileEnvAndCLIOverridePrecedence(t *testing.T) {
	configFile := filepath.Join(t.TempDir(), "config.toml")
	content := `server_url = "http://file:4096"
default_agent = "file-agent"
default_model = "file-model"
debug = false

[repl]
auto_resume = false

[shell]
enabled = false
`
	if err := os.WriteFile(configFile, []byte(content), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}

	debug := false
	noColor := true
	cfg, err := Load(LoadOptions{
		ConfigFiles: []string{configFile},
		LookupEnv: mapLookup(map[string]string{
			"WITTY_SERVER_URL":   "http://env:4096",
			"WITTY_AGENT":        "env-agent",
			"WITTY_DEBUG":        "true",
			"WITTY_SHELL_ENABLE": "true",
		}),
		Overrides: Overrides{
			DefaultAgent: "cli-agent",
			Debug:        &debug,
			NoColor:      &noColor,
		},
	})
	if err != nil {
		t.Fatalf("Load() error = %v", err)
	}

	if cfg.ServerURL != "http://env:4096" {
		t.Fatalf("ServerURL = %q, want env value", cfg.ServerURL)
	}
	if cfg.DefaultAgent != "cli-agent" {
		t.Fatalf("DefaultAgent = %q, want cli-agent", cfg.DefaultAgent)
	}
	if cfg.DefaultModel != "file-model" {
		t.Fatalf("DefaultModel = %q, want file-model", cfg.DefaultModel)
	}
	if cfg.Debug {
		t.Fatal("Debug = true, want CLI override false")
	}
	if !cfg.NoColor {
		t.Fatal("NoColor = false, want true")
	}
	if cfg.REPL.AutoResume {
		t.Fatal("REPL.AutoResume = true, want file override false")
	}
	if !cfg.Shell.Enabled {
		t.Fatal("Shell.Enabled = false, want env override true")
	}
}

func TestLoad_ConfigPathMissingReturnsContext(t *testing.T) {
	_, err := Load(LoadOptions{ConfigPath: filepath.Join(t.TempDir(), "missing.toml")})
	if err == nil {
		t.Fatal("Load() error = nil, want error")
	}
	if !strings.Contains(err.Error(), "load config") {
		t.Fatalf("Load() error = %q, want load config context", err.Error())
	}
}

func TestLoad_InvalidConfigReturnsContext(t *testing.T) {
	configFile := filepath.Join(t.TempDir(), "config.toml")
	if err := os.WriteFile(configFile, []byte("server_url = ["), 0o600); err != nil {
		t.Fatalf("write config: %v", err)
	}

	_, err := Load(LoadOptions{ConfigPath: configFile})
	if err == nil {
		t.Fatal("Load() error = nil, want error")
	}
	if !strings.Contains(err.Error(), "load config") {
		t.Fatalf("Load() error = %q, want load config context", err.Error())
	}
}

func TestLoad_InvalidBoolEnvReturnsContext(t *testing.T) {
	_, err := Load(LoadOptions{
		ConfigFiles: []string{},
		LookupEnv: mapLookup(map[string]string{
			"WITTY_DEBUG": "sometimes",
		}),
	})
	if err == nil {
		t.Fatal("Load() error = nil, want error")
	}
	if !strings.Contains(err.Error(), "parse WITTY_DEBUG") {
		t.Fatalf("Load() error = %q, want env parse context", err.Error())
	}
}

func mapLookup(values map[string]string) func(string) (string, bool) {
	return func(key string) (string, bool) {
		value, ok := values[key]
		return value, ok
	}
}
