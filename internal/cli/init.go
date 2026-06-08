package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newInitCommand(opts *rootOptions) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "init",
		Short: "Generate shell integration snippets",
	}
	cmd.AddCommand(&cobra.Command{
		Use:   "bash",
		Short: "Print Bash integration script",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			script, err := container.InitBash(cmd.Context())
			if err != nil {
				return err
			}
			_, err = fmt.Fprint(cmd.OutOrStdout(), script)
			return err
		},
	})
	return cmd
}
