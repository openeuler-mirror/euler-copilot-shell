package cli

import (
	"context"
	"io"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/witty-cli/internal/app"
	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

type rootOptions struct {
	configPath string
	serverURL  string
	agent      string
	model      string
	debug      bool
	noColor    bool
	version    version.Info
	stdout     io.Writer
	stderr     io.Writer
}

// Execute builds and runs the Cobra command tree.
func Execute(ctx context.Context, args []string, stdout, stderr io.Writer, info version.Info) error {
	cmd := NewRootCommand(info, stdout, stderr)
	cmd.SetArgs(args)
	return cmd.ExecuteContext(ctx)
}

// NewRootCommand returns the complete public CLI tree.
func NewRootCommand(info version.Info, stdout, stderr io.Writer) *cobra.Command {
	opts := &rootOptions{version: info, stdout: stdout, stderr: stderr}

	cmd := &cobra.Command{
		Use:           "witty",
		Short:         "openEuler terminal AI assistant",
		SilenceUsage:  true,
		SilenceErrors: true,
		RunE: func(cmd *cobra.Command, _ []string) error {
			return cmd.Help()
		},
	}
	cmd.SetOut(stdout)
	cmd.SetErr(stderr)
	cmd.CompletionOptions.DisableDefaultCmd = true
	cmd.Version = info.Version
	cmd.SetVersionTemplate(info.String() + "\n")

	flags := cmd.PersistentFlags()
	flags.StringVar(&opts.configPath, "config", "", "path to config file")
	flags.StringVar(&opts.serverURL, "server-url", "", "opencode server URL")
	flags.StringVar(&opts.agent, "agent", "", "default opencode agent")
	flags.StringVar(&opts.model, "model", "", "default opencode model")
	flags.BoolVar(&opts.debug, "debug", false, "enable debug logs")
	flags.BoolVar(&opts.noColor, "no-color", false, "disable colored output")

	cmd.AddCommand(newAskCommand(opts))
	cmd.AddCommand(newInitCommand(opts))
	cmd.AddCommand(newSessionCommand(opts))
	cmd.AddCommand(newContinueCommand(opts))
	cmd.AddCommand(newDoctorCommand(opts))
	cmd.AddCommand(newVersionCommand(opts))
	return cmd
}

func (o *rootOptions) loadApp(ctx context.Context, cmd *cobra.Command) (app.Container, error) {
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
		Version: o.version,
		Stdout:  o.stdout,
		Stderr:  o.stderr,
	})
}
