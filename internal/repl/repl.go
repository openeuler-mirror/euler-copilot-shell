package repl

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"

	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/shellbridge"
	"atomgit.com/openeuler/witty-cli/internal/terminal"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

// Loop provides an interactive REPL that reads user input,
// dispatches to core.Runner for prompts, and handles control commands.
type Loop interface {
	Run(ctx context.Context) error
}

// Options configures the REPL loop.
type Options struct {
	Runner       core.Runner
	Sessions     session.Resolver
	Transport    transport.Client
	Config       config.Config
	ConfigWriter config.Writer
	CWD          string
	Stdin        io.Reader
	Stdout       io.Writer
}

type repl struct {
	runner       core.Runner
	sessions     session.Resolver
	transport    transport.Client
	cfg          config.Config
	configWriter config.Writer
	cwd          string
	stdin        io.Reader
	stdout       io.Writer
	stdinFile    *os.File
	stdoutFile   *os.File

	// Mutable REPL session state, protected by mu.
	mu            sync.Mutex
	agentOverride string // empty means use cfg default
	modelOverride string // empty means use cfg default
	forceNewNext  bool   // next ask should use ForceNew
	pinnedSession string // empty means auto-resolve
}

// New creates a REPL loop.
func New(opts Options) (Loop, error) {
	if opts.Runner == nil {
		return nil, fmt.Errorf("repl: runner is required")
	}
	if opts.Sessions == nil {
		return nil, fmt.Errorf("repl: session resolver is required")
	}
	if opts.Transport == nil {
		return nil, fmt.Errorf("repl: transport is required")
	}
	if opts.ConfigWriter == nil {
		return nil, fmt.Errorf("repl: config writer is required")
	}
	if opts.Stdin == nil {
		opts.Stdin = os.Stdin
	}
	if opts.Stdout == nil {
		opts.Stdout = os.Stdout
	}
	if opts.CWD == "" {
		var err error
		opts.CWD, err = os.Getwd()
		if err != nil {
			return nil, fmt.Errorf("repl: resolve cwd: %w", err)
		}
	}
	stdinFile, _ := opts.Stdin.(*os.File)
	stdoutFile, _ := opts.Stdout.(*os.File)
	return &repl{
		runner:       opts.Runner,
		sessions:     opts.Sessions,
		transport:    opts.Transport,
		cfg:          opts.Config,
		configWriter: opts.ConfigWriter,
		cwd:          opts.CWD,
		stdin:        opts.Stdin,
		stdout:       opts.Stdout,
		stdinFile:    stdinFile,
		stdoutFile:   stdoutFile,
	}, nil
}

func (r *repl) effectiveAgent() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.agentOverride != "" {
		return r.agentOverride
	}
	if r.cfg.DefaultAgent != "" {
		return r.cfg.DefaultAgent
	}
	return config.DefaultAgent
}

func (r *repl) effectiveModel() string {
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.modelOverride != "" {
		return r.modelOverride
	}
	return r.cfg.DefaultModel
}

func (r *repl) prompt() string {
	agent := r.effectiveAgent()
	model := r.effectiveModel()
	if model != "" {
		return fmt.Sprintf("witty [%s:%s] > ", agent, model)
	}
	return fmt.Sprintf("witty [%s] > ", agent)
}

// Run starts the REPL loop. It returns nil on clean exit (Ctrl+D or /exit).
func (r *repl) Run(ctx context.Context) error {
	loopCtx := context.WithoutCancel(ctx)

	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT)
	defer signal.Stop(sigCh)

	var (
		askCancel   context.CancelFunc
		askCancelMu sync.Mutex
	)

	go func() {
		for range sigCh {
			askCancelMu.Lock()
			cancel := askCancel
			askCancelMu.Unlock()
			if cancel != nil {
				cancel()
			}
		}
	}()

	if !r.cfg.REPL.AutoResume {
		r.mu.Lock()
		r.forceNewNext = true
		r.mu.Unlock()
	}

	scanner := bufio.NewScanner(r.stdin)
	fmt.Fprint(r.stdout, r.prompt())

	for {
		select {
		case <-ctx.Done():
			return nil
		default:
		}

		if !scanner.Scan() {
			fmt.Fprintln(r.stdout)
			if err := scanner.Err(); err != nil {
				return fmt.Errorf("repl: read input: %w", err)
			}
			return nil
		}

		line := strings.TrimSpace(scanner.Text())
		if line == "" {
			fmt.Fprint(r.stdout, r.prompt())
			continue
		}

		if shellbridge.IsExitSlash(line) {
			return nil
		}

		if strings.HasPrefix(line, "/") {
			handled, err := r.handleSlashCommand(loopCtx, line)
			if err != nil {
				fmt.Fprintf(r.stdout, "\n[error] %v\n", err)
			}
			if handled {
				fmt.Fprintln(r.stdout)
				fmt.Fprint(r.stdout, r.prompt())
				continue
			}
		}

		askCtx, cancel := context.WithCancel(loopCtx)
		askCancelMu.Lock()
		askCancel = cancel
		askCancelMu.Unlock()

		r.mu.Lock()
		sessionID := r.pinnedSession
		forceNew := r.forceNewNext
		r.forceNewNext = false
		r.pinnedSession = ""
		r.mu.Unlock()

		req := core.AskRequest{
			Prompt:    line,
			CWD:       r.cwd,
			SessionID: sessionID,
			ForceNew:  forceNew,
			Agent:     r.effectiveAgent(),
			Model:     r.effectiveModel(),
			Variant:   r.cfg.DefaultVariant,
			Mode:      core.ModeAsk,
		}

		if err := r.runner.Run(askCtx, req); err != nil {
			if askCtx.Err() != nil {
				fmt.Fprintln(r.stdout, "\n[cancelled]")
			} else {
				fmt.Fprintf(r.stdout, "\n[error] %v\n", err)
			}
		}

		cancel()
		askCancelMu.Lock()
		askCancel = nil
		askCancelMu.Unlock()

		fmt.Fprintln(r.stdout)
		fmt.Fprint(r.stdout, r.prompt())
	}
}

