package cli

import (
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/shellbridge"
	"atomgit.com/openeuler/witty-cli/internal/terminal"
	"atomgit.com/openeuler/witty-cli/internal/transport"
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
	case shellbridge.ControlExit:
		return nil
	case shellbridge.ControlNew:
		_, err := fmt.Fprintln(cmd.OutOrStdout(), "[new] next witty ask will start a fresh session")
		return err
	case shellbridge.ControlAgent:
		return runShellAgentControl(cmd, opts, action)
	case shellbridge.ControlModel:
		return runShellModelControl(cmd, opts, action)
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
			if _, err := fmt.Fprintf(cmd.OutOrStdout(), "%s\t%s\t%s\t%d\n", summary.ID, summary.Title, summary.Directory, summary.Updated); err != nil {
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

func runShellAgentControl(cmd *cobra.Command, opts *rootOptions, action shellbridge.ControlAction) error {
	value := strings.TrimSpace(action.Value)

	if value == "" {
		inFile, inOK := cmd.InOrStdin().(*os.File)
		outFile, outOK := cmd.OutOrStdout().(*os.File)
		if !inOK || !outOK {
			return fmt.Errorf("interactive agent selection requires a terminal; use /agent <name> to set directly")
		}

		container, err := opts.loadApp(cmd.Context(), cmd)
		if err != nil {
			return err
		}
		transportClient := container.Transport()
		if transportClient == nil {
			return fmt.Errorf("transport not available; use /agent <name> to set directly")
		}

		agents, err := transportClient.ListAgents(cmd.Context(), "", "")
		if err != nil {
			return fmt.Errorf("list agents: %w", err)
		}
		if len(agents) == 0 {
			return fmt.Errorf("no agents available")
		}

		options := make([]terminal.ListOption, len(agents))
		for i, a := range agents {
			label := a.Name
			if a.Description != nil && *a.Description != "" {
				label = fmt.Sprintf("%s  — %s", a.Name, *a.Description)
			}
			options[i] = terminal.ListOption{Label: label, Value: a.Name}
		}

		result, selErr := terminal.RunSelector(inFile, outFile, "Select agent:", options)
		if selErr != nil {
			return fmt.Errorf("agent selection: %w", selErr)
		}
		if result == nil {
			return nil
		}
		value = result.Value
	}

	container, err := opts.loadApp(cmd.Context(), cmd)
	if err != nil {
		return err
	}
	if err := container.WriteConfig(cmd.Context()).SetDefaultAgent(value); err != nil {
		return fmt.Errorf("save agent config: %w", err)
	}
	_, err = fmt.Fprintf(cmd.OutOrStdout(), "[agent] set to %q (saved to %s)\n", value, container.WriteConfig(cmd.Context()).ConfigPath())
	return err
}

func runShellModelControl(cmd *cobra.Command, opts *rootOptions, action shellbridge.ControlAction) error {
	value := strings.TrimSpace(action.Value)

	if value == "" {
		container, err := opts.loadApp(cmd.Context(), cmd)
		if err != nil {
			return err
		}
		transportClient := container.Transport()
		if transportClient == nil {
			return fmt.Errorf("transport not available; use /model <provider/model> to set directly")
		}

		selValue, err := interactiveShellModelSelect(cmd, transportClient)
		if err != nil {
			return err
		}
		if selValue == "" {
			return nil
		}
		value = selValue
	}

	container, err := opts.loadApp(cmd.Context(), cmd)
	if err != nil {
		return err
	}

	providerID, modelID, ok := strings.Cut(value, "/")
	if !ok || strings.TrimSpace(providerID) == "" || strings.TrimSpace(modelID) == "" {
		return fmt.Errorf("model must be in provider/model format (e.g. opencode/gpt-4)")
	}
	providerID = strings.TrimSpace(providerID)
	modelID = strings.TrimSpace(modelID)

	// Check variants.
	variant := ""
	model := findShellModel(cmd, container.Transport(), providerID, modelID)
	if model != nil && len(model.Variants) > 0 {
		variantIDs := make([]string, 0, len(model.Variants))
		for vID := range model.Variants {
			variantIDs = append(variantIDs, vID)
		}
		options := make([]terminal.ListOption, len(variantIDs))
		for i, vID := range variantIDs {
			options[i] = terminal.ListOption{Label: vID, Value: vID}
		}

		inFile, _ := cmd.InOrStdin().(*os.File)
		outFile, _ := cmd.OutOrStdout().(*os.File)
		if inFile != nil && outFile != nil {
			result, selErr := terminal.RunSelector(inFile, outFile, "Select variant for "+value+":", options)
			if selErr != nil {
				return fmt.Errorf("variant selection: %w", selErr)
			}
			if result == nil {
				return nil
			}
			variant = result.Value
		}
	}

	modelStr := providerID + "/" + modelID
	if err := container.WriteConfig(cmd.Context()).SetDefaultModel(modelStr); err != nil {
		return fmt.Errorf("save model config: %w", err)
	}
	if variant != "" {
		if err := container.WriteConfig(cmd.Context()).SetDefaultVariant(variant); err != nil {
			return fmt.Errorf("save variant config: %w", err)
		}
	}

	if variant != "" {
		_, err = fmt.Fprintf(cmd.OutOrStdout(), "[model] set to %q (variant: %s, saved to %s)\n", modelStr, variant, container.WriteConfig(cmd.Context()).ConfigPath())
	} else {
		_, err = fmt.Fprintf(cmd.OutOrStdout(), "[model] set to %q (saved to %s)\n", modelStr, container.WriteConfig(cmd.Context()).ConfigPath())
	}
	return err
}

func interactiveShellModelSelect(cmd *cobra.Command, client transport.Client) (string, error) {
	if client == nil {
		return "", fmt.Errorf("transport not available")
	}
	providers, err := client.ListProviders(cmd.Context(), "", "")
	if err != nil {
		return "", fmt.Errorf("list providers: %w", err)
	}
	if len(providers.All) == 0 {
		return "", fmt.Errorf("no providers available")
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

	inFile, _ := cmd.InOrStdin().(*os.File)
	outFile, _ := cmd.OutOrStdout().(*os.File)
	if inFile == nil || outFile == nil {
		return "", fmt.Errorf("interactive model selection requires a terminal")
	}

	result, selErr := terminal.RunSelector(inFile, outFile, "Select model:", options)
	if selErr != nil {
		return "", fmt.Errorf("model selection: %w", selErr)
	}
	if result == nil {
		return "", nil
	}
	return result.Value, nil
}

func findShellModel(cmd *cobra.Command, client transport.Client, providerID, modelID string) *transport.Model {
	if client == nil {
		return nil
	}
	providers, err := client.ListProviders(cmd.Context(), "", "")
	if err != nil {
		return nil
	}
	for _, p := range providers.All {
		if p.ID != providerID {
			continue
		}
		models, _ := transport.ProviderModels(p)
		for _, m := range models {
			if m.ID == modelID {
				cp := m
				return &cp
			}
		}
	}
	return nil
}
