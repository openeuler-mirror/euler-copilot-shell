package shellbridge

import "testing"

func TestClassify_CheckpointCases(t *testing.T) {
	tests := []struct {
		name string
		line string
		want Route
	}{
		{name: "Chinese natural prompt", line: "检查系统内存", want: RouteAgent},
		{name: "systemctl command", line: "systemctl status nginx", want: RouteShell},
		{name: "systemctl natural language", line: "systemctl 怎么看 nginx 日志", want: RouteAgent},
		{name: "pipeline command", line: "cat /etc/os-release | grep NAME", want: RouteShell},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := Classify(tt.line)
			if got.Route != tt.want {
				t.Fatalf("Classify(%q) route = %q (%s), want %q", tt.line, got.Route, got.Reason, tt.want)
			}
		})
	}
}

func TestClassify_RoutingRules(t *testing.T) {
	tests := []struct {
		line string
		want Route
	}{
		{line: "   ", want: RouteEmpty},
		{line: "/help", want: RouteControl},
		{line: "/exit", want: RouteControl},
		{line: "/quit", want: RouteControl},
		{line: "/q", want: RouteControl},
		{line: "/ask explain rpm macros", want: RouteControl},
		{line: "/session list", want: RouteControl},
		{line: "/session continue ses_1", want: RouteControl},
		{line: "/usr/bin/ls", want: RouteShell},
		{line: "./script.sh", want: RouteShell},
		{line: "FOO=bar go test ./...", want: RouteShell},
		{line: "if true; then echo ok; fi", want: RouteShell},
		{line: "explain how to check memory", want: RouteAgent},
		{line: "how do I restart nginx", want: RouteAgent},
		{line: "witty ask something", want: RouteShell},
		{line: "/exit foo", want: RouteAgent},
		{line: "/new extra", want: RouteAgent},
		{line: "/help me", want: RouteAgent},
		{line: "/ask", want: RouteAgent},
		{line: "some_unknown_nonsense", want: RouteAgent},
		{line: "please show me the logs", want: RouteAgent},
		{line: "what is the kernel version", want: RouteAgent},
		{line: "can you check the disk space", want: RouteAgent},
		{line: "为什么服务启动失败", want: RouteAgent},
		{line: "看看系统日志", want: RouteAgent},
	}

	for _, tt := range tests {
		t.Run(tt.line, func(t *testing.T) {
			got := Classify(tt.line)
			if got.Route != tt.want {
				t.Fatalf("Classify(%q) route = %q (%s), want %q", tt.line, got.Route, got.Reason, tt.want)
			}
		})
	}
}

func TestParseControl(t *testing.T) {
	tests := []struct {
		name string
		raw  string
		want ControlAction
	}{
		{name: "ask", raw: "/ask 检查系统内存", want: ControlAction{Kind: ControlAsk, Raw: "/ask 检查系统内存", Prompt: "检查系统内存"}},
		{name: "agent", raw: "/agent build", want: ControlAction{Kind: ControlAgent, Raw: "/agent build", Value: "build"}},
		{name: "model", raw: "/model opencode/gpt", want: ControlAction{Kind: ControlModel, Raw: "/model opencode/gpt", Value: "opencode/gpt"}},
		{name: "new", raw: "/new", want: ControlAction{Kind: ControlNew, Raw: "/new"}},
		{name: "help", raw: "/help", want: ControlAction{Kind: ControlHelp, Raw: "/help"}},
		{name: "session list", raw: "/session list", want: ControlAction{Kind: ControlSessionList, Raw: "/session list"}},
		{name: "session continue", raw: "/session continue ses_1", want: ControlAction{Kind: ControlSessionContinue, Raw: "/session continue ses_1", SessionID: "ses_1"}},
		{name: "exit", raw: "/exit", want: ControlAction{Kind: ControlExit, Raw: "/exit"}},
		{name: "quit", raw: "/quit", want: ControlAction{Kind: ControlExit, Raw: "/quit"}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ParseControl(tt.raw)
			if err != nil {
				t.Fatalf("ParseControl(%q) error = %v", tt.raw, err)
			}
			if got != tt.want {
				t.Fatalf("ParseControl(%q) = %+v, want %+v", tt.raw, got, tt.want)
			}
		})
	}
}

func TestParseControl_RejectsUnsupported(t *testing.T) {
	for _, raw := range []string{"", "/usr/bin/ls", "/session delete ses_1", "/ask"} {
		t.Run(raw, func(t *testing.T) {
			if _, err := ParseControl(raw); err == nil {
				t.Fatalf("ParseControl(%q) error = nil, want error", raw)
			}
		})
	}
}

func TestWrapperLine(t *testing.T) {
	line, ok := WrapperLine(RouteAgent, "检查 user's memory")
	if !ok {
		t.Fatal("WrapperLine(RouteAgent) ok = false, want true")
	}
	want := `__witty_shell_dispatch agent -- '检查 user'"'"'s memory'`
	if line != want {
		t.Fatalf("WrapperLine() = %q, want %q", line, want)
	}
	if _, ok := WrapperLine(RouteShell, "ls"); ok {
		t.Fatal("WrapperLine(RouteShell) ok = true, want false")
	}
}

func TestIsExitSlash(t *testing.T) {
	tests := []struct {
		input string
		want  bool
	}{
		{"/exit", true},
		{"/EXIT", true},
		{"/quit", true},
		{"/q", true},
		{" /exit ", true},
		{"/Quit", true},
		{"/help", false},
		{"exit", false},
		{"", false},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			if got := IsExitSlash(tt.input); got != tt.want {
				t.Fatalf("IsExitSlash(%q) = %v, want %v", tt.input, got, tt.want)
			}
		})
	}
}

func TestSuggestSlash(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"/hel", "did you mean /help?"},
		{"/hepl", "did you mean /help?"},
		{"/agnt", "did you mean /agent?"},
		{"/exit", ""},       // exact match not suggested
		{"/usr/bin/ls", ""}, // too different
		{"", ""},
		{"no-slash", ""},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := SuggestSlash(tt.input)
			// For exact matches or too-different inputs, SuggestSlash returns empty.
			if tt.want == "" && got != "" {
				t.Fatalf("SuggestSlash(%q) = %q, want empty", tt.input, got)
			}
			if tt.want != "" && got != tt.want {
				t.Fatalf("SuggestSlash(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}
