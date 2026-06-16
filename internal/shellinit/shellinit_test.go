package shellinit

import (
	"context"
	"strings"
	"testing"
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
		"__WITTY_SHELL_INIT_LOADED",
		"__witty_should_enable()",
		"__witty_classify()",
		"__witty_debug_hook()",
		"__witty_shell_dispatch()",
		"__witty_debug()",
		"__witty_install_bindings()",
		"__witty_uninstall_bindings()",
		"__witty_command_not_found_handle()",
		"__witty_has_nl_signal()",
		"__witty_command_exists()",
		"shopt -s extdebug",
		"trap '__witty_debug_hook' DEBUG",
		"BASH_COMMAND",
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
	if !strings.HasSuffix(script, "\n") {
		t.Fatal("rendered script does not end with newline")
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
