package terminal

import (
	"bytes"
	"context"
	"errors"
	"io"
	"os"
	"testing"
	"time"
)

func TestWidthWithFallback_NilFileUsesFallback(t *testing.T) {
	if got := WidthWithFallback(nil, 120); got != 120 {
		t.Fatalf("WidthWithFallback(nil, 120) = %d, want 120", got)
	}
}

func TestWidthWithFallback_InvalidFallbackUsesDefault(t *testing.T) {
	if got := WidthWithFallback(nil, 0); got != DefaultWidth {
		t.Fatalf("WidthWithFallback(nil, 0) = %d, want %d", got, DefaultWidth)
	}
}

func TestNoColor_UsesNOColorEnvironment(t *testing.T) {
	lookup := func(key string) (string, bool) {
		return "", key == "NO_COLOR"
	}
	if !NoColor(lookup) {
		t.Fatal("NoColor() = false, want true")
	}
}

func TestPrompter_ReadLine(t *testing.T) {
	var out bytes.Buffer
	prompt := NewPrompter(bytes.NewBufferString("yes\n"), &out)

	got, err := prompt.ReadLine(context.Background(), "continue? ")
	if err != nil {
		t.Fatalf("ReadLine() error = %v", err)
	}
	if got != "yes" {
		t.Fatalf("ReadLine() = %q, want yes", got)
	}
	if out.String() != "continue? " {
		t.Fatalf("prompt output = %q, want %q", out.String(), "continue? ")
	}
}

func TestPrompter_ReadLineContextCanceled(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()

	prompt := NewPrompter(bytes.NewBufferString("ignored\n"), io.Discard)
	_, err := prompt.ReadLine(ctx, "")
	if !errors.Is(err, context.Canceled) {
		t.Fatalf("ReadLine() error = %v, want context.Canceled", err)
	}
}

func TestPrompter_ReadLineCancelsBlockedRead(t *testing.T) {
	reader, writer, err := os.Pipe()
	if err != nil {
		t.Fatalf("os.Pipe() error = %v", err)
	}
	defer func() { _ = reader.Close() }()
	defer func() { _ = writer.Close() }()

	prompt := NewPrompter(reader, io.Discard)
	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() {
		_, err := prompt.ReadLine(ctx, "")
		result <- err
	}()

	time.Sleep(20 * time.Millisecond)
	cancel()

	select {
	case err := <-result:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("ReadLine() error = %v, want context.Canceled", err)
		}
	case <-time.After(time.Second):
		t.Fatal("ReadLine() did not return after cancel")
	}
}
