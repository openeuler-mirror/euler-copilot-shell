package renderer

import (
	"bytes"
	"context"
	"errors"
	"flag"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

var updateRendererGolden = flag.Bool("update", false, "update renderer golden files")

func TestBlockBoundary(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name   string
		input  string
		want   string
		found  bool
		remain string
	}{
		{name: "paragraph", input: "hello\n\n", want: "hello\n\n", found: true},
		{name: "heading", input: "# Title\n", want: "# Title\n", found: true},
		{name: "list", input: "- one\n- two\n\n", want: "- one\n- two\n\n", found: true},
		{name: "quote", input: "> quoted\n> line\n\n", want: "> quoted\n> line\n\n", found: true},
		{name: "thematic break", input: "---\n", want: "---\n", found: true},
		{name: "fenced code", input: "```go\nfmt.Println(\"hi\")\n```\n", want: "```go\nfmt.Println(\"hi\")\n```\n", found: true},
		{name: "unclosed code fence", input: "```go\nfmt.Println(\"hi\")\n", found: false, remain: "```go\nfmt.Println(\"hi\")\n"},
		{name: "paragraph interrupted by heading", input: "first line\n# Title\n", want: "first line\n", found: true, remain: "# Title\n"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			buf := NewBlockBuffer()
			if err := buf.Append(tt.input); err != nil {
				t.Fatalf("Append() error = %v", err)
			}
			got, ok := buf.NextCompleteBlock()
			if ok != tt.found {
				t.Fatalf("NextCompleteBlock() found=%v, want %v", ok, tt.found)
			}
			if got != tt.want {
				t.Fatalf("NextCompleteBlock() = %q, want %q", got, tt.want)
			}
			if remaining := buf.Remaining(); remaining != tt.remain {
				t.Fatalf("Remaining() = %q, want %q", remaining, tt.remain)
			}
		})
	}
}

func TestMarkdownRenderer_WritesOnBlockBoundaryBeforeFlush(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewMarkdownRenderer(Options{Writer: &out, IsTTY: true, Width: 120, Theme: "dark"})
	if err != nil {
		t.Fatalf("NewMarkdownRenderer() error = %v", err)
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
	if strings.Contains(streamed, "Next") {
		t.Fatalf("output after block boundary contains tail block %q, want only completed block", streamed)
	}

	if err := r.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}
	if !strings.Contains(out.String(), "Next") {
		t.Fatalf("output after Flush() = %q, want tail block rendered", out.String())
	}
}

func TestMarkdownRenderer_Golden(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewMarkdownRenderer(Options{Writer: &out, IsTTY: true, Width: 120, Theme: "dark"})
	if err != nil {
		t.Fatalf("NewMarkdownRenderer() error = %v", err)
	}

	chunks := []string{
		"# Title\n\nParagraph one",
		".\n\n- one\n- two\n\n> quote\n\n```go\nfmt.Println(\"hi\")\n```\n",
	}
	for _, chunk := range chunks {
		if err := r.WriteDelta(context.Background(), chunk); err != nil {
			t.Fatalf("WriteDelta(%q) error = %v", chunk, err)
		}
	}
	if err := r.Flush(context.Background()); err != nil {
		t.Fatalf("Flush() error = %v", err)
	}

	assertGolden(t, filepath.Join("..", "..", "test", "testdata", "renderer", "phase1_ansi.golden"), out.Bytes())
}

func TestMarkdownRenderer_NonTTYWritesRawMarkdown(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	r, err := NewMarkdownRenderer(Options{Writer: &out, IsTTY: false, Width: 120, Theme: "dark"})
	if err != nil {
		t.Fatalf("NewMarkdownRenderer() error = %v", err)
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

func TestBlockBuffer_Overflow(t *testing.T) {
	t.Parallel()

	buf := NewBlockBuffer()
	// Fill to near max
	chunk := strings.Repeat("x", maxBufferSize)
	if err := buf.Append(chunk); err != nil {
		t.Fatalf("Append(at limit) error = %v", err)
	}
	// Next byte should overflow
	if err := buf.Append("y"); !errors.Is(err, ErrBufferFull) {
		t.Fatalf("Append(over limit) error = %v, want ErrBufferFull", err)
	}
}

func assertGolden(t *testing.T, path string, got []byte) {
	t.Helper()
	if *updateRendererGolden {
		if err := os.WriteFile(path, got, 0o644); err != nil {
			t.Fatalf("write golden %s: %v", path, err)
		}
	}
	want, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read golden %s: %v", path, err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("golden mismatch for %s\n--- got ---\n%s\n--- want ---\n%s", path, got, want)
	}
}
