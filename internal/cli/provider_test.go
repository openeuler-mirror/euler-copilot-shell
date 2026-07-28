package cli

import (
	"bytes"
	"context"
	"io"
	"strings"
	"testing"

	"atomgit.com/openeuler/euler-copilot-shell/internal/app"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
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
		passwordReader: func(io.Reader, io.Writer, string) (string, error) {
			return "", nil
		},
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetIn(strings.NewReader(""))
	cmd.SetArgs([]string{"provider", "connect", "deepseek"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute() error = %v", err)
	}
	if fake.connectProviderKey != "" {
		t.Fatalf("connect key = %q, want empty key for env fallback", fake.connectProviderKey)
	}
}

func TestResolveProviderAPIKeyInput_FlagTakesPrecedence(t *testing.T) {
	key, err := resolveProviderAPIKeyInput("sk-flag", strings.NewReader("sk-stdin"), io.Discard, nil, isTTYReader)
	if err != nil {
		t.Fatalf("error = %v", err)
	}
	if key != "sk-flag" {
		t.Fatalf("key = %q, want sk-flag", key)
	}
}

func TestResolveProviderAPIKeyInput_PromptsOnTTY(t *testing.T) {
	var out bytes.Buffer
	called := false
	mockReader := func(in io.Reader, w io.Writer, label string) (string, error) {
		called = true
		if label == "" {
			t.Fatal("label should not be empty")
		}
		if w != &out {
			t.Fatal("writer mismatch")
		}
		return "sk-prompted", nil
	}
	alwaysTTY := func(io.Reader) bool { return true }

	key, err := resolveProviderAPIKeyInput("", strings.NewReader(""), &out, mockReader, alwaysTTY)
	if err != nil {
		t.Fatalf("error = %v", err)
	}
	if !called {
		t.Fatal("password reader was not called")
	}
	if key != "sk-prompted" {
		t.Fatalf("key = %q, want sk-prompted", key)
	}
}

func TestResolveProviderAPIKeyInput_NilPasswordReaderReturnsEmpty(t *testing.T) {
	alwaysTTY := func(io.Reader) bool { return true }
	key, err := resolveProviderAPIKeyInput("", strings.NewReader(""), io.Discard, nil, alwaysTTY)
	if err != nil {
		t.Fatalf("error = %v", err)
	}
	if key != "" {
		t.Fatalf("key = %q, want empty for env fallback", key)
	}
}

func TestResolveProviderAPIKeyInput_ReadsFromNonTTYStdin(t *testing.T) {
	neverTTY := func(io.Reader) bool { return false }
	key, err := resolveProviderAPIKeyInput("", strings.NewReader("sk-piped\n"), io.Discard, nil, neverTTY)
	if err != nil {
		t.Fatalf("error = %v", err)
	}
	if key != "sk-piped" {
		t.Fatalf("key = %q, want sk-piped", key)
	}
}
