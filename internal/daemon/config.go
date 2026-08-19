package daemon

import (
	"fmt"
	"os"
	"time"

	"github.com/knadh/koanf/parsers/toml"
	"github.com/knadh/koanf/providers/confmap"
	"github.com/knadh/koanf/providers/file"
	"github.com/knadh/koanf/v2"
)

const (
	// DefaultConfigPath is the system-wide wittyd configuration file
	// installed by the RPM package.
	DefaultConfigPath = "/etc/witty/daemon.toml"

	DefaultSocketPath  = "/run/wittyd/wittyd.sock"
	DefaultIdleTimeout = 30 * time.Minute
	DefaultConfigFile  = "/etc/opencode/opencode.json"
	DefaultConfigDir   = "/usr/share/witty/opencode/config.d"
)

// Config holds the wittyd options that the current janitor implementation
// actually uses. The [server] section of daemon.toml is reserved for a
// future supervisor and is intentionally not consumed yet.
type Config struct {
	SocketPath  string
	IdleTimeout time.Duration
	ConfigFile  string
	ConfigDir   string
}

// DefaultConfig returns the built-in defaults. They match the behavior of
// the daemon before configuration file support was added.
func DefaultConfig() Config {
	return Config{
		SocketPath:  DefaultSocketPath,
		IdleTimeout: DefaultIdleTimeout,
		ConfigFile:  DefaultConfigFile,
		ConfigDir:   DefaultConfigDir,
	}
}

// LoadConfig reads daemon.toml from path (or DefaultConfigPath when path is
// empty) and merges it over the defaults. A missing file is not an error;
// an unreadable or invalid file is.
func LoadConfig(path string) (Config, error) {
	if path == "" {
		path = DefaultConfigPath
	}

	k := koanf.New(".")
	if err := k.Load(confmap.Provider(defaultConfigMap(), "."), nil); err != nil {
		return Config{}, fmt.Errorf("load daemon config defaults: %w", err)
	}

	if _, err := os.Stat(path); err != nil {
		if os.IsNotExist(err) {
			return readConfig(k), nil
		}
		return Config{}, fmt.Errorf("stat daemon config %q: %w", path, err)
	}

	if err := k.Load(file.Provider(path), toml.Parser()); err != nil {
		return Config{}, fmt.Errorf("load daemon config %q: %w", path, err)
	}
	return readConfig(k), nil
}

func defaultConfigMap() map[string]any {
	cfg := DefaultConfig()
	return map[string]any{
		"socket_path":          cfg.SocketPath,
		"idle_timeout_minutes": int(cfg.IdleTimeout / time.Minute),
		"config_watch_file":    cfg.ConfigFile,
		"config_watch_dir":     cfg.ConfigDir,
	}
}

func readConfig(k *koanf.Koanf) Config {
	return Config{
		SocketPath:  k.String("socket_path"),
		IdleTimeout: time.Duration(k.Int("idle_timeout_minutes")) * time.Minute,
		ConfigFile:  k.String("config_watch_file"),
		ConfigDir:   k.String("config_watch_dir"),
	}
}
