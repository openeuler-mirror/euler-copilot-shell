package cli

import (
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/shellbridge"
)

func newShellControlCommand(opts *rootOptions) *cobra.Command {
	cmd := &cobra.Command{
		Use:    "shell-control [raw]",
		Short:  "Handle hidden shell adapter control commands",
		Hidden: true,
		Args:   cobra.ArbitraryArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			raw := strings.TrimSpace(strings.Join(args, " "))
			action, err := shellbridge.ParseControl(raw)
			if err != nil {
				return fmt.Errorf("shell-control: %w", err)
			}
			return runShellControl(cmd, opts, action)
		},
	}
	return cmd
}

func runShellControl(cmd *cobra.Command, opts *rootOptions, action shellbridge.ControlAction) error {
	switch action.Kind {
	case shellbridge.ControlHelp:
		_, err := fmt.Fprintln(cmd.OutOrStdout(), shellbridge.HelpText())
		return err
	case shellbridge.ControlAgent:
		return printShellControlValue(cmd, "agent", strings.TrimSpace(action.Value), opts.agent)
	case shellbridge.ControlModel:
		return printShellControlValue(cmd, "model", strings.TrimSpace(action.Value), opts.model)
	case shellbridge.ControlNew:
		_, err := fmt.Fprintln(cmd.OutOrStdout(), "new session mode is available with: witty ask --new <prompt>")
		return err
	}

	container, err := opts.loadApp(cmd.Context(), cmd)
	if err != nil {
		return err
	}
	switch action.Kind {
	case shellbridge.ControlAsk:
		cwd, err := os.Getwd()
		if err != nil {
			return fmt.Errorf("shell-control ask: resolve cwd: %w", err)
		}
		req := core.AskRequest{
			Prompt:  action.Prompt,
			CWD:     cwd,
			Agent:   container.Config().DefaultAgent,
			Model:   container.Config().DefaultModel,
			Variant: container.Config().DefaultVariant,
			Mode:    core.ModeAsk,
		}
		if err := container.Ask(cmd.Context(), req); err != nil {
			return fmt.Errorf("shell-control ask: %w", err)
		}
		return nil
	case shellbridge.ControlSessionList:
		summaries, err := container.ListSessions(cmd.Context())
		if err != nil {
			return fmt.Errorf("shell-control session list: %w", err)
		}
		for _, summary := range summaries {
			if _, err := fmt.Fprintf(cmd.OutOrStdout(), "%s\t%s\t%s\n", summary.ID, summary.Title, summary.Directory); err != nil {
				return err
			}
		}
		return nil
	case shellbridge.ControlSessionContinue:
		ctx, err := container.ContinueSession(cmd.Context(), action.SessionID)
		if err != nil {
			return fmt.Errorf("shell-control session continue: %w", err)
		}
		_, err = fmt.Fprintf(cmd.OutOrStdout(), "continued session %s\n", ctx.ID)
		return err
	default:
		return fmt.Errorf("shell-control: unsupported action %q", action.Kind)
	}
}

func printShellControlValue(cmd *cobra.Command, name, value, flagValue string) error {
	if value == "" {
		if strings.TrimSpace(flagValue) != "" {
			_, err := fmt.Fprintf(cmd.OutOrStdout(), "%s: %s\n", name, strings.TrimSpace(flagValue))
			return err
		}
		_, err := fmt.Fprintf(cmd.OutOrStdout(), "%s is configured through --%s, WITTY_%s, or config.toml\n", name, name, strings.ToUpper(name))
		return err
	}
	_, err := fmt.Fprintf(cmd.OutOrStdout(), "%s override %q is supported by future REPL state; use --%s or config.toml for now\n", name, value, name)
	return err
}
