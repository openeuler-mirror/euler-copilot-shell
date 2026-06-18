package renderer

import (
	"context"
	"fmt"
	"io"
	"strings"
	"time"
	"unicode"
	"unicode/utf8"

	"charm.land/lipgloss/v2"
)

// ReasoningMode controls how reasoning (thinking) text is presented to the user.
// Mirrors OpenCode's thinking modes: show (full markdown), hide (collapsed single
// line), and the equivalent of "off" which discards reasoning entirely.
type ReasoningMode string

const (
	// ReasoningShow renders reasoning with a "│ " left-border prefix and full
	// Markdown rendering (via glamour). The first paragraph is prefixed with
	// "Thinking:" in italic. This is the default mode.
	ReasoningShow ReasoningMode = "show"
	// ReasoningMinimal collects all reasoning text silently and outputs a single
	// collapsed line at flush time: "▶ Thinking: {first sentence}...  {duration}".
	ReasoningMinimal ReasoningMode = "minimal"
	// ReasoningHide discards all reasoning text. No output is produced.
	ReasoningHide ReasoningMode = "hide"
)

// ReasoningConfig groups the options for constructing a ReasoningWriter.
type ReasoningConfig struct {
	Writer     io.Writer
	IsTTY      bool
	Downsample bool
	Mode       ReasoningMode
	// Markdown is the glamour engine used to render reasoning content as
	// Markdown. When nil on TTY, reasoning falls back to plain text output.
	Markdown markdownEngine
}

// ReasoningWriter renders reasoning (thinking) deltas with a visual style
// that is distinct from the final answer text.
//
// In show mode (default), reasoning is rendered as full Markdown with a
// "│ " left-border prefix on each line. The first paragraph carries a
// "Thinking:" identifier.
//
// In minimal mode, all reasoning text is collected silently and a single
// collapsed line is emitted at Flush time.
//
// In hide mode, all reasoning text is discarded.
type ReasoningWriter struct {
	out        io.Writer
	isTTY      bool
	downsample bool
	mode       ReasoningMode
	markdown   markdownEngine

	// buffer accumulates in-flight reasoning delta text that hasn't yet
	// reached a paragraph boundary.
	buffer strings.Builder
	// firstPara tracks whether we have emitted the first paragraph yet.
	// Used to add the "Thinking:" prefix only to the first output block.
	firstPara bool

	// ---- minimal mode state ----
	// startTime records when the first reasoning delta arrived.
	startTime time.Time
	started   bool
	// collected accumulates all reasoning text (for extracting the summary).
	collected strings.Builder
}

// NewReasoningWriter creates a reasoning writer. When mode is ReasoningHide,
// all writes are silently discarded.
func NewReasoningWriter(cfg ReasoningConfig) *ReasoningWriter {
	if cfg.Mode == "" {
		cfg.Mode = ReasoningShow
	}
	return &ReasoningWriter{
		out:        cfg.Writer,
		isTTY:      cfg.IsTTY,
		downsample: cfg.Downsample,
		mode:       cfg.Mode,
		markdown:   cfg.Markdown,
		firstPara:  true,
	}
}

// WriteDelta accumulates reasoning text. In show mode, complete paragraphs
// (separated by double newlines) are flushed immediately. In minimal and
// hide modes, text is collected silently.
func (w *ReasoningWriter) WriteDelta(ctx context.Context, delta string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if w.mode == ReasoningHide || delta == "" {
		return nil
	}

	if w.mode == ReasoningMinimal {
		if !w.started {
			w.startTime = time.Now()
			w.started = true
		}
		w.collected.WriteString(delta)
		return nil
	}

	// Show mode: accumulate and flush complete paragraphs.
	w.buffer.WriteString(delta)
	for {
		text := w.buffer.String()
		idx := strings.Index(text, "\n\n")
		if idx < 0 {
			break
		}
		paragraph := text[:idx+1] // include single trailing newline
		w.buffer.Reset()
		w.buffer.WriteString(text[idx+2:])
		if err := w.flushParagraph(ctx, paragraph); err != nil {
			return fmt.Errorf("write reasoning: %w", err)
		}
	}
	return nil
}

// Flush emits any remaining buffered (show) or collected (minimal) reasoning
// text. In hide mode this is a no-op.
func (w *ReasoningWriter) Flush(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	switch w.mode {
	case ReasoningHide:
		return nil
	case ReasoningMinimal:
		return w.flushMinimal(ctx)
	default: // ReasoningShow
		remaining := strings.TrimRight(w.buffer.String(), "\n")
		if remaining == "" {
			w.buffer.Reset()
			return nil
		}
		w.buffer.Reset()
		remaining += "\n"
		return w.flushParagraph(ctx, remaining)
	}
}

// Duration returns the time elapsed since the first reasoning delta was
// received. Returns zero if no deltas have been written.
func (w *ReasoningWriter) Duration() time.Duration {
	if !w.started {
		return 0
	}
	return time.Since(w.startTime)
}

// ResetFirstParagraph resets the first-paragraph flag so the next
// reasoning delta will produce a fresh "Thinking:" label.
func (w *ReasoningWriter) ResetFirstParagraph() {
	w.firstPara = true
}

// CollectedText returns all reasoning text collected so far. Used by tests
// and by minimal mode's Flush.
func (w *ReasoningWriter) CollectedText() string {
	if w.mode == ReasoningMinimal {
		return w.collected.String()
	}
	return w.buffer.String()
}

// ---- internal helpers ----

