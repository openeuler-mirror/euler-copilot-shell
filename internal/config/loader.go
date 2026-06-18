package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"

	"github.com/knadh/koanf/parsers/toml"
	"github.com/knadh/koanf/providers/confmap"
	"github.com/knadh/koanf/providers/file"
	"github.com/knadh/koanf/v2"
)

// LoadOptions controls configuration loading for production and tests.
type LoadOptions struct {
	ConfigPath    string
	ConfigFiles   []string
	Overrides     Overrides
	LookupEnv     func(string) (string, bool)
	UserConfigDir func() (string, error)
}

// Load reads configuration in the required order: defaults, file, env, CLI overrides.
func Load(opts LoadOptions) (Config, error) {
	lookupEnv := opts.LookupEnv
	if lookupEnv == nil {
		lookupEnv = os.LookupEnv
	}

	k := koanf.New(".")
	if err := k.Load(confmap.Provider(defaultMap(), "."), nil); err != nil {
		return Config{}, fmt.Errorf("load config defaults: %w", err)
	}

	files, explicitFile := configFiles(opts, lookupEnv)
	for _, path := range files {
		if path == "" {
			continue
		}
		if err := loadConfigFile(k, path, explicitFile); err != nil {
			return Config{}, fmt.Errorf("load config: %w", err)
		}
	}

	envValues, err := envMap(lookupEnv)
	if err != nil {
		return Config{}, fmt.Errorf("load config: %w", err)
	}
	if len(envValues) > 0 {
		if err := k.Load(confmap.Provider(envValues, "."), nil); err != nil {
			return Config{}, fmt.Errorf("load config env: %w", err)
		}
	}

	cliValues := overrideMap(opts.Overrides)
	if len(cliValues) > 0 {
		if err := k.Load(confmap.Provider(cliValues, "."), nil); err != nil {
			return Config{}, fmt.Errorf("load config overrides: %w", err)
		}
	}

	return readConfig(k), nil
}

func configFiles(opts LoadOptions, lookupEnv func(string) (string, bool)) ([]string, bool) {
	if opts.ConfigPath != "" {
		return []string{opts.ConfigPath}, true
	}
	if path, ok := lookupEnv("WITTY_CONFIG"); ok && path != "" {
		return []string{path}, true
	}
	if opts.ConfigFiles != nil {
		return opts.ConfigFiles, false
	}
	return defaultConfigFiles(opts.UserConfigDir), false
}

func defaultConfigFiles(userConfigDir func() (string, error)) []string {
	paths := []string{"/etc/witty/config.toml"}
	if userConfigDir == nil {
		userConfigDir = os.UserConfigDir
	}
	if dir, err := userConfigDir(); err == nil && dir != "" {
		paths = append(paths, filepath.Join(dir, "witty", "config.toml"))
	}
	return paths
}

func loadConfigFile(k *koanf.Koanf, path string, explicit bool) error {
	if _, err := os.Stat(path); err != nil {
		if os.IsNotExist(err) && !explicit {
			return nil
		}
		return fmt.Errorf("load config file %q: %w", path, err)
	}
	if err := k.Load(file.Provider(path), toml.Parser()); err != nil {
		return fmt.Errorf("load config file %q: %w", path, err)
	}
	return nil
}

func defaultMap() map[string]any {
	cfg := Default()
	return map[string]any{
		"server_url":             cfg.ServerURL,
		"default_agent":          cfg.DefaultAgent,
		"default_model":          cfg.DefaultModel,
		"default_variant":        cfg.DefaultVariant,
		"debug":                  cfg.Debug,
		"theme":                  cfg.Theme,
		"no_color":               cfg.NoColor,
		"renderer_phase":         cfg.RendererPhase,
		"repl.auto_resume":       cfg.REPL.AutoResume,
		"shell.enabled":          cfg.Shell.Enabled,
		"shell.debug":            cfg.Shell.Debug,
		"doctor.timeout_seconds": cfg.Doctor.TimeoutSeconds,
		"display.show_reasoning": cfg.Display.ShowReasoning,
		"display.tool_mode":      cfg.Display.ToolMode,
		"display.group_context":  cfg.Display.GroupContext,
		"display.step_style":     cfg.Display.StepStyle,
	}
}

