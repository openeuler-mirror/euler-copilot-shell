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
	first := firstField(line)
	if isWittyCommand(first) {
		return Classification{Route: RouteShell, Reason: "witty command"}
	}
	if isExplicitPath(first) {
		return Classification{Route: RouteShell, Reason: "explicit path"}
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
	if hasNaturalLanguageSignal(line) {
		return Classification{Route: RouteAgent, Reason: "natural language"}
	}
	if isKnownShellCommand(first) {
		return Classification{Route: RouteShell, Reason: "known shell command"}
	}
	return Classification{Route: RouteAgent, Reason: "agent fallback: unknown command without NL signal"}
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

func isExplicitPath(first string) bool {
	if !strings.HasPrefix(first, "/") {
		return strings.HasPrefix(first, "./") ||
			strings.HasPrefix(first, "../") ||
			strings.HasPrefix(first, "~/") ||
			strings.Contains(first, "/")
	}
	if strings.HasPrefix(first, "/") && !strings.Contains(first[1:], "/") {
		return false
	}
	return true
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
	if strings.ContainsAny(line, "?？") {
		return true
	}
	lower := strings.ToLower(line)
	for _, phrase := range []string{
		"how do ", "how ", "what's ", "what ", "why ", "explain ",
		"tell me ", "show me ", "please ", "help me ",
		"can you ", "is there ",
		"怎么看", "如何", "帮我", "请", "分析", "解释",
		"排查", "总结", "检查", "看看", "为什么", "是什么", "能不能",
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
		"python", "python3", "node", "npm", "docker", "podman", "kubectl",
		"jq", "yq", "helm", "terraform", "cargo", "rustc", "brew",
		"apt", "snap", "pip", "pip3", "conda", "mvn", "gradle", "cmake", "ninja",
		"vim", "nano", "tmux", "screen", "code":
		return true
	default:
		return false
	}
}
