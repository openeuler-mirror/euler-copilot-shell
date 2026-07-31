package renderer

import (
	"bytes"
	"context"
	"strings"
	"testing"
)

func TestReasoningWriter_NonTTYPlainPrefix(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningShow})

	if err := w.WriteDelta(context.Background(), "First paragraph.\n\nSecond paragraph."); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "  | Thinking: First paragraph.") {
		t.Fatalf("non-TTY output missing Thinking: prefix on first paragraph: %q", got)
	}
	if !strings.Contains(got, "  | Second paragraph.") {
		t.Fatalf("non-TTY output missing second paragraph prefix: %q", got)
	}
}

func TestReasoningWriter_HideNoOutput(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: true, Mode: ReasoningHide})

	if err := w.WriteDelta(context.Background(), "thinking text"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	if out.Len() > 0 {
		t.Fatalf("hide mode should produce no output, got %q", out.String())
	}
}

func TestReasoningWriter_TTYLeftBorder(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: true, Mode: ReasoningShow})

	if err := w.WriteDelta(context.Background(), "I should check the time.\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "│ Thinking: I should check the time.") {
		t.Fatalf("TTY output missing left-border + Thinking: prefix: %q", got)
	}
}

func TestReasoningWriter_FlushRemaining(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningShow})

	// No double newline, so nothing is flushed until Flush()
	if err := w.WriteDelta(context.Background(), "incomplete paragraph"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if out.Len() > 0 {
		t.Fatalf("should not flush before paragraph boundary, got %q", out.String())
	}

	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}
	got := out.String()
	if !strings.Contains(got, "  | Thinking: incomplete paragraph") {
		t.Fatalf("Flush() should emit remaining text with prefix: %q", got)
	}
}

func TestReasoningWriter_ParagraphBoundary(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningShow})

	// First paragraph complete, second incomplete
	if err := w.WriteDelta(context.Background(), "First.\n\nSecond"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "  | Thinking: First.") {
		t.Fatalf("first paragraph should be flushed with Thinking:: %q", got)
	}
	if strings.Contains(got, "Second") {
		t.Fatalf("second paragraph should not be flushed yet: %q", got)
	}

	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}
	got = out.String()
	// Second paragraph should NOT have Thinking: prefix
	if !strings.Contains(got, "  | Second") {
		t.Fatalf("second paragraph should be flushed after Flush(): %q", got)
	}
	if strings.Count(got, "Thinking:") != 1 {
		t.Fatalf("Thinking: should appear exactly once, got %d times in: %q", strings.Count(got, "Thinking:"), got)
	}
}

func TestReasoningWriter_ThinkingPrefixOnlyOnce(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningShow})

	// Three complete paragraphs.
	if err := w.WriteDelta(context.Background(), "Para one.\n\nPara two.\n\nPara three.\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	got := out.String()
	// Thinking: should appear exactly once (only on the first paragraph).
	count := strings.Count(got, "Thinking:")
	if count != 1 {
		t.Fatalf("Thinking: should appear exactly once, got %d: %q", count, got)
	}
	if !strings.Contains(got, "Para one.") && !strings.Contains(got, "Para two.") && !strings.Contains(got, "Para three.") {
		t.Fatalf("all three paragraphs should be present: %q", got)
	}
}

func TestReasoningWriter_MinimalMode(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningMinimal})

	// Write several paragraphs. Nothing should appear until Flush.
	if err := w.WriteDelta(context.Background(), "Let me think about this carefully. I need to analyze the code structure first.\n\nThen I will check the dependencies.\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	// No output yet.
	if out.Len() > 0 {
		t.Fatalf("minimal mode should not output during writes, got %q", out.String())
	}

	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "▶ Thinking:") {
		t.Fatalf("minimal flush should output '▶ Thinking:' prefix: %q", got)
	}
	if !strings.Contains(got, "Let me think about this carefully") {
		t.Fatalf("minimal flush should contain first sentence: %q", got)
	}
}

func TestReasoningWriter_MinimalModeShortText(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningMinimal})

	if err := w.WriteDelta(context.Background(), "Short thought."); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "Short thought...") {
		t.Fatalf("minimal flush should contain short text: %q", got)
	}
}

