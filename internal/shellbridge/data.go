package shellbridge

// NLPhrase is a natural language signal pattern.
type NLPhrase struct {
	Pattern string
	Prefix  bool // true → Bash "pattern"*, false → Bash *pattern*
}

// CommandNLPhrase is a high-confidence natural-language prefix following a
// known shell command. Command limits the rule to one command when non-empty.
type CommandNLPhrase struct {
	Command string
	Pattern string
}

// BashClassifierData is the canonical data used to generate the Bash classifier.
type BashClassifierData struct {
	ShellKeywords    []string
	KnownCommands    []string
	NLPhrases        []NLPhrase
	CommandNLPhrases []CommandNLPhrase
	ControlRules     []ControlRule
}

// DefaultBashClassifierData returns the canonical Bash classification rules.
func DefaultBashClassifierData() BashClassifierData {
	return BashClassifierData{
		ShellKeywords:    shellKeywords,
		KnownCommands:    knownCommands,
		NLPhrases:        nlPhrases,
		CommandNLPhrases: commandNLPhrases,
		ControlRules:     controlRules,
	}
}

var shellKeywords = []string{
	"if", "then", "else", "elif", "fi",
	"for", "while", "until", "do", "done",
	"case", "esac", "function", "time", "coproc",
	"select", "in",
}

var knownCommands = []string{
	"command", "builtin", "alias", "unalias", "type", "hash", "help",
	"cd", "pwd", "exit", "logout", "history", "jobs", "fg", "bg", "disown",
	"export", "unset", "readonly", "local", "declare", "printf", "echo", "test",
	"source", ".", "exec", "eval", "trap", "set", "shopt", "umask", "ulimit",
	"dirs", "pushd", "popd",
	"ls", "cat", "grep", "egrep", "fgrep", "awk",
	"sed", "find", "xargs", "sort", "uniq", "head", "tail", "cut", "tr", "wc",
	"tee", "less", "more", "man", "which", "where", "whereis", "stat", "file", "touch",
	"mkdir", "rmdir", "rm", "cp", "mv", "ln", "chmod", "chown", "tar", "gzip",
	"gunzip", "zip", "unzip", "ssh", "scp", "rsync", "curl", "wget", "git", "go",
	"make", "gcc", "dnf", "yum", "rpm", "systemctl", "journalctl", "service", "ps",
	"top", "free", "df", "du", "ip", "ss", "ping", "sudo", "su", "env", "bash", "sh",
	"python", "python3", "node", "npm", "docker", "podman", "kubectl",
	"jq", "yq", "helm", "terraform", "cargo", "rustc", "brew",
	"apt", "snap", "pip", "pip3", "conda", "mvn", "gradle", "cmake", "ninja",
	"vim", "nano", "tmux", "screen", "code",
}

var nlPhrases = []NLPhrase{
	{Pattern: "how do ", Prefix: true},
	{Pattern: "how ", Prefix: true},
	{Pattern: "what's ", Prefix: true},
	{Pattern: "what ", Prefix: true},
	{Pattern: "why ", Prefix: true},
	{Pattern: "explain ", Prefix: true},
	{Pattern: "tell me ", Prefix: true},
	{Pattern: "show me ", Prefix: true},
	{Pattern: "please ", Prefix: true},
	{Pattern: "help me ", Prefix: true},
	{Pattern: "can you ", Prefix: true},
	{Pattern: "is there ", Prefix: true},
	{Pattern: "怎么", Prefix: true},
	{Pattern: "如何", Prefix: true},
	{Pattern: "帮我", Prefix: true},
	{Pattern: "请", Prefix: true},
	{Pattern: "分析", Prefix: true},
	{Pattern: "解释", Prefix: true},
	{Pattern: "排查", Prefix: true},
	{Pattern: "总结", Prefix: true},
	{Pattern: "检查", Prefix: true},
	{Pattern: "看看", Prefix: true},
	{Pattern: "为什么", Prefix: true},
	{Pattern: "是什么", Prefix: true},
	{Pattern: "能不能", Prefix: true},
}

var commandNLPhrases = []CommandNLPhrase{
	{Pattern: "怎么"},
	{Pattern: "如何"},
	{Pattern: "为什么"},
	{Pattern: "为何"},
	{Pattern: "能不能"},
	{Pattern: "是否"},
	{Pattern: "怎样"},
	{Pattern: "how do i "},
	{Pattern: "how can i "},
	{Pattern: "how should i "},
	{Pattern: "what does "},
	{Pattern: "why does "},
	{Pattern: "why is "},
	{Pattern: "can you "},
	{Command: "help", Pattern: "me "},
}
