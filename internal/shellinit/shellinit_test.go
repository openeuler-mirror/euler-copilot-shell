package shellinit

import (
	"context"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"atomgit.com/openeuler/euler-copilot-shell/internal/shellbridge"
)

func TestBashTemplate(t *testing.T) {
	renderer := NewRenderer()
	script, err := renderer.RenderBash(context.Background(), BashOptions{
		BinaryPath:   "/usr/bin/witty",
		Version:      "1.2.3",
		ShellEnabled: true,
		ShellDebug:   false,
	})
	if err != nil {
		t.Fatalf("RenderBash() error = %v", err)
	}

	for _, forbidden := range []string{"{{", "}}", "[[ ."} {
		if strings.Contains(script, forbidden) {
			t.Fatalf("rendered script contains template delimiter %q", forbidden)
		}
	}
	for _, want := range []string{
		"Witty Bash integration 1.2.3",
		`__WITTY_BINARY="/usr/bin/witty"`,
		"__WITTY_SHELL_INIT_LOADED=1",
		"__witty_should_enable()",
		"__witty_classify()",
		"__witty_split_first_word()",
		"__witty_is_explicit_path()",
		"__witty_has_strong_shell_syntax()",
		"__witty_last_history_line()",
		"__witty_debug_hook()",
		"__witty_shell_dispatch()",
		"__witty_debug()",
		"__witty_install_bindings()",
		"__witty_uninstall_bindings()",
		"__witty_command_not_found_handle()",
		"__witty_is_control()",
		"__witty_has_nl_signal()",
		"__witty_has_nl_prefix()",
		"__witty_has_command_nl_signal()",
		"__witty_looks_like_shell_command()",
		"__witty_command_exists()",
		"shopt -s extdebug",
		"trap '__witty_debug_hook' DEBUG",
		"BASH_COMMAND",
		"builtin history 1",
		`command "$__WITTY_BINARY" ask -- "$raw"`,
		`command "$__WITTY_BINARY" shell-control -- "$raw"`,
		"HISTIGNORE",
		"WITTY_SHELL_ENABLE",
		"BASH_VERSINFO",
	} {
		if !strings.Contains(script, want) {
			t.Fatalf("rendered script missing %q", want)
		}
	}
	if !strings.Contains(script, "export __WITTY_SHELL_INIT_LOADED") {
		t.Fatal("rendered script does not export the initialization guard")
	}
	if !strings.HasSuffix(script, "\n") {
		t.Fatal("rendered script does not end with newline")
	}
}