func TestReasoningWriter_HideMode(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: false, Mode: ReasoningHide})

	if err := w.WriteDelta(context.Background(), "Secret reasoning."); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if err := w.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	if out.Len() > 0 {
		t.Fatalf("hide mode should produce no output, got %q", out.String())
	}
}

func TestFirstSentence(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name string
		text string
		max  int
		want string
	}{
		{
			name: "single sentence",
			text: "This is a thought.",
			max:  100,
			want: "This is a thought.",
		},
		{
			name: "sentence boundary with uppercase next",
			text: "First thought. Next thought continues.",
			max:  100,
			want: "First thought.",
		},
		{
			name: "sentence boundary with lowercase next",
			text: "e.g. something here. and more",
			max:  100,
			want: "e.g. something here. and more",
		},
		{
			name: "paragraph boundary",
			text: "Line one.\n\nLine two.",
			max:  100,
			want: "Line one.",
		},
		{
			name: "truncation",
			text: "A very long sentence that goes on and on and on and on and on without any period whatsoever.",
			max:  30,
			want: "A very long sentence that goes...",
		},
		{
			name: "empty",
			text: "",
			max:  100,
			want: "",
		},
		{
			name: "whitespace only",
			text: "   \n  \t  ",
			max:  100,
			want: "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := firstSentence(tt.text, tt.max)
			if got != tt.want {
				t.Errorf("firstSentence(%q, %d) = %q, want %q", tt.text, tt.max, got, tt.want)
			}
		})
	}
}

