package renderer

import (
	"context"
	"fmt"
	"io"
	"os"

	"charm.land/lipgloss/v2"

	wittyterm "atomgit.com/openeuler/euler-copilot-shell/internal/terminal"
)

const eraseLine = "\x1b[2K"
const cursorUp = "\x1b[1A"
const carriageReturn = "\r"

// EchoRenderer streams text deltas by echoing raw input immediately, then
// replacing each completed Markdown block with glamour-rendered output.
type EchoRenderer struct {
	out        io.Writer
	isTTY      bool
	downsample bool
	buffer     *BlockBuffer
	markdown   markdownEngine
	tracker    *RowTracker
	width      int
	firstBlock bool
	enabled    bool
	inputFile  *os.File
	outputFile *os.File
	reasoning  *ReasoningWriter
}

// EchoOptions configures an EchoRenderer.
type EchoOptions struct {
	Writer        io.Writer
	IsTTY         bool
	Width         int
	Theme         string
	NoColor       bool
	InputFile     *os.File
	OutputFile    *os.File
	Enabled       bool
	ShowReasoning bool   // deprecated: use ReasoningMode
	ReasoningMode string // "show" | "minimal" | "hide", default "show"
}

// NewEchoRenderer creates a streaming renderer that echoes deltas immediately
// and replaces completed Markdown blocks with rendered output.
func NewEchoRenderer(opts EchoOptions) (TextRenderer, error) {
	out := opts.Writer
	if out == nil {
		out = os.Stdout
	}

	width := opts.Width
	if width <= 0 {
		width = wittyterm.DefaultWidth
	}

	r := &EchoRenderer{
		out:        out,
		isTTY:      opts.IsTTY,
		downsample: opts.OutputFile != nil,
		buffer:     NewBlockBuffer(),
		tracker:    NewRowTracker(width),
		width:      width,
		firstBlock: true,
		enabled:    opts.Enabled && opts.IsTTY,
		inputFile:  opts.InputFile,
		outputFile: opts.OutputFile,
		reasoning: NewReasoningWriter(ReasoningConfig{
			Writer:     out,
			IsTTY:      opts.IsTTY,
			Downsample: opts.OutputFile != nil,
			Mode:       resolveReasoningMode(Options{ShowReasoning: opts.ShowReasoning, ReasoningMode: opts.ReasoningMode}),
		}),
	}

	if !opts.IsTTY {
		return r, nil
	}

	markdown, err := newMarkdownEngine(opts.Theme, opts.NoColor, width, opts.InputFile, opts.OutputFile)
	if err != nil {
		return nil, fmt.Errorf("create echo markdown renderer: %w", err)
	}
	r.markdown = markdown
	r.reasoning.markdown = markdown
	return r, nil
}

func (r *EchoRenderer) WriteDelta(ctx context.Context, delta string) error {
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

	if r.enabled {
		if _, err := io.WriteString(r.out, delta); err != nil {
			return fmt.Errorf("write echo delta: %w", err)
		}
		r.tracker.Track(delta)
	}

	if err := r.buffer.Append(delta); err != nil {
		return fmt.Errorf("buffer append: %w", err)
	}
	for {
		block, ok := r.buffer.NextCompleteBlock()
		if !ok {
			return nil
		}
		if err := r.renderBlockEcho(ctx, block); err != nil {
			return err
		}
	}
}

// Resize updates the terminal width used for row tracking. The glamour
// renderer width is not changed mid-stream; subsequent blocks may wrap at the
// original width until a new renderer is created.
func (r *EchoRenderer) Resize(width int) {
	if width <= 0 {
		width = wittyterm.DefaultWidth
	}
	r.width = width
	r.tracker.SetWidth(width)
}

// WriteReasoning writes reasoning text with dim styling via the embedded ReasoningWriter.
func (r *EchoRenderer) WriteReasoning(ctx context.Context, delta string) error {
	return r.reasoning.WriteDelta(ctx, delta)
}

// FlushReasoning flushes any buffered reasoning text.
func (r *EchoRenderer) FlushReasoning(ctx context.Context) error {
	return r.reasoning.Flush(ctx)
}

// ResetReasoning resets the first-paragraph flag.
func (r *EchoRenderer) ResetReasoning() {
	r.reasoning.ResetFirstParagraph()
}

func (r *EchoRenderer) Flush(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if !r.isTTY {
		return nil
	}

	remaining := r.buffer.Remaining()
	r.buffer.Reset()
	if remaining == "" {
		return nil
	}
	return r.renderBlockEcho(ctx, remaining)
}

func (r *EchoRenderer) renderBlockEcho(ctx context.Context, block string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if block == "" {
		return nil
	}

	if !r.enabled {
		return r.renderBlockFallback(ctx, block)
	}

	echoRows := r.tracker.Rows()
	if echoRows > 0 {
		if _, err := io.WriteString(r.out, carriageReturn); err != nil {
			return fmt.Errorf("write carriage return: %w", err)
		}
		for i := 0; i < echoRows; i++ {
			if _, err := io.WriteString(r.out, eraseLine); err != nil {
				return fmt.Errorf("erase echo line: %w", err)
			}
			if i < echoRows-1 {
				if _, err := io.WriteString(r.out, cursorUp); err != nil {
					return fmt.Errorf("cursor up: %w", err)
				}
			}
		}
		if _, err := io.WriteString(r.out, carriageReturn); err != nil {
			return fmt.Errorf("write carriage return after erase: %w", err)
		}
	}
	r.tracker.Reset()

	rendered, err := r.renderMarkdown(block)
	if err != nil {
		fallback := block
		if _, writeErr := io.WriteString(r.out, fallback); writeErr != nil {
			return fmt.Errorf("write raw block: %w", writeErr)
		}
		r.tracker.Track(fallback)
		r.firstBlock = false
		return nil
	}

	if !r.firstBlock {
		rendered = trimLeadingNewline(rendered)
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

func (r *EchoRenderer) renderBlockFallback(ctx context.Context, block string) error {
	if r.markdown == nil {
		_, err := io.WriteString(r.out, block)
		if err != nil {
			return fmt.Errorf("write raw block: %w", err)
		}
		r.firstBlock = false
		return nil
	}

	rendered, err := r.renderMarkdown(block)
	if err != nil {
		if _, writeErr := io.WriteString(r.out, block); writeErr != nil {
			return fmt.Errorf("write raw block: %w", writeErr)
		}
		r.firstBlock = false
		return nil
	}

	if !r.firstBlock {
		rendered = trimLeadingNewline(rendered)
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

func (r *EchoRenderer) renderMarkdown(block string) (string, error) {
	if r.markdown == nil {
		return block, nil
	}
	return r.markdown.Render(block)
}

func trimLeadingNewline(s string) string {
	if len(s) > 0 && s[0] == '\n' {
		return s[1:]
	}
	return s
}
