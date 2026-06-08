package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newDoctorCommand(opts *rootOptions) *cobra.Command {
	return &cobra.Command{
		Use:   "doctor",
		Short: "Run environment diagnostics",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			report, err := container.Doctor(cmd.Context())
			if err != nil {
				return err
			}
			_, err = fmt.Fprint(cmd.OutOrStdout(), report)
			return err
		},
	}
}
