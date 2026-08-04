package shellbridge

import (
	"strings"
	"testing"
)

func TestBashCommandNLPhraseCase(t *testing.T) {
	got := BashCommandNLPhraseCase([]CommandNLPhrase{
		{Pattern: "怎么"},
		{Command: "help", Pattern: "me "},
	})
	want := `*:"怎么"* | "help:me "*`
	if got != want {
		t.Fatalf("BashCommandNLPhraseCase() = %q, want %q", got, want)
	}
}

func TestBashControlCase(t *testing.T) {
	got := BashControlCase([]ControlRule{
		{Command: "/exit", MinWords: 1, MaxWords: 1},
		{Command: "/ask", MinWords: 2},
		{Command: "/session", Subcommand: "list", MinWords: 2, MaxWords: 2},
	})
	want := `"/exit::1" | "/ask:"?*":"* | "/session:list:2"`
	if got != want {
		t.Fatalf("BashControlCase() = %q, want %q", got, want)
	}
}

func TestParseControl(t *testing.T) {
	tests := []struct {
		name string
		raw  string
		want ControlAction
	}{
		{name: "ask", raw: "/ask 检查系统内存", want: ControlAction{Kind: ControlAsk, Raw: "/ask 检查系统内存", Prompt: "检查系统内存"}},
		{name: "case insensitive ask", raw: "/ASK 检查系统内存", want: ControlAction{Kind: ControlAsk, Raw: "/ASK 检查系统内存", Prompt: "检查系统内存"}},
		{name: "agent", raw: "/agent build", want: ControlAction{Kind: ControlAgent, Raw: "/agent build", Value: "build"}},
		{name: "model", raw: "/model opencode/gpt", want: ControlAction{Kind: ControlModel, Raw: "/model opencode/gpt", Value: "opencode/gpt"}},
		{name: "new", raw: "/new", want: ControlAction{Kind: ControlNew, Raw: "/new"}},
		{name: "help", raw: "/help", want: ControlAction{Kind: ControlHelp, Raw: "/help"}},
		{name: "session help", raw: "/session", want: ControlAction{Kind: ControlSessionHelp, Raw: "/session"}},
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

func TestSessionHelpText(t *testing.T) {
	for _, want := range []string{"/session list", "/session continue <id>"} {
		if !strings.Contains(SessionHelpText(), want) {
			t.Fatalf("SessionHelpText() missing %q", want)
		}
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
