package renderer

import (
	"bytes"
	"context"
	"strings"
	"testing"
)

func TestEchoRenderer_NonTTYWritesRawMarkdown(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: false, Width: 120, Theme: "dark"})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	input := "# Title\n\nParagraph\n"
	if err := r.WriteDelta(context.Background(), input); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if err := r.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}
	if out.String() != input {
		t.Fatalf("non-TTY output = %q, want raw markdown %q", out.String(), input)
	}
	if strings.Contains(out.String(), "\x1b[") {
		t.Fatalf("non-TTY output = %q, want no ANSI", out.String())
	}
}

func TestEchoRenderer_DisabledFallsBackToPhase1(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: true, Width: 120, Theme: "dark", Enabled: false})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	if err := r.WriteDelta(context.Background(), "Paragraph\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}
	if err := r.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	if out.Len() == 0 {
		t.Fatal("disabled EchoRenderer should still render via fallback")
	}
}

func TestEchoRenderer_EnabledEchoesThenReplaces(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: true, Width: 120, Theme: "dark", Enabled: true})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	if err := r.WriteDelta(context.Background(), "Hello\n\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "Hello\n\n") {
		t.Fatalf("EchoRenderer should echo raw delta first, got %q", got)
	}
	if !strings.Contains(got, "\x1b[2K") {
		t.Fatalf("EchoRenderer should erase echo lines, got %q", got)
	}
	// "Hello\n\n" occupies 3 terminal rows: line with "Hello", blank line,
	// and the cursor's current line. All 3 must be erased.
	eraseCount := strings.Count(got, "\x1b[2K")
	if eraseCount != 3 {
		t.Fatalf("expected 3 erase sequences for 3 terminal rows, got %d in %q", eraseCount, got)
	}
	cursorUpCount := strings.Count(got, "\x1b[1A")
	if cursorUpCount != 2 {
		t.Fatalf("expected 2 cursor-up sequences, got %d in %q", cursorUpCount, got)
	}
}

func TestEchoRenderer_EraseCountIncrementalDelta(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: true, Width: 120, Theme: "dark", Enabled: true})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	// Send text in small chunks to simulate streaming.
	if err := r.WriteDelta(context.Background(), "Hello"); err != nil {
		t.Fatalf("WriteDelta(first) error = %v", err)
	}
	if err := r.WriteDelta(context.Background(), "\n\n"); err != nil {
		t.Fatalf("WriteDelta(second) error = %v", err)
	}

	got := out.String()
	// After echoing "Hello" (no newline) then "\n\n", the tracker has
	// rows=2, cursorCol=0. TerminalRows = 3. All 3 lines must be erased.
	eraseCount := strings.Count(got, "\x1b[2K")
	if eraseCount != 3 {
		t.Fatalf("expected 3 erase sequences for incremental delta, got %d in %q", eraseCount, got)
	}
}

func TestEchoRenderer_EraseCountNoTrailingNewline(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: true, Width: 120, Theme: "dark", Enabled: true})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	// "Title\n\nBody" — "Title\n\n" is a complete block, "Body" remains buffered.
	if err := r.WriteDelta(context.Background(), "Title\n\nBody"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	got := out.String()
	// The echo "Title\n\nBody" occupies 4 terminal rows:
	//   line 0: Title
	//   line 1: (empty)
	//   line 2: Body  (cursorCol > 0)
	// TerminalRows = rows(2) + 1 = 3... wait, "Body" is on the current line.
	// rows=2 (two \n), cursorCol=4 ("Body"). TerminalRows = 2 + 1 = 3.
	// But we need to erase all 3 visible lines: Title, empty, Body.
	eraseCount := strings.Count(got, "\x1b[2K")
	if eraseCount != 3 {
		t.Fatalf("expected 3 erase sequences for Title+Body, got %d in %q", eraseCount, got)
	}
}

func TestEchoRenderer_FlushUnclosedBlock(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: true, Width: 120, Theme: "dark", Enabled: false})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	if err := r.WriteDelta(context.Background(), "```go\nfmt.Println(\"hi\")\n"); err != nil {
		t.Fatalf("WriteDelta() error = %v", err)
	}

	if err := r.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}
	got := out.String()
	if !strings.Contains(StripANSI(got), "fmt.Println") {
		t.Fatalf("Flush should output unclosed block content, got %q", StripANSI(got))
	}
}

func TestEchoRenderer_WritesOnBlockBoundary(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewEchoRenderer(EchoOptions{Writer: &out, IsTTY: true, Width: 120, Theme: "dark", Enabled: false})
	if err != nil {
		t.Fatalf("NewEchoRenderer() error = %v", err)
	}

	if err := r.WriteDelta(context.Background(), "Paragraph"); err != nil {
		t.Fatalf("WriteDelta(first) error = %v", err)
	}
	if out.Len() != 0 {
		t.Fatalf("output after incomplete paragraph = %q, want empty", out.String())
	}

	if err := r.WriteDelta(context.Background(), "\n\nNext"); err != nil {
		t.Fatalf("WriteDelta(second) error = %v", err)
	}
	streamed := out.String()
	if streamed == "" {
		t.Fatal("output after block boundary = empty, want streamed rendered block")
	}
}
