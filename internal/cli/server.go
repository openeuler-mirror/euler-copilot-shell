package cli

import (
	"fmt"

	"github.com/spf13/cobra"
)

func newServerCommand(opts *rootOptions) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "server",
		Short: "Manage opencode server lifecycle",
	}
	cmd.AddCommand(newServerStatusCommand(opts))
	cmd.AddCommand(newServerStopCommand(opts))
	cmd.AddCommand(newServerRestartCommand(opts))
	return cmd
}

func newServerStatusCommand(opts *rootOptions) *cobra.Command {
	return &cobra.Command{
		Use:   "status",
		Short: "Show opencode server running status",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			// Avoid the side effect of starting a server just to report status.
			opts.skipServerEnsure = true
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			defer container.Close()
			mgr := container.ServerManager()
			if mgr == nil {
				_, err = fmt.Fprintln(cmd.OutOrStdout(),
					"Server management is not available (using explicit --server-url).")
				return err
			}
			st := mgr.Status(cmd.Context())
			running := "no"
			if st.Running {
				running = "yes"
			}
			managed := "no"
			if st.Managed {
				managed = "yes"
			}
			startedAt := st.StartedAt
			if startedAt == "" {
				startedAt = "unknown"
			}

			_, err = fmt.Fprintf(cmd.OutOrStdout(),
				"Running:    %s\n"+
					"Port:       %d\n"+
					"PID:        %d\n"+
					"Managed:    %s\n"+
					"StartedAt:  %s\n",
				running, st.Port, st.PID, managed, startedAt)
			return err
		},
	}
}

func newServerStopCommand(opts *rootOptions) *cobra.Command {
	return &cobra.Command{
		Use:   "stop",
		Short: "Stop the managed opencode server",
		Args:  cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			// Avoid the side effect of starting a server just to stop one.
			opts.skipServerEnsure = true
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			defer container.Close()
			mgr := container.ServerManager()
			if mgr == nil {
				_, err = fmt.Fprintln(cmd.OutOrStdout(),
					"Server management is not available (using explicit --server-url).")
				return err
			}

			// Stop reads the state file and disposes the server via the
			// /global/dispose API (with SIGTERM fallback). Any witty process
			// holding the state file password can stop the server, so there is
			// no managed-only precondition here.
			if err := mgr.Stop(cmd.Context()); err != nil {
				return err
			}
			_, err = fmt.Fprintln(cmd.OutOrStdout(), "Server stopped.")
			return err
		},
	}
}

func newServerRestartCommand(opts *rootOptions) *cobra.Command {
	return &cobra.Command{
		Use:   "restart",
		Short: "Restart the opencode server to pick up config changes",
		Long: "Stop the currently running opencode server and start a fresh one. " +
			"Use this after installing or removing agent/skill/MCP config files " +
			"so the server picks up the latest configuration.",
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			// Load app WITHOUT skipServerEnsure (we want Ensure after stop).
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			defer container.Close()
			mgr := container.ServerManager()
			if mgr == nil {
				_, err = fmt.Fprintln(cmd.OutOrStdout(),
					"Server management is not available (using explicit --server-url).")
				return err
			}

			// 1. Stop the existing server.
			if err := mgr.Stop(cmd.Context()); err != nil {
				return fmt.Errorf("stop server: %w", err)
			}

			// 2. Start a fresh server via Ensure.
			conn, err := mgr.Ensure(cmd.Context())
			if err != nil {
				return fmt.Errorf("start server: %w", err)
			}
			_, err = fmt.Fprintf(cmd.OutOrStdout(), "Server restarted on %s.\n", conn.URL)
			return err
		},
	}
}
