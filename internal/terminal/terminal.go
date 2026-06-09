package terminal

import (
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/muesli/cancelreader"
	"golang.org/x/term"
)

const DefaultWidth = 80

// IsTerminal reports whether file is attached to a terminal.
func IsTerminal(file *os.File) bool {
	if file == nil {
		return false
	}
	return term.IsTerminal(int(file.Fd()))
}

// Width returns the terminal width, falling back to DefaultWidth when unavailable.
func Width(file *os.File) int {
	return WidthWithFallback(file, DefaultWidth)
}

// WidthWithFallback returns the terminal width or fallback when probing fails.
func WidthWithFallback(file *os.File, fallback int) int {
	if fallback <= 0 {
		fallback = DefaultWidth
	}
	if file == nil {
		return fallback
	}
	width, _, err := term.GetSize(int(file.Fd()))
	if err != nil || width <= 0 {
		return fallback
	}
	return width
}

// NoColor reports whether the NO_COLOR convention is active.
func NoColor(lookupEnv func(string) (string, bool)) bool {
	if lookupEnv == nil {
		lookupEnv = os.LookupEnv
	}
	_, ok := lookupEnv("NO_COLOR")
	return ok
}

// SupportsColor reports whether color should be emitted to file.
func SupportsColor(file *os.File, lookupEnv func(string) (string, bool)) bool {
	return !NoColor(lookupEnv) && IsTerminal(file)
}

// Prompter reads a single line of user input.
type Prompter interface {
	ReadLine(ctx context.Context, label string) (string, error)
}

type linePrompter struct {
	in  io.Reader
	out io.Writer
}

// NewPrompter creates a reusable line prompt for permission, question, and REPL flows.
func NewPrompter(in io.Reader, out io.Writer) Prompter {
	if in == nil {
		in = io.Reader(os.Stdin)
	}
	if out == nil {
		out = io.Discard
	}
	return &linePrompter{in: in, out: out}
}

func (p *linePrompter) ReadLine(ctx context.Context, label string) (string, error) {
	select {
	case <-ctx.Done():
		return "", ctx.Err()
	default:
	}

	if label != "" {
		if _, err := fmt.Fprint(p.out, label); err != nil {
			return "", fmt.Errorf("write prompt: %w", err)
		}
	}

	reader := p.in
	cancelable, err := cancelreader.NewReader(p.in)
	if err == nil {
		reader = cancelable
		defer cancelable.Close()
		done := make(chan struct{})
		go func() {
			select {
			case <-ctx.Done():
				cancelable.Cancel()
			case <-done:
			}
		}()
		defer close(done)
	}

	line, err := readPromptLine(reader)
	if err != nil {
		if errors.Is(err, cancelreader.ErrCanceled) && ctx.Err() != nil {
			return "", ctx.Err()
		}
		if errors.Is(err, io.EOF) && line != "" {
			return line, nil
		}
		return "", fmt.Errorf("read prompt: %w", err)
	}
	return line, nil
}

func readPromptLine(reader io.Reader) (string, error) {
	var builder strings.Builder
	one := make([]byte, 1)
	for {
		n, err := reader.Read(one)
		if n > 0 {
			if one[0] == '\n' {
				return strings.TrimRight(builder.String(), "\r"), nil
			}
			builder.WriteByte(one[0])
		}
		if err != nil {
			return strings.TrimRight(builder.String(), "\r"), err
		}
	}
}
