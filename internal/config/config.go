package config

const (
	DefaultServerURL            = "http://127.0.0.1:4096"
	DefaultAgent                = "build"
	DefaultTheme                = "auto"
	DefaultDoctorTimeoutSeconds = 5
)

// Config is the process-wide Witty runtime configuration.
type Config struct {
	ServerURL      string
	DefaultAgent   string
	DefaultModel   string
	DefaultVariant string
	Debug          bool
	Theme          string
	NoColor        bool
	REPL           REPLConfig
	Shell          ShellConfig
	Doctor         DoctorConfig
}

type REPLConfig struct {
	AutoResume bool
}

type ShellConfig struct {
	Enabled bool
	Debug   bool
}

type DoctorConfig struct {
	TimeoutSeconds int
}

// Overrides are CLI-provided values that should win over defaults, files, and env.
type Overrides struct {
	ServerURL      string
	DefaultAgent   string
	DefaultModel   string
	DefaultVariant string
	Debug          *bool
	NoColor        *bool
}

func Default() Config {
	return Config{
		ServerURL:      DefaultServerURL,
		DefaultAgent:   DefaultAgent,
		DefaultModel:   "",
		DefaultVariant: "",
		Debug:          false,
		Theme:          DefaultTheme,
		NoColor:        false,
		REPL: REPLConfig{
			AutoResume: true,
		},
		Shell: ShellConfig{
			Enabled: true,
			Debug:   false,
		},
		Doctor: DoctorConfig{
			TimeoutSeconds: DefaultDoctorTimeoutSeconds,
		},
	}
}