func TestBashClassifierRoutes(t *testing.T) {
	version, err := exec.Command("bash", "-c", `printf '%s' "${BASH_VERSINFO[0]}"`).Output()
	if err != nil {
		t.Fatalf("read Bash version: %v", err)
	}
	major, err := strconv.Atoi(string(version))
	if err != nil {
		t.Fatalf("parse Bash version %q: %v", version, err)
	}
	if major < 4 {
		t.Skipf("Bash classifier requires Bash 4+, found Bash %d", major)
	}

	script, err := NewRenderer().RenderBash(context.Background(), BashOptions{
		BinaryPath:   "/usr/bin/witty",
		ShellEnabled: true,
	})
	if err != nil {
		t.Fatalf("RenderBash() error = %v", err)
	}
	initPath := filepath.Join(t.TempDir(), "witty.bash")
	if err := os.WriteFile(initPath, []byte(script), 0o600); err != nil {
		t.Fatalf("write Bash init: %v", err)
	}

	tests := []struct {
		name string
		line string
		want string
	}{
		{name: "empty", line: "   ", want: "empty"},
		{name: "Chinese prompt", line: "检查系统内存", want: "agent"},
		{name: "Chinese prose containing path", line: "把生成的脚本保存在/root/目录下", want: "agent"},
		{name: "Chinese prose ending in path", line: "把日志写到/var/log下", want: "agent"},
		{name: "path-like Chinese prose", line: "/root目录下有哪些文件", want: "agent"},
		{name: "glued path question", line: "/root/目录下有什么", want: "agent"},
		{name: "path question", line: "/root/目录下有哪些文件", want: "agent"},
		{name: "path question with space", line: "/root/ 下有哪些文件", want: "agent"},
		{name: "path question with ASCII mark", line: "/root/目录下有哪些文件?", want: "agent"},
		{name: "quoted Unicode path", line: `"/home/user/中文 脚本.sh" --flag`, want: "shell"},
		{name: "single quoted Unicode path", line: `'/home/user/中文 工具' --flag`, want: "shell"},
		{name: "Unicode script path", line: "/home/中文目录/script.sh", want: "shell"},
		{name: "Unicode directory path", line: "/home/中文目录/.config/", want: "shell"},
		{name: "Unicode relative path", line: "./脚本.sh", want: "shell"},
		{name: "Unicode home path", line: "~/中文配置", want: "shell"},
		{name: "ASCII relative path", line: "scripts/build.sh", want: "shell"},
		{name: "absolute path", line: "/usr/bin/ls", want: "shell"},
		{name: "systemctl command", line: "systemctl status nginx", want: "shell"},
		{name: "systemctl question", line: "systemctl 怎么看 nginx 日志", want: "agent"},
		{name: "known command question", line: "git 怎么只看最近一次提交", want: "agent"},
		{name: "help command question", line: "help me understand systemd", want: "agent"},
		{name: "English explain prompt", line: "explain how to check memory", want: "agent"},
		{name: "English how prompt", line: "how do I restart nginx", want: "agent"},
		{name: "English please prompt", line: "please show me the logs", want: "agent"},
		{name: "English what prompt", line: "what is the kernel version", want: "agent"},
		{name: "English can you prompt", line: "can you check the disk space", want: "agent"},
		{name: "Chinese why prompt", line: "为什么服务启动失败", want: "agent"},
		{name: "Chinese look prompt", line: "看看系统日志", want: "agent"},
		{name: "witty command", line: "witty ask something", want: "shell"},
		{name: "where witty command", line: "where witty", want: "shell"},
		{name: "where ls command", line: "where ls", want: "shell"},
		{name: "known command with Unicode argument", line: "rm 检查报告.txt", want: "shell"},
		{name: "grep with Unicode argument", line: "grep 错误 app.log", want: "shell"},
		{name: "grep with how argument", line: "grep how input.txt", want: "shell"},
		{name: "ls with Unicode filename", line: "ls 中文报告.txt", want: "shell"},
		{name: "echo quoted question mark", line: `echo "?"`, want: "shell"},
		{name: "echo question mark", line: "echo ?", want: "shell"},
		{name: "curl query string", line: "curl 'https://host/api?page=1'", want: "shell"},
		{name: "docker delayed question", line: "docker 镜像怎么删", want: "shell"},
		{name: "assignment", line: "FOO=bar go test ./...", want: "shell"},
		{name: "shell keyword", line: "if true; then echo ok; fi", want: "shell"},
		{name: "pipeline", line: "检查系统内存 | tee answer.txt", want: "shell"},
		{name: "compound command", line: "检查系统内存; echo done", want: "shell"},
		{name: "arithmetic expression", line: "((counter++))", want: "shell"},
		{name: "brace expansion", line: "foobar{,baz}", want: "shell"},
		{name: "parameter command", line: "$cmd arg", want: "shell"},
		{name: "glob command", line: "*.sh", want: "shell"},
		{name: "quoted known command", line: `"echo" hello`, want: "shell"},
		{name: "command-shaped Unicode arguments", line: "deploy 生产环境", want: "shell"},
		{name: "unknown command fallback", line: "some_unknown_nonsense", want: "shell"},
	}

	const classifyScript = `
unset __WITTY_SHELL_INIT_LOADED
source "$1"
declare -A __WITTY_CMD_CACHE=()
__witty_classify "$2"
`
	classify := func(t *testing.T, name, line, want string) {
		t.Helper()
		t.Run(name, func(t *testing.T) {
			cmd := exec.Command("bash", "--noprofile", "--norc", "-c", classifyScript, "bash", initPath, line)
			output, err := cmd.CombinedOutput()
			if err != nil {
				t.Fatalf("classify %q: %v: %s", line, err, output)
			}
			if got := strings.TrimSpace(string(output)); got != want {
				t.Fatalf("classify %q = %q, want %q", line, got, want)
			}
		})
	}
	for _, tt := range tests {
		classify(t, tt.name, tt.line, tt.want)
	}

	seen := make(map[string]bool)
	var controlCandidates []string
	addControlCandidate := func(words []string) {
		line := strings.Join(words, " ")
		if !seen[line] {
			seen[line] = true
			controlCandidates = append(controlCandidates, line)
		}
	}
	for _, rule := range shellbridge.DefaultBashClassifierData().ControlRules {
		words := []string{rule.Command}
		if rule.Subcommand != "" {
			words = append(words, rule.Subcommand)
		}
		for len(words) < rule.MinWords {
			words = append(words, "value")
		}
		addControlCandidate(words)
		if len(words) > 1 {
			addControlCandidate(words[:len(words)-1])
		}
		if rule.MaxWords > 0 {
			addControlCandidate(append(append([]string{}, words...), "extra"))
		}
	}
	for _, line := range controlCandidates {
		want := "control"
		if _, err := shellbridge.ParseControl(line); err != nil {
			want = "shell"
		}
		classify(t, "control parity/"+line, line, want)
	}
}

func TestBashTemplate_Defaults(t *testing.T) {
	renderer := NewRenderer()
	script, err := renderer.RenderBash(context.Background(), BashOptions{})
	if err != nil {
		t.Fatalf("RenderBash() error = %v", err)
	}
	for _, want := range []string{`__WITTY_BINARY="witty"`, "Witty Bash integration dev"} {
		if !strings.Contains(script, want) {
			t.Fatalf("rendered script missing default %q", want)
		}
	}
}

func TestBashTemplate_ContextCanceled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := NewRenderer().RenderBash(ctx, BashOptions{})
	if err == nil {
		t.Fatal("RenderBash() error = nil, want context cancellation")
	}
}