func TestMarkdownRenderer_WriteReasoning(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewMarkdownRenderer(Options{
		Writer:        &out,
		IsTTY:         false,
		Width:         80,
		Theme:         "dark",
		ReasoningMode: "show",
	})
	if err != nil {
		t.Fatalf("NewMarkdownRenderer() error = %v", err)
	}

	if err := r.WriteReasoning(context.Background(), "Thinking about the answer.\n\n"); err != nil {
		t.Fatalf("WriteReasoning() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "  | Thinking: Thinking about the answer.") {
		t.Fatalf("reasoning output missing Thinking: prefix: %q", got)
	}
}

func TestMarkdownRenderer_WriteReasoningDisabled(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewMarkdownRenderer(Options{
		Writer:        &out,
		IsTTY:         false,
		Width:         80,
		Theme:         "dark",
		ReasoningMode: "hide",
	})
	if err != nil {
		t.Fatalf("NewMarkdownRenderer() error = %v", err)
	}

	if err := r.WriteReasoning(context.Background(), "Thinking about the answer."); err != nil {
		t.Fatalf("WriteReasoning() error = %v", err)
	}
	if err := r.FlushReasoning(context.Background()); err != nil {
		t.Fatalf("FlushReasoning() error = %v", err)
	}

	if out.Len() > 0 {
		t.Fatalf("disabled reasoning should produce no output, got %q", out.String())
	}
}

func TestMarkdownRenderer_ReasoningModeString(t *testing.T) {
	t.Parallel()

	// Test that the string-based ReasoningMode option works.
	var out bytes.Buffer
	r, err := NewMarkdownRenderer(Options{
		Writer:        &out,
		IsTTY:         false,
		Width:         80,
		Theme:         "dark",
		ReasoningMode: "minimal",
	})
	if err != nil {
		t.Fatalf("NewMarkdownRenderer() error = %v", err)
	}

	if err := r.WriteReasoning(context.Background(), "Let me analyze the code. I should check imports first."); err != nil {
		t.Fatalf("WriteReasoning() error = %v", err)
	}
	if err := r.FlushReasoning(context.Background()); err != nil {
		t.Fatalf("FlushReasoning() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "▶ Thinking:") {
		t.Fatalf("minimal mode should output '▶ Thinking:' prefix: %q", got)
	}
}

func TestReasoningWriter_EchoEchoesThenReplaces(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{
		Writer:      &out,
		IsTTY:       true,
		Mode:        ReasoningShow,
		EchoEnabled: true,
		Width:       120,
	})

	// A complete paragraph: echoed verbatim, then erased and replaced with
	// the styled block.
	if err := w.WriteDelta(context.Background(), "Hello thinking.\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	got := out.String()
	// Raw echo of the delta appears first.
	if !strings.HasPrefix(got, "Hello thinking.\n\n") {
		t.Fatalf("echo mode should write raw delta first, got %q", got)
	}
	// Erase sequences replace the echoed rows. "Hello thinking.\n\n" occupies
	// 3 terminal rows: the text line, the blank line, and the cursor line.
	eraseCount := strings.Count(got, "\x1b[2K")
	if eraseCount != 3 {
		t.Fatalf("expected 3 erase sequences for 3 terminal rows, got %d in %q", eraseCount, got)
	}
	cursorUpCount := strings.Count(got, "\x1b[1A")
	if cursorUpCount != 2 {
		t.Fatalf("expected 2 cursor-up sequences, got %d in %q", cursorUpCount, got)
	}
	// The rendered paragraph with the left-border + Thinking: prefix.
	if !strings.Contains(got, "│ Thinking: Hello thinking.") {
		t.Fatalf("rendered paragraph missing left-border + Thinking: prefix: %q", got)
	}
}

func TestReasoningWriter_EchoIncrementalDelta(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	w := NewReasoningWriter(ReasoningConfig{
		Writer:      &out,
		IsTTY:       true,
		Mode:        ReasoningShow,
		EchoEnabled: true,
		Width:       120,
	})

	// First delta: no paragraph boundary yet, so only echo — no erase.
	if err := w.WriteDelta(context.Background(), "Hello"); err != nil {
		t.Fatalf("WriteDelta(first) error = %v", err)
	}
	if got := out.String(); got != "Hello" {
		t.Fatalf("first delta should only echo, got %q", got)
	}

	// Second delta completes the paragraph: echo + erase + render.
	if err := w.WriteDelta(context.Background(), " thinking.\n\n"); err != nil {
		t.Fatalf("WriteDelta(second) error = %v", err)
	}
	got := out.String()
	if !strings.Contains(got, "Hello thinking.\n\n") {
		t.Fatalf("should contain echoed raw text, got %q", got)
	}
	if !strings.Contains(got, "\x1b[2K") {
		t.Fatalf("should erase echoed rows on paragraph completion, got %q", got)
	}
	if !strings.Contains(got, "│ Thinking: Hello thinking.") {
		t.Fatalf("should render the completed paragraph, got %q", got)
	}
}

func TestReasoningWriter_EchoDisabledByDefault(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	// EchoEnabled omitted (default false): behaves like the original
	// paragraph-level flush with no verbatim echo.
	w := NewReasoningWriter(ReasoningConfig{Writer: &out, IsTTY: true, Mode: ReasoningShow})

	if err := w.WriteDelta(context.Background(), "Hello thinking.\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	got := out.String()
	if strings.HasPrefix(got, "Hello thinking.\n\n") {
		t.Fatalf("echo should be disabled by default, got %q", got)
	}
	if strings.Contains(got, "\x1b[2K") {
		t.Fatalf("no erase sequences expected when echo disabled, got %q", got)
	}
	if !strings.Contains(got, "│ Thinking: Hello thinking.") {
		t.Fatalf("rendered paragraph should still be present, got %q", got)
	}
}

func TestEchoRenderer_ReasoningEchoesThenReplaces(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{
		Writer:        &out,
		IsTTY:         true,
		Width:         120,
		Theme:         "dark",
		Enabled:       true,
		ReasoningMode: "show",
	})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	if err := r.WriteReasoning(context.Background(), "Analyzing the problem.\n\n"); err != nil {
		t.Fatalf("WriteReasoning() error = %v", err)
	}

	got := out.String()
	// Raw echo of the reasoning delta appears first.
	if !strings.HasPrefix(got, "Analyzing the problem.\n\n") {
		t.Fatalf("EchoRenderer reasoning should echo raw delta first, got %q", got)
	}
	// Erase sequences replace the echoed rows.
	if !strings.Contains(got, "\x1b[2K") {
		t.Fatalf("EchoRenderer reasoning should erase echo rows, got %q", got)
	}
	// Rendered paragraph with Thinking: prefix. Glamour wraps/styles the
	// text (and places "Thinking:" and the body on separate lines), so
	// check the ANSI-stripped form for each piece.
	stripped := StripANSI(got)
	if !strings.Contains(stripped, "Thinking:") {
		t.Fatalf("EchoRenderer reasoning should render Thinking: prefix, stripped=%q", stripped)
	}
	if !strings.Contains(stripped, "Analyzing the problem.") {
		t.Fatalf("EchoRenderer reasoning should render the body text, stripped=%q", stripped)
	}
}
