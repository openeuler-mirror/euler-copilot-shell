package shellbridge

import (
	"regexp"
	"strings"
	"unicode"
)

// Route identifies how a shell line should be dispatched.
type Route string

const (
	RouteEmpty   Route = "empty"
	RouteShell   Route = "shell"
	RouteAgent   Route = "agent"
	RouteControl Route = "control"
)

// Classification describes the selected route and the rule that selected it.
type Classification struct {
	Route  Route
	Reason string
}

var assignmentPattern = regexp.MustCompile(`^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*(\[[^]]+\])?\+?=`)

var globPattern = regexp.MustCompile(`[*?]|\[[^]]+\]`)

var arithmeticPattern = regexp.MustCompile(`^\(\(.+\)\)$`)

var braceExpansionPattern = regexp.MustCompile(`\{[^{}\n]*(,|\.\.)[^{}\n]*\}`)

var parameterCommandPattern = regexp.MustCompile(`^\$([A-Za-z_][A-Za-z0-9_]*|[0-9@*#?$!_-])$`)

var commandTokenPattern = regexp.MustCompile(`^[A-Za-z0-9_][A-Za-z0-9_.+@%-]*$`)

// Classify routes a raw interactive Bash input line to shell, agent, control, or empty.
func Classify(input string) Classification {
	line := strings.TrimSpace(input)
	if line == "" {
		return Classification{Route: RouteEmpty, Reason: "empty input"}
	}
	if isSlashControl(line) {
		return Classification{Route: RouteControl, Reason: "whitelisted slash control"}
	}
	first, rest := firstFieldWithRest(line)
	first = stripShellEscapes(first)

	if isWittyCommand(first) {
		return Classification{Route: RouteShell, Reason: "witty command"}
	}
	if isExplicitPath(first) {
		return Classification{Route: RouteShell, Reason: "explicit path"}
	}
	if isParameterCommand(first) {
		return Classification{Route: RouteShell, Reason: "parameter-expanded command"}
	}
	if hasStrongShellSyntax(line) {
		return Classification{Route: RouteShell, Reason: "shell syntax"}
	}
	if assignmentPattern.MatchString(line) {
		return Classification{Route: RouteShell, Reason: "assignment"}
	}
	if isShellKeyword(first) {
		return Classification{Route: RouteShell, Reason: "shell keyword"}
	}
	if isKnownShellCommand(first) {
		if hasCommandNaturalLanguageSignal(first, rest) {
			return Classification{Route: RouteAgent, Reason: "known command + NL question"}
		}
		return Classification{Route: RouteShell, Reason: "known shell command"}
	}
	if isGlobPattern(first) {
		return Classification{Route: RouteShell, Reason: "glob pattern"}
	}
	if isArithmeticExpression(line) {
		return Classification{Route: RouteShell, Reason: "arithmetic expression"}
	}
	if hasNaturalLanguagePrefix(line) {
		return Classification{Route: RouteAgent, Reason: "natural language"}
	}
	if isCommandToken(first) {
		return Classification{Route: RouteShell, Reason: "command-shaped input"}
	}
	if hasNaturalLanguageSignal(line) {
		return Classification{Route: RouteAgent, Reason: "natural language"}
	}
	return Classification{Route: RouteShell, Reason: "shell fallback: ambiguous input"}
}

func isSlashControl(line string) bool {
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return false
	}
	switch strings.ToLower(fields[0]) {
	case "/exit", "/quit", "/q":
		return len(fields) == 1
	case "/new", "/help":
		return len(fields) == 1
	case "/ask":
		return len(fields) >= 2
	case "/agent", "/model":
		return true
	case "/session":
		if len(fields) < 2 {
			return false
		}
		switch fields[1] {
		case "list":
			return len(fields) == 2
		case "continue":
			return len(fields) == 3
		default:
			return false
		}
	default:
		return false
	}
}

func isWittyCommand(first string) bool {
	return first == "witty"
}

func firstField(line string) string {
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return ""
	}
	return fields[0]
}

func firstFieldWithRest(line string) (string, string) {
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return "", ""
	}
	if len(fields) == 1 {
		return fields[0], ""
	}
	rest := strings.Join(fields[1:], " ")
	return fields[0], rest
}

func stripShellEscapes(first string) string {
	for strings.HasPrefix(first, "\\") {
		first = first[1:]
	}
	if len(first) >= 2 {
		q := first[0]
		if (q == '"' || q == '\'') && first[len(first)-1] == q {
			first = first[1 : len(first)-1]
		}
	}
	return first
}

func isExplicitPath(first string) bool {
	return strings.HasPrefix(first, "/") ||
		strings.HasPrefix(first, "./") ||
		strings.HasPrefix(first, "../") ||
		strings.HasPrefix(first, "~/") ||
		strings.Contains(first, "/")
}

func isParameterCommand(first string) bool {
	return parameterCommandPattern.MatchString(first)
}

func hasStrongShellSyntax(line string) bool {
	if strings.Contains(line, "\n") || strings.HasSuffix(line, "\\") {
		return true
	}
	for _, token := range []string{"|", ">", "<", ";", "&&", "||", "`", "$(", "${"} {
		if strings.Contains(line, token) {
			return true
		}
	}
	return braceExpansionPattern.MatchString(line)
}

func hasNaturalLanguagePrefix(line string) bool {
	lower := strings.ToLower(line)
	for _, p := range nlPhrases {
		if p.Prefix && strings.HasPrefix(lower, p.Pattern) {
			return true
		}
	}
	return false
}

func hasNaturalLanguageSignal(line string) bool {
	for _, r := range line {
		if unicode.Is(unicode.Han, r) {
			return true
		}
	}
	if strings.ContainsAny(line, "?？") {
		return true
	}
	lower := strings.ToLower(line)
	for _, p := range nlPhrases {
		if p.Prefix && strings.HasPrefix(lower, p.Pattern) {
			return true
		}
		if !p.Prefix && strings.Contains(lower, p.Pattern) {
			return true
		}
	}
	return false
}

func hasCommandNaturalLanguageSignal(command, rest string) bool {
	lower := strings.ToLower(strings.TrimSpace(rest))
	for _, p := range commandNLPhrases {
		if p.Command != "" && p.Command != command {
			continue
		}
		if strings.HasPrefix(lower, p.Pattern) {
			return true
		}
	}
	return false
}

func isGlobPattern(first string) bool {
	return globPattern.MatchString(first)
}

func isArithmeticExpression(line string) bool {
	compact := strings.Map(func(r rune) rune {
		if r == ' ' || r == '\t' || r == '\r' || r == '\n' {
			return -1
		}
		return r
	}, strings.TrimSpace(line))
	return arithmeticPattern.MatchString(compact)
}

func isCommandToken(first string) bool {
	return commandTokenPattern.MatchString(first)
}

var keywordSet, commandSet map[string]bool

func init() {
	keywordSet = make(map[string]bool, len(shellKeywords))
	for _, kw := range shellKeywords {
		keywordSet[kw] = true
	}
	commandSet = make(map[string]bool, len(knownCommands))
	for _, c := range knownCommands {
		commandSet[c] = true
	}
}

func isShellKeyword(first string) bool {
	return keywordSet[first]
}

func isKnownShellCommand(first string) bool {
	return commandSet[first]
}
