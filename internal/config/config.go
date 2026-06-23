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
	RendererPhase  int
	REPL           REPLConfig
	Shell          ShellConfig
	Doctor         DoctorConfig
	Display        DisplayConfig
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

// DisplayConfig controls how intermediate process (reasoning, tool calls, steps)
// are displayed in the terminal.
type DisplayConfig struct {
	ShowReasoning     string // "show", "minimal", "hide" (default "show")
	ToolMode          string // "compact" or "verbose"
	GroupContextTools bool   // group consecutive read/grep/glob/list calls
	StepStyle         string // "line", "minimal", "none"
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
		RendererPhase:  1,
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
		Display: DisplayConfig{
			ShowReasoning:     "show",
			ToolMode:          "compact",
			GroupContextTools: true,
			StepStyle:         "line",
		},
	}
}
