package config

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/knadh/koanf/parsers/toml"
	"github.com/knadh/koanf/providers/confmap"
	"github.com/knadh/koanf/providers/file"
	"github.com/knadh/koanf/v2"
)

// Writer persists configuration changes back to the user config file.
type Writer interface {
	SetDefaultAgent(agent string) error
	SetDefaultModel(model string) error
	SetDefaultVariant(variant string) error
	ConfigPath() string
}

type configWriter struct {
	userConfigDir func() (string, error)
	configPath    string
}

// NewWriter creates a config writer targeting the user config file.
func NewWriter(userConfigDir func() (string, error)) Writer {
	return &configWriter{userConfigDir: userConfigDir}
}

func (w *configWriter) ConfigPath() string {
	if w.configPath != "" {
		return w.configPath
	}
	dir := ""
	if w.userConfigDir != nil {
		if d, err := w.userConfigDir(); err == nil {
			dir = d
		}
	}
	if dir == "" {
		if d, err := os.UserConfigDir(); err == nil {
			dir = d
		}
	}
	if dir == "" {
		home, _ := os.UserHomeDir()
		dir = filepath.Join(home, ".config")
	}
	w.configPath = filepath.Join(dir, "witty", "config.toml")
	return w.configPath
}

// loadConfig reads the current config, merging existing file values with defaults.
func (w *configWriter) loadConfig() (*koanf.Koanf, error) {
	k := koanf.New(".")
	if err := k.Load(confmap.Provider(defaultMap(), "."), nil); err != nil {
		return nil, fmt.Errorf("load defaults: %w", err)
	}

	path := w.ConfigPath()
	if _, err := os.Stat(path); err == nil {
		if err := k.Load(file.Provider(path), toml.Parser()); err != nil {
			return nil, fmt.Errorf("load config file %q: %w", path, err)
		}
	}
	return k, nil
}

func (w *configWriter) SetDefaultAgent(agent string) error {
	return w.writeKey("default_agent", agent)
}

func (w *configWriter) SetDefaultModel(model string) error {
	return w.writeKey("default_model", model)
}

func (w *configWriter) SetDefaultVariant(variant string) error {
	return w.writeKey("default_variant", variant)
}

func (w *configWriter) writeKey(key, value string) error {
	if value == "" {
		return fmt.Errorf("config: %s is required", key)
	}

	k, err := w.loadConfig()
	if err != nil {
		return err
	}

	k.Set(key, value)

	path := w.ConfigPath()
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return fmt.Errorf("create config dir: %w", err)
	}

	data, err := k.Marshal(toml.Parser())
	if err != nil {
		return fmt.Errorf("marshal config: %w", err)
	}

	if err := os.WriteFile(path, data, 0o600); err != nil {
		return fmt.Errorf("write config %q: %w", path, err)
	}
	return nil
}
