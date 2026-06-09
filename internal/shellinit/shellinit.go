package shellinit

import (
	"bytes"
	"context"
	"fmt"
	"strings"
	"text/template"
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

func (r *renderer) RenderBash(ctx context.Context, opts BashOptions) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}

	data := normalizeBashOptions(opts)
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

func normalizeBashOptions(opts BashOptions) BashOptions {
	if strings.TrimSpace(opts.BinaryPath) == "" {
		opts.BinaryPath = "witty"
	}
	if strings.TrimSpace(opts.Version) == "" {
		opts.Version = "dev"
	}
	return opts
}
