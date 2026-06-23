package cli

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
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
	for _, want := range []string{"ask", "init", "provider"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("help output = %q, want subcommand %q", out.String(), want)
		}
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
	for _, want := range []string{"Witty Bash integration dev", "__witty_classify()", "__witty_shell_dispatch()"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("init bash output = %q, want %q", out.String(), want)
		}
	}
}

func TestExecute_AskHelp(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"ask", "--help"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err != nil {
		t.Fatalf("Execute(ask --help) error = %v", err)
	}
	for _, want := range []string{"stream the response", "--new", "--session", "provider/model"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("ask help output = %q, want %q", out.String(), want)
		}
	}
}

func TestExecute_ProviderHelp(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"provider", "connect", "--help"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err != nil {
		t.Fatalf("Execute(provider connect --help) error = %v", err)
	}
	for _, want := range []string{"Connect a provider using API key", "--key", "provider env vars"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("provider help output = %q, want %q", out.String(), want)
		}
	}
}

func TestExecute_ArgumentError(t *testing.T) {
	var out, errOut bytes.Buffer
	err := Execute(context.Background(), []string{"session", "continue"}, &out, &errOut, version.New("dev", "none", "unknown"))
	if err == nil {
		t.Fatal("Execute(session continue) error = nil, want argument error")
	}
}
