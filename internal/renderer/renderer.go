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
	// WriteReasoning writes reasoning (thinking) deltas with a separate visual
	// style. When the reasoning renderer is disabled, this is a no-op.
	WriteReasoning(ctx context.Context, delta string) error
	// FlushReasoning flushes any buffered reasoning text.
	FlushReasoning(ctx context.Context) error
	// ResetReasoning resets the reasoning writer's first-paragraph flag so the
	// next reasoning block starts with a fresh "Thinking:" label.
	ResetReasoning()
	// Resize notifies the renderer that the terminal width has changed.
	// Implementations that track rows should update their internal width;
	// others may treat this as a no-op.
	Resize(width int)
}

// Options controls MarkdownRenderer construction.
type Options struct {
	Writer        io.Writer
	IsTTY         bool
	Width         int
	Theme         string
	NoColor       bool
	InputFile     *os.File
	OutputFile    *os.File
	ShowReasoning bool   // deprecated: use ReasoningMode
	ReasoningMode string // "show" | "minimal" | "hide", default "show"
}

// MarkdownRenderer implements Phase 1 block-boundary Markdown rendering.
type MarkdownRenderer struct {
	out        io.Writer
	isTTY      bool
	downsample bool
	buffer     *BlockBuffer
	markdown   markdownEngine
	firstBlock bool
	reasoning  *ReasoningWriter
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
		reasoning: NewReasoningWriter(ReasoningConfig{
			Writer:     out,
			IsTTY:      opts.IsTTY,
			Downsample: opts.OutputFile != nil,
			Mode:       resolveReasoningMode(opts),
		}),
	}
	if !opts.IsTTY {
		return r, nil
	}

	markdown, err := newMarkdownEngine(opts.Theme, opts.NoColor, width, opts.InputFile, opts.OutputFile)
	if err != nil {
		return nil, fmt.Errorf("create markdown renderer: %w", err)
	}
	r.markdown = markdown
	r.reasoning.markdown = markdown
	return r, nil
}

// resolveReasoningMode converts the options into a ReasoningMode.
// Backward-compatible: if ReasoningMode is set, it takes precedence;
// otherwise ShowReasoning=true maps to "show", false to "hide".
func resolveReasoningMode(opts Options) ReasoningMode {
	if opts.ReasoningMode != "" {
		switch strings.ToLower(strings.TrimSpace(opts.ReasoningMode)) {
		case "minimal":
			return ReasoningMinimal
		case "hide":
			return ReasoningHide
		default:
			return ReasoningShow
		}
	}
	if opts.ShowReasoning {
		return ReasoningShow
	}
	return ReasoningHide
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

	if err := r.buffer.Append(delta); err != nil {
		return fmt.Errorf("buffer append: %w", err)
	}
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

// Resize is a no-op for Phase 1 — MarkdownRenderer does not track echo rows.
func (r *MarkdownRenderer) Resize(_ int) {}

// WriteReasoning writes reasoning text with dim styling via the embedded ReasoningWriter.
func (r *MarkdownRenderer) WriteReasoning(ctx context.Context, delta string) error {
	return r.reasoning.WriteDelta(ctx, delta)
}

// FlushReasoning flushes any buffered reasoning text.
func (r *MarkdownRenderer) FlushReasoning(ctx context.Context) error {
	return r.reasoning.Flush(ctx)
}

// ResetReasoning resets the first-paragraph flag so the next reasoning
// block starts with a fresh "Thinking:" label.
func (r *MarkdownRenderer) ResetReasoning() {
	r.reasoning.ResetFirstParagraph()
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
