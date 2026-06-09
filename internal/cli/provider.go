package cli

import (
	"fmt"
	"io"
	"strings"
	"text/tabwriter"

	"github.com/spf13/cobra"
)

func newProviderCommand(opts *rootOptions) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "provider",
		Short: "Manage opencode providers",
	}
	cmd.AddCommand(newProviderListCommand(opts))
	cmd.AddCommand(newProviderConnectCommand(opts))
	return cmd
}

func newProviderListCommand(opts *rootOptions) *cobra.Command {
	var connectedOnly bool
	cmd := &cobra.Command{
		Use:   "list",
		Short: "List providers that support API key authentication",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			providers, err := container.ListProviders(cmd.Context())
			if err != nil {
				return fmt.Errorf("provider list: %w", err)
			}
			tw := tabwriter.NewWriter(cmd.OutOrStdout(), 0, 4, 2, ' ', 0)
			if _, err := fmt.Fprintln(tw, "STATUS\tID\tNAME\tDEFAULT_MODEL"); err != nil {
				return err
			}
			for _, provider := range providers {
				if connectedOnly && !provider.Connected {
					continue
				}
				status := "-"
				if provider.Connected {
					status = "connected"
				}
				name := provider.Name
				if strings.TrimSpace(name) == "" {
					name = provider.ID
				}
				if _, err := fmt.Fprintf(tw, "%s\t%s\t%s\t%s\n", status, provider.ID, name, provider.DefaultModel); err != nil {
					return err
				}
			}
			return tw.Flush()
		},
	}
	cmd.Flags().BoolVar(&connectedOnly, "connected", false, "show only connected providers")
	return cmd
}

func newProviderConnectCommand(opts *rootOptions) *cobra.Command {
	var apiKey string
	cmd := &cobra.Command{
		Use:   "connect <provider>",
		Short: "Connect a provider using API key",
		Args:  cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			key, err := resolveProviderAPIKeyInput(apiKey, cmd.InOrStdin())
			if err != nil {
				return fmt.Errorf("provider connect: %w", err)
			}
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			provider, err := container.ConnectProviderWithAPIKey(cmd.Context(), args[0], key)
			if err != nil {
				return fmt.Errorf("provider connect: %w", err)
			}
			_, err = fmt.Fprintf(cmd.OutOrStdout(), "connected provider %s\n", provider.ID)
			return err
		},
	}
	cmd.Flags().StringVar(&apiKey, "key", "", "provider API key (if omitted, witty reads stdin or provider env vars)")
	return cmd
}

func resolveProviderAPIKeyInput(flagValue string, stdin io.Reader) (string, error) {
	if key := strings.TrimSpace(flagValue); key != "" {
		return key, nil
	}
	if stdin == nil || isTTYReader(stdin) {
		return "", nil
	}
	data, err := io.ReadAll(stdin)
	if err != nil {
		return "", fmt.Errorf("read provider API key from stdin: %w", err)
	}
	return strings.TrimSpace(string(data)), nil
}