func envMap(lookupEnv func(string) (string, bool)) (map[string]any, error) {
	values := make(map[string]any)
	copyStringEnv(values, lookupEnv, "WITTY_SERVER_URL", "server_url")
	copyStringEnv(values, lookupEnv, "WITTY_AGENT", "default_agent")
	copyStringEnv(values, lookupEnv, "WITTY_MODEL", "default_model")
	copyStringEnv(values, lookupEnv, "WITTY_VARIANT", "default_variant")

	if err := copyBoolEnv(values, lookupEnv, "WITTY_DEBUG", "debug"); err != nil {
		return nil, err
	}
	if err := copyBoolEnv(values, lookupEnv, "WITTY_SHELL_ENABLE", "shell.enabled"); err != nil {
		return nil, err
	}
	if err := copyBoolEnv(values, lookupEnv, "WITTY_SHELL_DEBUG", "shell.debug"); err != nil {
		return nil, err
	}
	if err := copyBoolEnv(values, lookupEnv, "WITTY_DISPLAY_SHOW_REASONING", "display.show_reasoning"); err != nil {
		return nil, err
	}
	if _, ok := lookupEnv("NO_COLOR"); ok {
		values["no_color"] = true
	}
	return values, nil
}

func copyStringEnv(values map[string]any, lookupEnv func(string) (string, bool), envKey, configKey string) {
	if value, ok := lookupEnv(envKey); ok {
		values[configKey] = value
	}
}

func copyBoolEnv(values map[string]any, lookupEnv func(string) (string, bool), envKey, configKey string) error {
	value, ok := lookupEnv(envKey)
	if !ok {
		return nil
	}
	parsed, err := strconv.ParseBool(value)
	if err != nil {
		return fmt.Errorf("parse %s: %w", envKey, err)
	}
	values[configKey] = parsed
	return nil
}

func overrideMap(overrides Overrides) map[string]any {
	values := make(map[string]any)
	if overrides.ServerURL != "" {
		values["server_url"] = overrides.ServerURL
	}
	if overrides.DefaultAgent != "" {
		values["default_agent"] = overrides.DefaultAgent
	}
	if overrides.DefaultModel != "" {
		values["default_model"] = overrides.DefaultModel
	}
	if overrides.DefaultVariant != "" {
		values["default_variant"] = overrides.DefaultVariant
	}
	if overrides.Debug != nil {
		values["debug"] = *overrides.Debug
	}
	if overrides.NoColor != nil {
		values["no_color"] = *overrides.NoColor
	}
	return values
}

func readConfig(k *koanf.Koanf) Config {
	return Config{
		ServerURL:      k.String("server_url"),
		DefaultAgent:   k.String("default_agent"),
		DefaultModel:   k.String("default_model"),
		DefaultVariant: k.String("default_variant"),
		Debug:          k.Bool("debug"),
		Theme:          k.String("theme"),
		NoColor:        k.Bool("no_color"),
		RendererPhase:  k.Int("renderer_phase"),
		REPL: REPLConfig{
			AutoResume: k.Bool("repl.auto_resume"),
		},
		Shell: ShellConfig{
			Enabled: k.Bool("shell.enabled"),
			Debug:   k.Bool("shell.debug"),
		},
		Doctor: DoctorConfig{
			TimeoutSeconds: k.Int("doctor.timeout_seconds"),
		},
		Display: DisplayConfig{
			ShowReasoning: k.Bool("display.show_reasoning"),
			ToolMode:      k.String("display.tool_mode"),
			GroupContext:  k.Bool("display.group_context"),
			StepStyle:     k.String("display.step_style"),
		},
	}
}
