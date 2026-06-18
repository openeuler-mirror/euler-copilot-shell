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
