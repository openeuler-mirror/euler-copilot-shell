package config

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// These assets are shipped in the witty-builtin-agent RPM. Keeping the safety
// rules under test prevents a later config/prompt edit from silently removing
// the consent gates or the credential-reference policy.
func TestBuiltinAgentConfigSafetyRules(t *testing.T) {
	root := filepath.Join("..", "..", "packaging", "builtin-agents")
	configPath := filepath.Join(root, "config.d", "witty-builtin-agent.json")
	data, err := os.ReadFile(configPath)
	if err != nil {
		t.Fatalf("read %s: %v", configPath, err)
	}

	var document struct {
		Agent map[string]struct {
			Permission struct {
				Bash map[string]string `json:"bash"`
			} `json:"permission"`
		} `json:"agent"`
		MCP map[string]struct {
			Environment map[string]string `json:"environment"`
		} `json:"mcp"`
	}
	if err := json.Unmarshal(data, &document); err != nil {
		t.Fatalf("decode %s: %v", configPath, err)
	}

	agent, ok := document.Agent["witty-builtin-agent"]
	if !ok {
		t.Fatal("witty-builtin-agent entry is missing")
	}
	if got := agent.Permission.Bash["*"]; got != "allow" {
		t.Fatalf("bash default = %q, want allow", got)
	}
	for _, pattern := range []string{
		"*dnf install *",
		"*dnf download *",
		"*npm install*",
		"*npm i *",
		"*npx *",
		"*yarn add *",
		"*pnpm add *",
		"*rpm2cpio *",
		"*pip install *",
		"*kroki.io*",
		"*plantuml.com*",
		"*user-agent*",
		"*USER_AGENT*",
		"*curl *-A *",
	} {
		if got := agent.Permission.Bash[pattern]; got != "ask" {
			t.Fatalf("bash permission %q = %q, want ask", pattern, got)
		}
	}

	mcp, ok := document.MCP["openeuler_portal"]
	if !ok {
		t.Fatal("openeuler_portal MCP entry is missing")
	}
	for name, value := range mcp.Environment {
		if !strings.HasPrefix(value, "{env:") || !strings.HasSuffix(value, "}") {
			t.Fatalf("%s = %q, want an {env:...} reference", name, value)
		}
	}

	promptPath := filepath.Join(root, "agents", "witty-builtin-agent", "witty-builtin-agent.md")
	prompt, err := os.ReadFile(promptPath)
	if err != nil {
		t.Fatalf("read %s: %v", promptPath, err)
	}
	for _, phrase := range []string{
		"Installing or downloading anything needs explicit consent",
		"Never upload data to a public third-party service",
		"redact other users' IP addresses",
		"Do not leave requested verification unfinished",
	} {
		if !strings.Contains(string(prompt), phrase) {
			t.Fatalf("prompt is missing safety rule %q", phrase)
		}
	}
}

func TestPackagingRecordsConfigModeAndDeterministicPermission(t *testing.T) {
	specPath := filepath.Join("..", "..", "packaging", "euler-copilot-shell.spec")
	spec, err := os.ReadFile(specPath)
	if err != nil {
		t.Fatalf("read %s: %v", specPath, err)
	}
	wantSpec := "%ghost %attr(0644, root, root) %config(noreplace) %{_sysconfdir}/opencode/opencode.json"
	if !strings.Contains(string(spec), wantSpec) {
		t.Fatalf("spec is missing %q", wantSpec)
	}

	loaderPath := filepath.Join("..", "..", "packaging", "agent-loader", "bin", "rebuild-managed-config.mjs")
	loader, err := os.ReadFile(loaderPath)
	if err != nil {
		t.Fatalf("read %s: %v", loaderPath, err)
	}
	if !strings.Contains(string(loader), "await fs.chmod(tempPath, 0o644);") {
		t.Fatal("managed-config generator does not force mode 0644")
	}
}
