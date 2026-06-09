package cli

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/version"
)

func TestExecute_Help(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"--help"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err != nil {
		t.Fatalf("Execute(--help) error = %v", err)
	}
	if !strings.Contains(out.String(), "openEuler terminal AI assistant") {
		t.Fatalf("help output = %q, want root short description", out.String())
	}
	if !strings.Contains(out.String(), "ask") || !strings.Contains(out.String(), "init") {
		t.Fatalf("help output = %q, want subcommands", out.String())
	}
}

func TestExecute_Version(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"version"}, &out, &errOut, version.New("1.2.3", "abc", "today"))
	if err != nil {
		t.Fatalf("Execute(version) error = %v", err)
	}
	for _, want := range []string{"version: 1.2.3", "commit: abc", "date: today"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("version output = %q, want %q", out.String(), want)
		}
	}
}

func TestExecute_InitBash(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"init", "bash"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err != nil {
		t.Fatalf("Execute(init bash) error = %v", err)
	}
	if !strings.Contains(out.String(), "Witty Bash integration placeholder") {
		t.Fatalf("init bash output = %q, want placeholder", out.String())
	}
}

func TestExecute_AskHelp(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"ask", "--help"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err != nil {
		t.Fatalf("Execute(ask --help) error = %v", err)
	}
	if !strings.Contains(out.String(), "Ask opencode") {
		t.Fatalf("ask help output = %q, want ask description", out.String())
	}
}

func TestExecute_ArgumentError(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"session", "continue"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err == nil {
		t.Fatal("Execute(session continue) error = nil, want argument error")
	}
}
