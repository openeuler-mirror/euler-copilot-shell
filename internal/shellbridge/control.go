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

// IsExitSlash returns true when the raw input is an exit slash command.
func IsExitSlash(raw string) bool {
	fields := strings.Fields(strings.TrimSpace(raw))
	if len(fields) == 0 {
		return false
	}
	switch strings.ToLower(fields[0]) {
	case "/exit", "/quit", "/q":
		return true
	default:
		return false
	}
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

	lower := strings.ToLower(fields[0])
	switch lower {
	case "/exit", "/quit", "/q":
		if len(fields) != 1 {
			return ControlAction{}, fmt.Errorf("%s does not accept arguments", fields[0])
		}
		return ControlAction{Kind: ControlExit, Raw: line}, nil
	case "/ask":
		prompt := strings.TrimSpace(strings.TrimPrefix(line, "/ask"))
		if prompt == "" {
			return ControlAction{}, fmt.Errorf("/ask requires a prompt")
		}
		return ControlAction{Kind: ControlAsk, Raw: line, Prompt: prompt}, nil
	case "/agent":
		return ControlAction{Kind: ControlAgent, Raw: line, Value: strings.TrimSpace(strings.TrimPrefix(line, "/agent"))}, nil
	case "/model":
		return ControlAction{Kind: ControlModel, Raw: line, Value: strings.TrimSpace(strings.TrimPrefix(line, "/model"))}, nil
	case "/new":
		if len(fields) != 1 {
			return ControlAction{}, fmt.Errorf("/new does not accept arguments")
		}
		return ControlAction{Kind: ControlNew, Raw: line}, nil
	case "/help":
		if len(fields) != 1 {
			return ControlAction{}, fmt.Errorf("/help does not accept arguments")
		}
		return ControlAction{Kind: ControlHelp, Raw: line}, nil
	case "/session":
		return parseSessionControl(line, fields)
	default:
		return ControlAction{}, fmt.Errorf("unsupported shell control command %q; %s", fields[0], SuggestSlash(fields[0]))
	}
}

func parseSessionControl(line string, fields []string) (ControlAction, error) {
	if len(fields) < 2 {
		return ControlAction{}, fmt.Errorf("/session requires a subcommand")
	}
	switch fields[1] {
	case "list":
		if len(fields) != 2 {
			return ControlAction{}, fmt.Errorf("/session list does not accept arguments")
		}
		return ControlAction{Kind: ControlSessionList, Raw: line}, nil
	case "continue":
		if len(fields) != 3 {
			return ControlAction{}, fmt.Errorf("/session continue requires exactly one session id")
		}
		return ControlAction{Kind: ControlSessionContinue, Raw: line, SessionID: fields[2]}, nil
	default:
		return ControlAction{}, fmt.Errorf("unsupported /session subcommand %q", fields[1])
	}
}

var knownSlashCommands = []string{
	"/ask", "/agent", "/model", "/new", "/help", "/exit", "/quit", "/q", "/session",
}

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
  /session list              List opencode sessions
  /session continue <id>     Continue a session by id`)
}