// flushParagraph renders a single reasoning paragraph with left-border styling.
func (w *ReasoningWriter) flushParagraph(ctx context.Context, paragraph string) error {
	if err := ctx.Err(); err != nil {
		return err
	}
	if paragraph == "" {
		return nil
	}

	rendered, err := w.renderMarkdown(paragraph)
	if err != nil {
		// Fall back to plain text if Markdown rendering fails.
		rendered = paragraph
	}

	lines := strings.Split(rendered, "\n")
	// Remove trailing empty line from Split.
	if len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}

	var b strings.Builder
	// Add a blank line before the first reasoning paragraph as padding.
	// Markdown blocks carry their own padding from glamour, but reasoning
	// appears after tools or other output and needs a visual separator.
	if w.firstPara {
		if w.isTTY {
			b.WriteString("│ \n")
		} else {
			b.WriteString("  | \n")
		}
	}
	for i, line := range lines {
		if w.isTTY {
			b.WriteString("│ ")
		} else {
			b.WriteString("  | ")
		}
		// First paragraph, first line gets the "Thinking:" prefix.
		if w.firstPara && i == 0 {
			b.WriteString("Thinking: ")
		}
		b.WriteString(line)
		b.WriteString("\n")
	}

	output := b.String()
	if w.isTTY {
		// Apply dim + italic styling to the entire reasoning block.
		styled := reasoningDimStyle().Render(output)
		if w.downsample {
			_, err = lipgloss.Fprint(w.out, styled)
		} else {
			_, err = io.WriteString(w.out, styled)
		}
	} else {
		_, err = io.WriteString(w.out, output)
	}
	if err != nil {
		return fmt.Errorf("write reasoning: %w", err)
	}

	w.firstPara = false
	return nil
}

// renderMarkdown converts reasoning text through glamour for rich formatting.
func (w *ReasoningWriter) renderMarkdown(text string) (string, error) {
	if !w.isTTY || w.markdown == nil {
		return text, nil
	}
	return w.markdown.Render(text)
}

// flushMinimal outputs the collapsed single-line reasoning summary.
func (w *ReasoningWriter) flushMinimal(ctx context.Context) error {
	if err := ctx.Err(); err != nil {
		return err
	}

	text := w.collected.String()
	if text == "" {
		return nil
	}

	summary := firstSentence(text, 80)
	if summary == "" {
		return nil
	}

	duration := w.Duration()
	line := fmt.Sprintf("▶ Thinking: %s...", summary)
	if duration > 0 {
		line += fmt.Sprintf("  %s", formatReasoningDuration(duration))
	}

	if w.isTTY {
		styled := reasoningMinimalStyle().Render(line)
		if w.downsample {
			_, err := lipgloss.Fprintln(w.out, styled)
			return err
		}
	}
	_, err := fmt.Fprintln(w.out, line)
	return err
}

// ---- style helpers ----

// reasoningDimStyle returns the lipgloss style for reasoning text on TTY.
// Uses a muted foreground (color 8) with italic — consistent with OpenCode's
// theme.textMuted approach.
func reasoningDimStyle() lipgloss.Style {
	return lipgloss.NewStyle().
		Foreground(lipgloss.Color("8")).
		Italic(true)
}

// reasoningMinimalStyle returns the style for the collapsed reasoning line.
func reasoningMinimalStyle() lipgloss.Style {
	return lipgloss.NewStyle().
		Foreground(lipgloss.Color("3")). // yellow/warning tone
		Italic(true)
}

// ---- text helpers ----

// firstSentence extracts the first sentence from text, truncated to maxChars.
// A sentence ends at ". " followed by a capital letter, or at "\n\n".
func firstSentence(text string, maxChars int) string {
	text = strings.TrimSpace(text)
	if text == "" {
		return ""
	}

	// Look for sentence boundary: ". " followed by uppercase letter or CJK.
	for i := 0; i < len(text)-1; i++ {
		if text[i] == '.' && text[i+1] == ' ' {
			// Check if next non-space char is uppercase.
			rest := strings.TrimLeft(text[i+2:], " ")
			if len(rest) > 0 {
				r, _ := utf8.DecodeRuneInString(rest)
				if unicode.IsUpper(r) {
					return ellipsis(text[:i+1], maxChars)
				}
			}
		}
		// Also break at double newline (paragraph boundary).
		if text[i] == '\n' && i+1 < len(text) && text[i+1] == '\n' {
			return ellipsis(text[:i], maxChars)
		}
	}

	return ellipsis(text, maxChars)
}

// ellipsis truncates s to maxChars runes, appending "..." if truncated.
func ellipsis(s string, maxChars int) string {
	s = strings.TrimSpace(s)
	if len(s) <= maxChars {
		return s
	}
	// Try to break at a space near maxChars.
	end := maxChars
	for end > maxChars/2 && s[end] != ' ' {
		end--
	}
	if end <= maxChars/2 {
		end = maxChars
	}
	return strings.TrimSpace(s[:end]) + "..."
}

// formatReasoningDuration formats a duration for the minimal reasoning line.
func formatReasoningDuration(d time.Duration) string {
	ms := float64(d) / float64(time.Millisecond)
	secs := ms / 1000
	switch {
	case secs < 0.001:
		return fmt.Sprintf("%.0fµs", ms*1000)
	case secs < 1:
		return fmt.Sprintf("%.0fms", ms)
	case secs < 60:
		return fmt.Sprintf("%.1fs", secs)
	default:
		m := int(secs) / 60
		s := int(secs) % 60
		return fmt.Sprintf("%dm%ds", m, s)
	}
}
