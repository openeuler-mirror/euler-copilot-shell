package shellbridge

import (
	"fmt"
	"strings"
)

// ControlKind identifies a supported slash control command.
type ControlKind string

const (
	ControlAsk             ControlKind = "ask"
	ControlAgent           ControlKind = "agent"
	ControlModel           ControlKind = "model"
	ControlSessionHelp     ControlKind = "session_help"
	ControlSessionList     ControlKind = "session_list"
	ControlSessionContinue ControlKind = "session_continue"
	ControlNew             ControlKind = "new"
	ControlHelp            ControlKind = "help"
	ControlExit            ControlKind = "exit"
)

// ControlAction is the normalized form of a whitelisted slash command.
type ControlAction struct {
	Kind      ControlKind
	Raw       string
	Prompt    string
	Value     string
	SessionID string
}

// ControlRule defines one slash command form accepted by both Go and Bash.
type ControlRule struct {
	Command    string
	Subcommand string
	Kind       ControlKind
	MinWords   int
	MaxWords   int // zero means unbounded
}

var controlRules = []ControlRule{
	{Command: "/exit", Kind: ControlExit, MinWords: 1, MaxWords: 1},
	{Command: "/quit", Kind: ControlExit, MinWords: 1, MaxWords: 1},
	{Command: "/q", Kind: ControlExit, MinWords: 1, MaxWords: 1},
	{Command: "/ask", Kind: ControlAsk, MinWords: 2},
	{Command: "/agent", Kind: ControlAgent, MinWords: 1},
	{Command: "/model", Kind: ControlModel, MinWords: 1},
	{Command: "/new", Kind: ControlNew, MinWords: 1, MaxWords: 1},
	{Command: "/help", Kind: ControlHelp, MinWords: 1, MaxWords: 1},
	{Command: "/session", Kind: ControlSessionHelp, MinWords: 1, MaxWords: 1},
	{Command: "/session", Subcommand: "list", Kind: ControlSessionList, MinWords: 2, MaxWords: 2},
	{Command: "/session", Subcommand: "continue", Kind: ControlSessionContinue, MinWords: 3, MaxWords: 3},
}

// IsExitSlash returns true when the raw input is an exit slash command.
func IsExitSlash(raw string) bool {
	fields := strings.Fields(strings.TrimSpace(raw))
	if len(fields) == 0 {
		return false
	}
	command := strings.ToLower(fields[0])
	for _, rule := range controlRules {
		if rule.Command == command && rule.Kind == ControlExit {
			return true
		}
	}
	return false
}

// ParseControl parses slash commands that the shell adapter is allowed to dispatch.
func ParseControl(raw string) (ControlAction, error) {
	line := strings.TrimSpace(raw)
	if line == "" {
		return ControlAction{}, fmt.Errorf("shell control command is required")
	}
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return ControlAction{}, fmt.Errorf("shell control command is required")
	}

	rule, ok := matchControlRule(fields)
	if !ok {
		return ControlAction{}, fmt.Errorf("unsupported shell control command %q; %s", fields[0], SuggestSlash(fields[0]))
	}

	action := ControlAction{Kind: rule.Kind, Raw: line}
	switch rule.Kind {
	case ControlAsk:
		action.Prompt = controlRemainder(line, fields[0])
	case ControlAgent, ControlModel:
		action.Value = controlRemainder(line, fields[0])
	case ControlSessionContinue:
		action.SessionID = fields[2]
	}
	return action, nil
}

func matchControlRule(fields []string) (ControlRule, bool) {
	command := strings.ToLower(fields[0])
	subcommand := ""
	if len(fields) > 1 {
		subcommand = strings.ToLower(fields[1])
	}
	for _, rule := range controlRules {
		if rule.Command != command || (rule.Subcommand != "" && rule.Subcommand != subcommand) {
			continue
		}
		if len(fields) < rule.MinWords || (rule.MaxWords > 0 && len(fields) > rule.MaxWords) {
			continue
		}
		return rule, true
	}
	return ControlRule{}, false
}

func controlRemainder(line, command string) string {
	return strings.TrimSpace(line[len(command):])
}

var knownSlashCommands = func() []string {
	seen := make(map[string]bool, len(controlRules))
	commands := make([]string, 0, len(controlRules))
	for _, rule := range controlRules {
		if !seen[rule.Command] {
			seen[rule.Command] = true
			commands = append(commands, rule.Command)
		}
	}
	return commands
}()

// SuggestSlash returns a suggestion for a mistyped slash command, or empty string.
func SuggestSlash(input string) string {
	if input == "" || !strings.HasPrefix(input, "/") {
		return ""
	}
	lower := strings.ToLower(strings.TrimSpace(input))
	best := ""
	bestDist := 3
	for _, cmd := range knownSlashCommands {
		if lower == cmd {
			return "" // exact match, not a suggestion
		}
		if strings.HasPrefix(cmd, lower) {
			return "did you mean " + cmd + "?"
		}
		d := levenshteinDistance(lower, cmd)
		if d < bestDist {
			bestDist = d
			best = cmd
		}
	}
	if best != "" && bestDist <= 2 {
		return "did you mean " + best + "?"
	}
	return ""
}

func levenshteinDistance(a, b string) int {
	n, m := len(a), len(b)
	if n == 0 {
		return m
	}
	if m == 0 {
		return n
	}
	dp := make([][]int, n+1)
	for i := range dp {
		dp[i] = make([]int, m+1)
		dp[i][0] = i
	}
	for j := range dp[0] {
		dp[0][j] = j
	}
	for i := 1; i <= n; i++ {
		for j := 1; j <= m; j++ {
			cost := 1
			if a[i-1] == b[j-1] {
				cost = 0
			}
			dp[i][j] = min3(
				dp[i-1][j]+1,
				dp[i][j-1]+1,
				dp[i-1][j-1]+cost,
			)
		}
	}
	return dp[n][m]
}

func min3(a, b, c int) int {
	if a <= b && a <= c {
		return a
	}
	if b <= c {
		return b
	}
	return c
}

// HelpText returns the slash command help text used by REPL and shell-control.
func HelpText() string {
	return strings.TrimSpace(`Witty slash commands:
  /help                      Show this help
  /exit, /quit, /q           Exit the REPL
  /ask <prompt>              Ask opencode explicitly
  /agent [name]              Show or set the default agent
  /model [provider/model]    Show or set the default model
  /new                       Start a fresh session on the next prompt
  /session                   Show session command usage
  /session list              List opencode sessions
  /session continue <id>     Continue a session by id`)
}

// SessionHelpText returns the detailed usage of the /session command.
func SessionHelpText() string {
	return strings.TrimSpace(`Witty session commands:
  /session                   Show this help
  /session list              List opencode sessions
  /session continue <id>     Continue a session by id`)
}
