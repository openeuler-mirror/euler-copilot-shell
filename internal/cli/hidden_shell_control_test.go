package cli

import (
	"bytes"
	"context"
	"os"
	"strings"
	"testing"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/witty-cli/internal/app"
	"atomgit.com/openeuler/witty-cli/internal/config"
	"atomgit.com/openeuler/witty-cli/internal/core"
	"atomgit.com/openeuler/witty-cli/internal/session"
	"atomgit.com/openeuler/witty-cli/internal/version"
)

func TestShellControlCommand_AskDelegatesToAsk(t *testing.T) {
	fake := &fakeContainer{cfg: config.Config{DefaultAgent: "build", DefaultModel: "opencode/gpt", DefaultVariant: "reasoning-low"}}
	cmd, _, _ := shellControlTestCommand(fake)
	cmd.SetArgs([]string{"shell-control", "--", "/ask", "检查系统内存"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(shell-control /ask) error = %v", err)
	}
	if fake.askReq.Prompt != "检查系统内存" {
		t.Fatalf("prompt = %q, want raw /ask prompt", fake.askReq.Prompt)
	}
	cwd, err := os.Getwd()
	if err != nil {
		t.Fatalf("Getwd() error = %v", err)
	}
	if fake.askReq.CWD != cwd {
		t.Fatalf("cwd = %q, want %q", fake.askReq.CWD, cwd)
	}
	if fake.askReq.Agent != "build" || fake.askReq.Model != "opencode/gpt" || fake.askReq.Variant != "reasoning-low" {
		t.Fatalf("ask request = %+v, want config defaults", fake.askReq)
	}
	if fake.askReq.Mode != core.ModeAsk {
		t.Fatalf("mode = %q, want %q", fake.askReq.Mode, core.ModeAsk)
	}
}

func TestShellControlCommand_HelpDoesNotLoadApp(t *testing.T) {
	var out, errOut bytes.Buffer
	loaded := false
	opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
	opts.loadAppFn = func(context.Context, *cobra.Command) (app.Container, error) {
		loaded = true
		return &fakeContainer{}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"shell-control", "--", "/help"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(shell-control /help) error = %v", err)
	}
	if loaded {
		t.Fatal("/help loaded app, want static shell help")
	}
	if !strings.Contains(out.String(), "/session list") {
		t.Fatalf("help output = %q, want slash command list", out.String())
	}
}

func TestShellControlCommand_SessionControls(t *testing.T) {
	fake := &fakeContainer{
		sessions:         []session.Summary{{ID: "ses_1", Title: "One", Directory: "/work", Updated: 1718000000}},
		continuedSession: session.Context{ID: "ses_1"},
	}
	cmd, out, _ := shellControlTestCommand(fake)
	cmd.SetArgs([]string{"shell-control", "--", "/session", "list"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(shell-control /session list) error = %v", err)
	}
	if !strings.Contains(out.String(), "ses_1\tOne\t/work") {
		t.Fatalf("session list output = %q, want session summary", out.String())
	}

	out.Reset()
	cmd.SetArgs([]string{"shell-control", "--", "/session", "continue", "ses_1"})
	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(shell-control /session continue) error = %v", err)
	}
	if fake.continueSessionID != "ses_1" {
		t.Fatalf("continue id = %q, want ses_1", fake.continueSessionID)
	}
	if !strings.Contains(out.String(), "continued session ses_1") {
		t.Fatalf("continue output = %q, want confirmation", out.String())
	}
}

func shellControlTestCommand(fake *fakeContainer) (*cobra.Command, *bytes.Buffer, *bytes.Buffer) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	}
	cmd := newRootCommandWithOptions(opts)
	return cmd, &out, &errOut
}

func TestShellControlCommand_Agent_Show(t *testing.T) {
	// /agent without args requires interactive terminal; test error case.
	var out, errOut bytes.Buffer
	opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
	opts.loadAppFn = func(context.Context, *cobra.Command) (app.Container, error) {
		return &fakeContainer{}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"shell-control", "--", "/agent"})

	err := cmd.ExecuteContext(context.Background())
	if err == nil {
		t.Fatal("Expected error for /agent without TTY")
	}
	if !strings.Contains(err.Error(), "terminal") {
		t.Fatalf("error = %v, want terminal hint", err)
	}
}

func TestShellControlCommand_Agent_Set(t *testing.T) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
	opts.loadAppFn = func(context.Context, *cobra.Command) (app.Container, error) {
		return &fakeContainer{}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"shell-control", "--", "/agent", "build"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(shell-control /agent build) error = %v", err)
	}
	if !strings.Contains(out.String(), `[agent] set to "build"`) {
		t.Fatalf("agent set output = %q, want agent confirmation", out.String())
	}
}

func TestShellControlCommand_Model_Set(t *testing.T) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
	opts.loadAppFn = func(context.Context, *cobra.Command) (app.Container, error) {
		return &fakeContainer{}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"shell-control", "--", "/model", "opencode/gpt-4"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(shell-control /model) error = %v", err)
	}
	if !strings.Contains(out.String(), `[model] set to "opencode/gpt-4"`) {
		t.Fatalf("model set output = %q, want model confirmation", out.String())
	}
}

func TestShellControlCommand_Exit_NoOp(t *testing.T) {
	for _, cmd := range []string{"/exit", "/quit", "/q"} {
		t.Run(cmd, func(t *testing.T) {
			var out, errOut bytes.Buffer
			opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
			opts.loadAppFn = func(context.Context, *cobra.Command) (app.Container, error) {
				return &fakeContainer{}, nil
			}
			c := newRootCommandWithOptions(opts)
			c.SetArgs([]string{"shell-control", "--", cmd})
			if err := c.ExecuteContext(context.Background()); err != nil {
				t.Fatalf("Execute(shell-control %s) error = %v", cmd, err)
			}
		})
	}
}
