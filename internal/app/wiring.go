package app

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"os"
	"os/signal"
	"syscall"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/config"
	"atomgit.com/openeuler/euler-copilot-shell/internal/core"
	"atomgit.com/openeuler/euler-copilot-shell/internal/doctor"
	"atomgit.com/openeuler/euler-copilot-shell/internal/event"
	"atomgit.com/openeuler/euler-copilot-shell/internal/permission"
	"atomgit.com/openeuler/euler-copilot-shell/internal/presenter"
	"atomgit.com/openeuler/euler-copilot-shell/internal/renderer"
	"atomgit.com/openeuler/euler-copilot-shell/internal/repl"
	"atomgit.com/openeuler/euler-copilot-shell/internal/server"
	"atomgit.com/openeuler/euler-copilot-shell/internal/session"
	"atomgit.com/openeuler/euler-copilot-shell/internal/shellinit"
	"atomgit.com/openeuler/euler-copilot-shell/internal/terminal"
	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
)

// Options contains process-level dependencies used by the composition root.
type Options struct {
	Config           config.LoadOptions
	Version          version.Info
	Stdout           io.Writer
	Stderr           io.Writer
	SessionStatePath string

	// ServerURL, when non-empty, bypasses server lifecycle management
	// and connects directly to the given URL. This is used when the
	// user explicitly provides --server-url.
	ServerURL string
}

// New loads config, initializes shared infrastructure, and returns the app container.
func New(ctx context.Context, opts Options) (Container, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}

	cfg, err := config.Load(opts.Config)
	if err != nil {
		return nil, err
	}

	stdout := stdoutWriter(opts.Stdout)
	stdoutFile := writerFile(stdout)
	isTTY := terminal.IsTerminal(stdoutFile)
	interactiveTTY := isTTY && terminal.IsTerminal(os.Stdin)

	logger := newLogger(cfg, stderrWriter(opts.Stderr))

	// Determine the server connection. When the user explicitly provides
	// --server-url, use it directly and skip lifecycle management.
	var (
		conn      server.Connection
		serverMgr server.Manager
	)
	if opts.ServerURL != "" {
		conn = server.Connection{URL: opts.ServerURL}
	} else {
		serverStateDir := resolveServerStateDir(opts.Config)
		serverMgr, err = server.NewManager(server.Options{
			StateDir:           serverStateDir,
			AutoStart:          cfg.Server.AutoStart,
			PreferredPort:      cfg.Server.Port,
			Hostname:           cfg.Server.Hostname,
			StartupTimeout:     time.Duration(cfg.Server.StartupTimeoutSeconds) * time.Second,
			OpenCodeBinaryPath: "opencode",
		})
		if err != nil {
			return nil, fmt.Errorf("create server manager: %w", err)
		}
		conn, err = serverMgr.Ensure(ctx)
		if err != nil {
			return nil, fmt.Errorf("ensure opencode server: %w", err)
		}
	}
	logger.Debug("server connection resolved", "url", conn.URL)

	transportClient, err := transport.NewClient(transport.Options{
		BaseURL:  conn.URL,
		Logger:   logger,
		Password: conn.Password,
	})
	if err != nil {
		return nil, err
	}
	sessionResolver, err := session.NewService(session.Options{
		Transport: transportClient,
		StatePath: opts.SessionStatePath,
	})
	if err != nil {
		return nil, err
	}
	eventRouter := event.NewRouter(transportClient)
	width := terminal.Width(stdoutFile)

	var rendererService renderer.TextRenderer
	if cfg.RendererPhase >= 2 {
		rendererService, err = renderer.NewEchoRenderer(renderer.EchoOptions{
			Writer:        stdout,
			IsTTY:         isTTY,
			Width:         width,
			Theme:         cfg.Theme,
			NoColor:       cfg.NoColor,
			InputFile:     os.Stdin,
			OutputFile:    stdoutFile,
			Enabled:       true,
			ReasoningMode: cfg.Display.ShowReasoning,
		})
	} else {
		rendererService, err = renderer.NewMarkdownRenderer(renderer.Options{
			Writer:        stdout,
			IsTTY:         isTTY,
			Width:         width,
			Theme:         cfg.Theme,
			NoColor:       cfg.NoColor,
			InputFile:     os.Stdin,
			OutputFile:    stdoutFile,
			ReasoningMode: cfg.Display.ShowReasoning,
		})
	}
	if err != nil {
		return nil, fmt.Errorf("create renderer: %w", err)
	}

	// Listen for terminal resize signals and forward to the renderer.
	if isTTY {
		go watchTerminalResize(ctx, rendererService, stdoutFile, logger)
	}

	presenterService := presenter.NewPresenter(presenter.Options{
		Writer:            stdout,
		IsTTY:             isTTY,
		NoColor:           cfg.NoColor,
		StepStyle:         cfg.Display.StepStyle,
		GroupContextTools: cfg.Display.GroupContextTools,
		Width:             width,
	})
	var prompt terminal.Prompter
	if interactiveTTY {
		prompt = terminal.NewPrompter(os.Stdin, stdout)
	}
	permissionService, err := permission.NewManager(permission.Options{
		Transport:   transportClient,
		Prompt:      prompt,
		SelectFn:    adaptPermissionSelect(prompt),
		Writer:      stdout,
		Interactive: interactiveTTY,
	})
	if err != nil {
		return nil, fmt.Errorf("create permission manager: %w", err)
	}
	askRunner, err := core.NewAskRunner(core.Options{
		Transport:  transportClient,
		Events:     eventRouter,
		Sessions:   sessionResolver,
		Renderer:   rendererService,
		Presenter:  presenterService,
		Permission: permissionService,
		ServerURL:  conn.URL,
	})
	if err != nil {
		return nil, fmt.Errorf("create ask runner: %w", err)
	}

	replLoop, err := repl.New(repl.Options{
		Runner:       askRunner,
		Sessions:     sessionResolver,
		Transport:    transportClient,
		Config:       cfg,
		ConfigWriter: config.NewWriter(nil),
	})
	if err != nil {
		return nil, fmt.Errorf("create repl: %w", err)
	}

	return &App{
		cfg:          cfg,
		logger:       logger,
		transport:    transportClient,
		events:       eventRouter,
		sessions:     sessionResolver,
		renderer:     rendererService,
		presenter:    presenterService,
		permission:   permissionService,
		ask:          askRunner,
		repl:         replLoop,
		shellInit:    shellinit.NewRenderer(),
		version:      opts.Version,
		configWriter: config.NewWriter(nil),
		serverMgr:    serverMgr,
		doctor: doctor.New(doctor.Options{
			Config: doctor.ConfigSummary{
				ServerURL:      conn.URL,
				DefaultAgent:   cfg.DefaultAgent,
				DefaultModel:   cfg.DefaultModel,
				Theme:          cfg.Theme,
				NoColor:        cfg.NoColor,
				ShellEnabled:   cfg.Shell.Enabled,
				RendererPhase:  cfg.RendererPhase,
				TimeoutSeconds: cfg.Doctor.TimeoutSeconds,
			},
			Env: doctor.Environment{
				ConfigSearchPaths: config.ConfigSearchPaths(opts.Config, os.LookupEnv),
				StdoutIsTTY:       isTTY,
				StdinIsTTY:        terminal.IsTerminal(os.Stdin),
				TerminalWidth:     width,
				NoColor:           cfg.NoColor,
				SupportsColor:     terminal.SupportsColor(stdoutFile, os.LookupEnv),
				Term:              os.Getenv("TERM"),
				ShellLoaded:       os.Getenv("__WITTY_SHELL_INIT_LOADED") == "1",
				InteractiveTTY:    interactiveTTY,
			},
			Server:  newServerProbeAdapter(transportClient),
			Timeout: time.Duration(cfg.Doctor.TimeoutSeconds) * time.Second,
		}),
	}, nil
}