func (r *repl) handleSlashCommand(ctx context.Context, line string) (bool, error) {
	action, err := shellbridge.ParseControl(line)
	if err != nil {
		suggestion := shellbridge.SuggestSlash(strings.Fields(line)[0])
		if suggestion != "" {
			return true, fmt.Errorf("%w; %s", err, suggestion)
		}
		return false, nil
	}

	switch action.Kind {
	case shellbridge.ControlHelp:
		_, err := fmt.Fprintln(r.stdout, "\n"+shellbridge.HelpText())
		return true, err

	case shellbridge.ControlExit:
		return true, nil

	case shellbridge.ControlAgent:
		return r.handleAgentControl(ctx, action)

	case shellbridge.ControlModel:
		return r.handleModelControl(ctx, action)

	case shellbridge.ControlNew:
		r.mu.Lock()
		r.forceNewNext = true
		r.pinnedSession = ""
		r.mu.Unlock()
		fmt.Fprintln(r.stdout, "\n[new] next prompt will start a fresh session")
		return true, nil

	case shellbridge.ControlAsk:
		askCtx, cancel := context.WithCancel(ctx)
		defer cancel()

		r.mu.Lock()
		sessionID := r.pinnedSession
		forceNew := r.forceNewNext
		r.forceNewNext = false
		r.pinnedSession = ""
		r.mu.Unlock()

		req := core.AskRequest{
			Prompt:    action.Prompt,
			CWD:       r.cwd,
			SessionID: sessionID,
			ForceNew:  forceNew,
			Agent:     r.effectiveAgent(),
			Model:     r.effectiveModel(),
			Variant:   r.cfg.DefaultVariant,
			Mode:      core.ModeAsk,
		}
		if err := r.runner.Run(askCtx, req); err != nil {
			if askCtx.Err() != nil {
				fmt.Fprintln(r.stdout, "\n[cancelled]")
			} else {
				return true, err
			}
		}
		return true, nil

	case shellbridge.ControlSessionList:
		summaries, err := r.sessions.List(ctx, session.Scope{})
		if err != nil {
			return true, fmt.Errorf("session list: %w", err)
		}
		if len(summaries) == 0 {
			fmt.Fprintln(r.stdout, "\n(no sessions)")
			return true, nil
		}
		fmt.Fprintln(r.stdout)
		for _, s := range summaries {
			timeStr := formatUnixTime(s.Updated)
			fmt.Fprintf(r.stdout, "%s\t%s\t%s\t%s\n", s.ID, s.Title, s.Directory, timeStr)
		}
		return true, nil

	case shellbridge.ControlSessionContinue:
		sessCtx, err := r.sessions.Continue(ctx, action.SessionID)
		if err != nil {
			return true, fmt.Errorf("session continue: %w", err)
		}
		r.mu.Lock()
		r.pinnedSession = sessCtx.ID
		r.forceNewNext = false
		r.mu.Unlock()
		fmt.Fprintf(r.stdout, "\ncontinued session %s\n", sessCtx.ID)
		return true, nil

	default:
		return false, nil
	}
}

func (r *repl) handleAgentControl(ctx context.Context, action shellbridge.ControlAction) (bool, error) {
	value := strings.TrimSpace(action.Value)

	if value == "" {
		// Interactive: list agents from server and let user select.
		agents, err := r.transport.ListAgents(ctx, "", "")
		if err != nil {
			return true, fmt.Errorf("list agents: %w", err)
		}
		if len(agents) == 0 {
			return true, fmt.Errorf("no agents available from server")
		}

		options := make([]terminal.ListOption, len(agents))
		for i, a := range agents {
			label := a.Name
			if a.Description != nil && *a.Description != "" {
				label = fmt.Sprintf("%s  — %s", a.Name, *a.Description)
			}
			options[i] = terminal.ListOption{Label: label, Value: a.Name}
		}

		fmt.Fprintln(r.stdout) // move to new line before selector
		v, vok := terminal.RunSelect(ctx, r.stdinFile, r.stdoutFile, "Select agent:", options)
		if !vok {
			fmt.Fprintln(r.stdout, "\n[cancelled]")
			return true, nil
		}
		value = v
	}

	// Persist to config file.
	if err := r.configWriter.SetDefaultAgent(value); err != nil {
		return true, fmt.Errorf("save agent config: %w", err)
	}

	r.mu.Lock()
	r.agentOverride = value
	r.forceNewNext = true
	r.pinnedSession = ""
	r.mu.Unlock()
	fmt.Fprintf(r.stdout, "\n[agent] set to %q (saved to %s)\n", value, r.configWriter.ConfigPath())
	return true, nil
}

