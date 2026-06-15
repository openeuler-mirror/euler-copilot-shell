package cli

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/witty-cli/internal/core"
	wittyterm "atomgit.com/openeuler/witty-cli/internal/terminal"
)

func newAskCommand(opts *rootOptions) *cobra.Command {
	var forceNew bool
	var sessionID string

	cmd := &cobra.Command{
		Use:   "ask [prompt]",
		Short: "Ask opencode a single prompt",
		Long:  "Send one prompt to opencode and stream the response. Prompt text can be passed as command arguments or piped on stdin.",
		Example: strings.Join([]string{
			`witty ask "检查系统内存"`,
			`echo "解释这个函数" | witty ask --new`,
			`witty ask --session ses_123 "继续上次的重构"`,
		}, "\n"),
		Args: cobra.ArbitraryArgs,
		RunE: func(cmd *cobra.Command, args []string) error {
			if forceNew && strings.TrimSpace(sessionID) != "" {
				return fmt.Errorf("ask: --new and --session cannot be used together")
			}
			prompt, err := resolveAskPrompt(args, cmd.InOrStdin())
			if err != nil {
				return fmt.Errorf("ask: %w", err)
			}
			cwd, err := os.Getwd()
			if err != nil {
				return fmt.Errorf("ask: resolve cwd: %w", err)
			}
			container, err := opts.loadApp(cmd.Context(), cmd)
			if err != nil {
				return err
			}
			// When auto_resume is disabled, force a new session for each ask.
			if !container.Config().REPL.AutoResume && strings.TrimSpace(sessionID) == "" {
				forceNew = true
			}
			req := core.AskRequest{
				Prompt:    prompt,
				CWD:       cwd,
				SessionID: strings.TrimSpace(sessionID),
				ForceNew:  forceNew,
				Agent:     container.Config().DefaultAgent,
				Model:     container.Config().DefaultModel,
				Variant:   container.Config().DefaultVariant,
				Mode:      core.ModeAsk,
			}
			if err := container.Ask(cmd.Context(), req); err != nil {
				return fmt.Errorf("ask: %w", err)
			}
			return nil
		},
	}
	flags := cmd.Flags()
	flags.BoolVar(&forceNew, "new", false, "create a new session instead of reusing the current directory session")
	flags.StringVar(&sessionID, "session", "", "continue the specified session ID")
	return cmd
}

func resolveAskPrompt(args []string, stdin io.Reader) (string, error) {
	if len(args) > 0 {
		prompt := strings.TrimSpace(strings.Join(args, " "))
		if prompt == "" {
			return "", fmt.Errorf("prompt is required")
		}
		return prompt, nil
	}
	if isTTYReader(stdin) {
		return "", fmt.Errorf("prompt is required; pass an argument or pipe stdin")
	}
	if stdin == nil {
		return "", fmt.Errorf("prompt is required; pass an argument or pipe stdin")
	}
	data, err := io.ReadAll(stdin)
	if err != nil {
		return "", fmt.Errorf("read stdin prompt: %w", err)
	}
	prompt := strings.TrimSpace(string(data))
	if prompt == "" {
		return "", fmt.Errorf("prompt is required; pass an argument or pipe stdin")
	}
	return prompt, nil
}

func isTTYReader(reader io.Reader) bool {
	file, ok := reader.(*os.File)
	if !ok {
		return false
	}
	return wittyterm.IsTerminal(file)
}