// resolveServerStateDir determines the directory for server-state.json.
// It defaults to the same directory as the session state file.
func resolveServerStateDir(loadOpts config.LoadOptions) string {
	// TODO: in future, allow explicit override via config or env.
	path, err := server.DefaultServerStateDir(nil, nil)
	if err != nil {
		return ""
	}
	return path
}

func newLogger(cfg config.Config, stderr io.Writer) *slog.Logger {
	writer := writerOrDiscard(stderr)
	if !cfg.Debug && !isTTYWriter(writer) {
		writer = io.Discard
	}

	level := slog.LevelInfo
	if cfg.Debug {
		level = slog.LevelDebug
	}

	handlerOpts := &slog.HandlerOptions{Level: level}
	if cfg.Debug {
		handlerOpts.ReplaceAttr = func(_ []string, attr slog.Attr) slog.Attr {
			if attr.Key == slog.TimeKey {
				return slog.Attr{}
			}
			return attr
		}
	}

	return slog.New(slog.NewTextHandler(writer, handlerOpts))
}

func isTTYWriter(writer io.Writer) bool {
	return terminal.IsTerminal(writerFile(writer))
}

func writerFile(writer io.Writer) *os.File {
	file, ok := writer.(*os.File)
	if !ok {
		return nil
	}
	return file
}

// adaptPermissionSelect builds a permission.SelectFn from a terminal.Prompter
// by converting between the two packages' SelectOption types.
func adaptPermissionSelect(p terminal.Prompter) func(ctx context.Context, title string, options []permission.SelectOption) (int, error) {
	if p == nil {
		return nil
	}
	return func(ctx context.Context, title string, options []permission.SelectOption) (int, error) {
		termOpts := make([]terminal.SelectOption, len(options))
		for i, o := range options {
			termOpts[i] = terminal.SelectOption{Label: o.Label, Description: o.Description, Value: o.Value}
		}
		return p.Select(ctx, title, termOpts)
	}
}

// watchTerminalResize listens for SIGWINCH and notifies the renderer of
// width changes. It exits when ctx is cancelled.
func watchTerminalResize(ctx context.Context, r renderer.TextRenderer, stdoutFile *os.File, logger *slog.Logger) {
	ch := make(chan os.Signal, 1)
	signal.Notify(ch, syscall.SIGWINCH)
	defer signal.Stop(ch)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ch:
			width := terminal.Width(stdoutFile)
			logger.Debug("terminal resize", "width", width)
			r.Resize(width)
		}
	}
}

// serverProbeAdapter adapts transport.Client to the doctor.ServerProbe interface.
type serverProbeAdapter struct {
	client transport.Client
}

func newServerProbeAdapter(client transport.Client) doctor.ServerProbe {
	if client == nil {
		return nil
	}
	return &serverProbeAdapter{client: client}
}

func (a *serverProbeAdapter) Health(ctx context.Context) (doctor.HealthResult, error) {
	h, err := a.client.Health(ctx)
	if err != nil {
		return doctor.HealthResult{}, err
	}
	return doctor.HealthResult{Healthy: h.Healthy, Version: h.Version}, nil
}

func (a *serverProbeAdapter) ProbeEndpoint(ctx context.Context, endpoint string) (int, error) {
	return a.client.ProbeEndpoint(ctx, endpoint)
}