func (r *repl) handleModelControl(ctx context.Context, action shellbridge.ControlAction) (bool, error) {
	value := strings.TrimSpace(action.Value)

	if value == "" {
		// Interactive: list providers and their models, let user select.
		selValue, err := r.interactiveModelSelect(ctx)
		if err != nil {
			return true, err
		}
		if selValue == "" {
			return true, nil // cancelled
		}
		value = selValue
	}

	// Parse provider/model format.
	providerID, modelID, ok := strings.Cut(value, "/")
	if !ok || strings.TrimSpace(providerID) == "" || strings.TrimSpace(modelID) == "" {
		return true, fmt.Errorf("model must be in provider/model format (e.g. opencode/gpt-4)")
	}
	providerID = strings.TrimSpace(providerID)
	modelID = strings.TrimSpace(modelID)

	// Check if the selected model has variants.
	model, err := r.findModel(ctx, providerID, modelID)
	if err != nil {
		return true, err
	}

	variant := ""
	if model != nil && len(model.Variants) > 0 {
		// Interactive variant selection.
		variantIDs := make([]string, 0, len(model.Variants))
		for vID := range model.Variants {
			variantIDs = append(variantIDs, vID)
		}
		options := make([]terminal.ListOption, len(variantIDs))
		for i, vID := range variantIDs {
			options[i] = terminal.ListOption{Label: vID, Value: vID}
		}

		fmt.Fprintln(r.stdout)
		v, vok := terminal.RunSelect(ctx, r.stdinFile, r.stdoutFile, "Select variant for "+value+":", options)
		if !vok {
			fmt.Fprintln(r.stdout, "\n[cancelled]")
			return true, nil
		}
		variant = v
	}

	// Persist to config file.
	modelStr := providerID + "/" + modelID
	if err := r.configWriter.SetDefaultModel(modelStr); err != nil {
		return true, fmt.Errorf("save model config: %w", err)
	}
	if variant != "" {
		if err := r.configWriter.SetDefaultVariant(variant); err != nil {
			return true, fmt.Errorf("save variant config: %w", err)
		}
	}

	r.mu.Lock()
	r.modelOverride = modelStr
	r.mu.Unlock()

	if variant != "" {
		fmt.Fprintf(r.stdout, "\n[model] set to %q (variant: %s, saved to %s)\n", modelStr, variant, r.configWriter.ConfigPath())
	} else {
		fmt.Fprintf(r.stdout, "\n[model] set to %q (saved to %s)\n", modelStr, r.configWriter.ConfigPath())
	}
	return true, nil
}

// interactiveModelSelect presents a combined provider/model list for selection.
func (r *repl) interactiveModelSelect(ctx context.Context) (string, error) {
	providers, err := r.transport.ListProviders(ctx, "", "")
	if err != nil {
		return "", fmt.Errorf("list providers: %w", err)
	}
	if len(providers.All) == 0 {
		return "", fmt.Errorf("no providers available from server")
	}

	var options []terminal.ListOption
	connected := make(map[string]bool)
	for _, c := range providers.Connected {
		connected[c] = true
	}

	for _, p := range providers.All {
		if !connected[p.ID] {
			continue
		}
		models, _ := transport.ProviderModels(p)
		for _, m := range models {
			label := fmt.Sprintf("%s/%s  — %s", p.ID, m.ID, m.Name)
			options = append(options, terminal.ListOption{
				Label: label,
				Value: p.ID + "/" + m.ID,
			})
		}
	}

	if len(options) == 0 {
		return "", fmt.Errorf("no models available from connected providers")
	}

	fmt.Fprintln(r.stdout)
	value, ok := terminal.RunSelect(ctx, r.stdinFile, r.stdoutFile, "Select model:", options)
	if !ok {
		fmt.Fprintln(r.stdout, "\n[cancelled]")
		return "", nil
	}
	return value, nil
}

// findModel looks up a model by provider and model ID.
func (r *repl) findModel(ctx context.Context, providerID, modelID string) (*transport.Model, error) {
	providers, err := r.transport.ListProviders(ctx, "", "")
	if err != nil {
		return nil, fmt.Errorf("list providers: %w", err)
	}
	for _, p := range providers.All {
		if p.ID != providerID {
			continue
		}
		models, _ := transport.ProviderModels(p)
		for _, m := range models {
			if m.ID == modelID {
				cp := m
				return &cp, nil
			}
		}
	}
	return nil, nil // model not found; variants assumed empty
}

func formatUnixTime(ts int) string {
	if ts == 0 {
		return "-"
	}
	return fmt.Sprintf("%d", ts)
}
