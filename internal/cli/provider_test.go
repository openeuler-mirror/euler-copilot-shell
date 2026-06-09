package cli

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/app"
	"atomgit.com/openeuler/witty-cli/internal/version"
	"github.com/spf13/cobra"
)

func TestProviderListCommand_PrintsProviders(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{
		providers: []app.ProviderStatus{
			{ID: "deepseek", Name: "DeepSeek", DefaultModel: "deepseek-chat", Connected: true},
			{ID: "openai", Name: "OpenAI", DefaultModel: "gpt-4.1", Connected: false},
		},
	}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"provider", "list"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	got := out.String()
	for _, want := range []string{"STATUS", "deepseek", "DeepSeek", "connected", "openai"} {
		if !strings.Contains(got, want) {
			t.Fatalf("provider list output = %q, want %q", got, want)
		}
	}
}

func TestProviderListCommand_ConnectedOnly(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{
		providers: []app.ProviderStatus{
			{ID: "deepseek", Name: "DeepSeek", Connected: true},
			{ID: "openai", Name: "OpenAI", Connected: false},
		},
	}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"provider", "list", "--connected"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	got := out.String()
	if !strings.Contains(got, "deepseek") {
		t.Fatalf("connected-only output = %q, want deepseek", got)
	}
	if strings.Contains(got, "openai") {
		t.Fatalf("connected-only output = %q, should not contain openai", got)
	}
}

func TestProviderConnectCommand_UsesFlagKey(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{connectProvider: app.ProviderStatus{ID: "deepseek"}}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"provider", "connect", "deepseek", "--key", "sk-test"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if fake.connectProviderInput != "deepseek" || fake.connectProviderKey != "sk-test" {
		t.Fatalf("connect input/key = %q/%q, want deepseek/sk-test", fake.connectProviderInput, fake.connectProviderKey)
	}
	if !strings.Contains(out.String(), "connected provider deepseek") {
		t.Fatalf("output = %q, want success message", out.String())
	}
}

func TestProviderConnectCommand_ReadsKeyFromStdin(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{connectProvider: app.ProviderStatus{ID: "deepseek"}}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetIn(strings.NewReader("sk-from-stdin\n"))
	cmd.SetArgs([]string{"provider", "connect", "deepseek"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if fake.connectProviderKey != "sk-from-stdin" {
		t.Fatalf("connect key = %q, want stdin key", fake.connectProviderKey)
	}
}

func TestProviderConnectCommand_AllowsEmptyKeyForEnvFallback(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{connectProvider: app.ProviderStatus{ID: "deepseek"}}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"provider", "connect", "deepseek"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if fake.connectProviderKey != "" {
		t.Fatalf("connect key = %q, want empty key for env fallback", fake.connectProviderKey)
	}
}
