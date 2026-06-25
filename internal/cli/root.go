package cli

import (
	"context"
	"io"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/euler-copilot-shell/internal/app"
	"atomgit.com/openeuler/euler-copilot-shell/internal/config"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
)

type rootOptions struct {
	configPath string
	serverURL  string
	agent      string
	model      string
	variant    string
	debug      bool
	noColor    bool
	version    version.Info
	stdout     io.Writer
	stderr     io.Writer
	loadAppFn  func(ctx context.Context, cmd *cobra.Command) (app.Container, error)
}

// Execute builds and runs the Cobra command tree.
func Execute(ctx context.Context, args []string, stdout, stderr io.Writer, info version.Info) error {
	cmd := NewRootCommand(info, stdout, stderr)
	cmd.SetArgs(args)
	return cmd.ExecuteContext(ctx)
}

// NewRootCommand returns the complete public CLI tree.
func NewRootCommand(info version.Info, stdout, stderr io.Writer) *cobra.Command {
	return newRootCommandWithOptions(&rootOptions{version: info, stdout: stdout, stderr: stderr})
}

func newRootCommandWithOptions(opts *rootOptions) *cobra.Command {
	cmd := &cobra.Command{
		Use:           "witty",
		Short:         "openEuler terminal AI assistant",
		SilenceUsage:  true,
		SilenceErrors: true,
		RunE: func(cmd *cobra.Command, _ []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			return container.StartREPL(cmd.Context())
		},
	}
	cmd.SetOut(opts.stdout)
	cmd.SetErr(opts.stderr)
	cmd.CompletionOptions.DisableDefaultCmd = true
	cmd.Version = opts.version.Version
	cmd.SetVersionTemplate(opts.version.String() + "\n")

	flags := cmd.PersistentFlags()
	flags.StringVar(&opts.configPath, "config", "", "path to config file")
	flags.StringVar(&opts.serverURL, "server-url", "", "opencode server URL")
	flags.StringVar(&opts.agent, "agent", "", "default opencode agent")
	flags.StringVar(&opts.model, "model", "", "default opencode model (provider/model)")
	flags.StringVar(&opts.variant, "variant", "", "default model variant (e.g. reasoning level)")
	flags.BoolVar(&opts.debug, "debug", false, "enable debug logs")
	flags.BoolVar(&opts.noColor, "no-color", false, "disable colored output")

	cmd.AddCommand(newAskCommand(opts))
	cmd.AddCommand(newInitCommand(opts))
	cmd.AddCommand(newSessionCommand(opts))
	cmd.AddCommand(newContinueCommand(opts))
	cmd.AddCommand(newProviderCommand(opts))
	cmd.AddCommand(newDoctorCommand(opts))
	cmd.AddCommand(newShellControlCommand(opts))
	cmd.AddCommand(newVersionCommand(opts))
	return cmd
}

func (o *rootOptions) loadApp(ctx context.Context, cmd *cobra.Command) (app.Container, error) {
	if o.loadAppFn != nil {
		return o.loadAppFn(ctx, cmd)
	}
	flags := cmd.Root().PersistentFlags()
	overrides := config.Overrides{}
	if flags.Changed("server-url") {
		overrides.ServerURL = o.serverURL
	}
	if flags.Changed("agent") {
		overrides.DefaultAgent = o.agent
	}
	if flags.Changed("model") {
		overrides.DefaultModel = o.model
	}
	if flags.Changed("variant") {
		overrides.DefaultVariant = o.variant
	}
	if flags.Changed("debug") {
		overrides.Debug = &o.debug
	}
	if flags.Changed("no-color") {
		overrides.NoColor = &o.noColor
	}

	return app.New(ctx, app.Options{
		Config: config.LoadOptions{
			ConfigPath: o.configPath,
			Overrides:  overrides,
		},
		Version:   o.version,
		Stdout:    o.stdout,
		Stderr:    o.stderr,
		ServerURL: overrides.ServerURL,
	})
}
