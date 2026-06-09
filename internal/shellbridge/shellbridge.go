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

var assignmentPattern = regexp.MustCompile(`^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*=`)

// Classify routes a raw interactive Bash input line to shell, agent, control, or empty.
func Classify(input string) Classification {
	line := strings.TrimSpace(input)
	if line == "" {
		return Classification{Route: RouteEmpty, Reason: "empty input"}
	}
	if isSlashControl(line) {
		return Classification{Route: RouteControl, Reason: "whitelisted slash control"}
	}
	if first := firstField(line); isExplicitPath(first) {
		return Classification{Route: RouteShell, Reason: "explicit path"}
	}
	if hasStrongShellSyntax(line) {
		return Classification{Route: RouteShell, Reason: "shell syntax"}
	}
	if assignmentPattern.MatchString(line) {
		return Classification{Route: RouteShell, Reason: "assignment"}
	}
	first := firstField(line)
	if isShellKeyword(first) {
		return Classification{Route: RouteShell, Reason: "shell keyword"}
	}
	if hasNaturalLanguageSignal(line) {
		return Classification{Route: RouteAgent, Reason: "natural language"}
	}
	if isKnownShellCommand(first) {
		return Classification{Route: RouteShell, Reason: "known shell command"}
	}
	return Classification{Route: RouteAgent, Reason: "default agent route"}
}

func isSlashControl(line string) bool {
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return false
	}
	switch fields[0] {
	case "/ask", "/agent", "/model", "/new", "/help":
		return true
	case "/session":
		return len(fields) >= 2 && (fields[1] == "list" || fields[1] == "continue")
	default:
		return false
	}
}

func firstField(line string) string {
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return ""
	}
	return fields[0]
}

func isExplicitPath(first string) bool {
	return strings.HasPrefix(first, "/") ||
		strings.HasPrefix(first, "./") ||
		strings.HasPrefix(first, "../") ||
		strings.HasPrefix(first, "~/") ||
		strings.Contains(first, "/")
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
	return false
}

func hasNaturalLanguageSignal(line string) bool {
	for _, r := range line {
		if unicode.Is(unicode.Han, r) {
			return true
		}
	}
	lower := strings.ToLower(line)
	if strings.ContainsAny(line, "?？") {
		return true
	}
	for _, phrase := range []string{
		"how ", "how do", "what ", "why ", "explain ", "tell me", "show me", "check ", "please ", "怎么看", "如何", "解释", "检查",
	} {
		if strings.Contains(lower, phrase) {
			return true
		}
	}
	return false
}

func isShellKeyword(first string) bool {
	switch first {
	case "if", "then", "else", "elif", "fi", "for", "while", "until", "do", "done", "case", "esac", "function", "time", "coproc", "select", "in":
		return true
	default:
		return false
	}
}

func isKnownShellCommand(first string) bool {
	switch first {
	case "command", "builtin", "alias", "unalias", "type", "hash", "help",
		"cd", "pwd", "exit", "logout", "history", "jobs", "fg", "bg", "disown",
		"export", "unset", "readonly", "local", "declare", "printf", "echo", "test",
		"source", ".", "exec", "eval", "trap", "set", "shopt", "umask", "ulimit",
		"dirs", "pushd", "popd", "ls", "cat", "grep", "egrep", "fgrep", "awk",
		"sed", "find", "xargs", "sort", "uniq", "head", "tail", "cut", "tr", "wc",
		"tee", "less", "more", "man", "which", "whereis", "stat", "file", "touch",
		"mkdir", "rmdir", "rm", "cp", "mv", "ln", "chmod", "chown", "tar", "gzip",
		"gunzip", "zip", "unzip", "ssh", "scp", "rsync", "curl", "wget", "git", "go",
		"make", "gcc", "dnf", "yum", "rpm", "systemctl", "journalctl", "service", "ps",
		"top", "free", "df", "du", "ip", "ss", "ping", "sudo", "su", "env", "bash", "sh",
		"python", "python3", "node", "npm", "docker", "podman", "kubectl":
		return true
	default:
		return false
	}
}
