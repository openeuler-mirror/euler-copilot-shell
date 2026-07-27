package shellinit

import (
	"bytes"
	"context"
	"fmt"
	"strings"
	"text/template"

	"atomgit.com/openeuler/euler-copilot-shell/internal/shellbridge"
)

const bashTemplatePath = "templates/witty.bash.tmpl"

// Renderer renders shell integration snippets.
type Renderer interface {
	RenderBash(ctx context.Context, opts BashOptions) (string, error)
}

// BashOptions contains values injected into the Bash integration template.
type BashOptions struct {
	BinaryPath   string
	Version      string
	ShellEnabled bool
	ShellDebug   bool
}

type renderer struct{}

// NewRenderer creates a template-backed shell init renderer.
func NewRenderer() Renderer {
	return &renderer{}
}

type bashTemplateData struct {
	BinaryPath       string
	Version          string
	ShellEnabled     bool
	ShellDebug       bool
	ShellKeywordCase string
	ShellCommandCase string
	NLPhraseCase     string
	CommandNLCase    string
}

func (r *renderer) RenderBash(ctx context.Context, opts BashOptions) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}

	rules := shellbridge.DefaultClassificationData()
	data := bashTemplateData{
		BinaryPath:       opts.BinaryPath,
		Version:          opts.Version,
		ShellEnabled:     opts.ShellEnabled,
		ShellDebug:       opts.ShellDebug,
		ShellKeywordCase: shellbridge.BashKeywordCase(rules.ShellKeywords),
		ShellCommandCase: shellbridge.BashCommandCase(rules.KnownCommands),
		NLPhraseCase:     shellbridge.BashNLPhraseCase(rules.NLPhrases),
		CommandNLCase:    shellbridge.BashCommandNLPhraseCase(rules.CommandNLPhrases),
	}
	if strings.TrimSpace(data.BinaryPath) == "" {
		data.BinaryPath = "witty"
	}
	if strings.TrimSpace(data.Version) == "" {
		data.Version = "dev"
	}

	tmpl, err := template.New("witty-bash-init").
		Delims("[[", "]]").
		ParseFS(TemplateFS, bashTemplatePath)
	if err != nil {
		return "", fmt.Errorf("parse bash init template: %w", err)
	}

	var buf bytes.Buffer
	if err := tmpl.ExecuteTemplate(&buf, "witty.bash.tmpl", data); err != nil {
		return "", fmt.Errorf("render bash init template: %w", err)
	}
	if err := ctx.Err(); err != nil {
		return "", err
	}

	out := buf.String()
	if !strings.HasSuffix(out, "\n") {
		out += "\n"
	}
	return out, nil
}
