package cli

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"
)

func newAskCommand(opts *rootOptions) *cobra.Command {
	return &cobra.Command{
		Use:   "ask <prompt>",
		Short: "Ask opencode a single prompt",
		Args:  cobra.MinimumNArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			prompt := strings.Join(args, " ")
			if err := container.Ask(cmd.Context(), prompt); err != nil {
				return fmt.Errorf("ask: %w", err)
			}
			return nil
		},
	}
}
