package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newSessionCommand(opts *rootOptions) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "session",
		Short: "Manage opencode sessions",
	}
	cmd.AddCommand(&cobra.Command{
		Use:   "list",
		Short: "List sessions",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			summaries, err := container.ListSessions(cmd.Context())
			if err != nil {
				return fmt.Errorf("session list: %w", err)
			}
			for _, summary := range summaries {
				if _, err := fmt.Fprintf(cmd.OutOrStdout(), "%s\t%s\t%s\n", summary.ID, summary.Title, summary.Directory); err != nil {
					return err
				}
			}
			return nil
		},
	})
	cmd.AddCommand(&cobra.Command{
		Use:   "continue <id>",
		Short: "Continue a session by id",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			ctx, err := container.ContinueSession(cmd.Context(), args[0])
			if err != nil {
				return fmt.Errorf("session continue: %w", err)
			}
			_, err = fmt.Fprintf(cmd.OutOrStdout(), "continued session %s\n", ctx.ID)
			return err
		},
	})
	return cmd
}

func newContinueCommand(opts *rootOptions) *cobra.Command {
	return &cobra.Command{
		Use:   "continue <id>",
		Short: "Continue a session by id",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			ctx, err := container.ContinueSession(cmd.Context(), args[0])
			if err != nil {
				return fmt.Errorf("continue: %w", err)
			}
			_, err = fmt.Fprintf(cmd.OutOrStdout(), "continued session %s\n", ctx.ID)
			return err
		},
	}
}
