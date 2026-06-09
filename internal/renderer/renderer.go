package renderer

import (
	"context"
	"fmt"
	"io"
	"os"
	"strings"

	"charm.land/lipgloss/v2"

	wittyterm "atomgit.com/openeuler/witty-cli/internal/terminal"
)

// TextRenderer renders normalized text deltas into terminal output.
type TextRenderer interface {
	WriteDelta(ctx context.Context, delta string) error
	Flush(ctx context.Context) error
}

// Options controls MarkdownRenderer construction.
type Options struct {
	Writer     io.Writer
	IsTTY      bool
	Width      int
	Theme      string
	NoColor    bool
	InputFile  *os.File
	OutputFile *os.File
}

// MarkdownRenderer implements Phase 1 block-boundary Markdown rendering.
type MarkdownRenderer struct {
	out        io.Writer
	isTTY      bool
	downsample bool
	buffer     *BlockBuffer
	markdown   markdownEngine
	firstBlock bool
}

// NewMarkdownRenderer creates a Phase 1 text renderer.
func NewMarkdownRenderer(opts Options) (TextRenderer, error) {
	out := opts.Writer
	if out == nil {
		out = os.Stdout
	}

	width := opts.Width
	if width <= 0 {
		width = wittyterm.DefaultWidth
	}

	r := &MarkdownRenderer{
		out:        out,
		isTTY:      opts.IsTTY,
		downsample: opts.OutputFile != nil,
		buffer:     NewBlockBuffer(),
		firstBlock: true,
	}
	if !opts.IsTTY {
		return r, nil
	}

	markdown, err := newMarkdownEngine(opts.Theme, opts.NoColor, width, opts.InputFile, opts.OutputFile)
	if err != nil {
		return nil, fmt.Errorf("create markdown renderer: %w", err)
	}
	r.markdown = markdown
	return r, nil
}

func (r *MarkdownRenderer) WriteDelta(ctx context.Context, delta string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if delta == "" {
		return nil
	}
	if !r.isTTY {
		if _, err := io.WriteString(r.out, delta); err != nil {
			return fmt.Errorf("write raw delta: %w", err)
		}
		return nil
	}

	r.buffer.Append(delta)
	for {
		block, ok := r.buffer.NextCompleteBlock()
		if !ok {
			return nil
		}
		if err := r.renderBlock(ctx, block); err != nil {
			return err
		}
	}
}

func (r *MarkdownRenderer) Flush(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if !r.isTTY {
		return nil
	}

	remaining := r.buffer.Remaining()
	r.buffer.Reset()
	if strings.TrimSpace(remaining) == "" {
		return nil
	}
	return r.renderBlock(ctx, remaining)
}

func (r *MarkdownRenderer) renderBlock(ctx context.Context, block string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if block == "" {
		return nil
	}
	if r.markdown == nil {
		_, err := io.WriteString(r.out, block)
		if err != nil {
			return fmt.Errorf("write raw block: %w", err)
		}
		r.firstBlock = false
		return nil
	}

	rendered, err := r.markdown.Render(block)
	if err != nil {
		if _, writeErr := io.WriteString(r.out, block); writeErr != nil {
			return fmt.Errorf("write raw block: %w", writeErr)
		}
		r.firstBlock = false
		return nil
	}
	if !r.firstBlock {
		rendered = strings.TrimLeft(rendered, "\n")
	}
	var writeErr error
	if r.downsample {
		_, writeErr = lipgloss.Fprint(r.out, rendered)
	} else {
		_, writeErr = io.WriteString(r.out, rendered)
	}
	if writeErr != nil {
		return fmt.Errorf("write rendered block: %w", writeErr)
	}
	r.firstBlock = false
	return nil
}
