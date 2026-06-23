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

// Select renders an interactive list with arrow-key navigation and returns the
// chosen index. It requires the input to be a terminal in raw mode.
func (p *linePrompter) Select(ctx context.Context, title string, options []SelectOption) (int, error) {
	if len(options) == 0 {
		return -1, fmt.Errorf("select: no options provided")
	}

	file, ok := p.in.(*os.File)
	if !ok || !term.IsTerminal(int(file.Fd())) {
		return -1, fmt.Errorf("select: input is not a terminal")
	}

	fd := int(file.Fd())
	prevState, err := term.MakeRaw(fd)
	if err != nil {
		return -1, fmt.Errorf("select: enter raw mode: %w", err)
	}
	defer func() { _ = term.Restore(fd, prevState) }()

	// Wrap stdin with cancelreader so ctx.Done() can interrupt the blocking read.
	cancelReader, err := cancelreader.NewReader(file)
	if err != nil {
		return -1, fmt.Errorf("select: create cancel reader: %w", err)
	}
	defer func() { _ = cancelReader.Close() }()

	done := make(chan struct{})
	go func() {
		select {
		case <-ctx.Done():
			cancelReader.Cancel()
		case <-done:
		}
	}()
	defer close(done)

	// Print initial state.
	selected := 0
	renderSelect(p.out, title, options, selected)

	// Read keys.
	buf := make([]byte, 6)
	for {
		n, err := cancelReader.Read(buf)
		if err != nil {
			if errors.Is(err, cancelreader.ErrCanceled) && ctx.Err() != nil {
				eraseSelect(p.out, len(options))
				return -1, ctx.Err()
			}
			if errors.Is(err, io.EOF) {
				eraseSelect(p.out, len(options))
				return -1, nil
			}
			eraseSelect(p.out, len(options))
			return -1, fmt.Errorf("select: read input: %w", err)
		}

		key := buf[:n]

		switch {
		case isEnter(key):
			eraseSelect(p.out, len(options))
			return selected, nil
		case isEscape(key):
			eraseSelect(p.out, len(options))
			return -1, nil
		case isUp(key):
			if selected > 0 {
				selected--
			}
		case isDown(key):
			if selected < len(options)-1 {
				selected++
			}
		case isCtrlC(key):
			eraseSelect(p.out, len(options))
			return -1, context.Canceled
		default:
			// number key quick-select: 1-9 map to indices 0-8
			if len(key) == 1 && key[0] >= '1' && key[0] <= '9' {
				idx := int(key[0] - '1')
				if idx < len(options) {
					eraseSelect(p.out, len(options))
					return idx, nil
				}
			}
		}

		renderSelect(p.out, title, options, selected)
	}
}

// renderSelect draws the select list at the current cursor position.
// It assumes the terminal is in raw mode and uses ANSI escape codes.
func renderSelect(out io.Writer, title string, options []SelectOption, selected int) {
	// Move cursor back up to the first option line (or title line).
	// We use a stable rendering: title + one line per option.
	lines := len(options)
	if title != "" {
		lines++
	}

	var b strings.Builder

	// If this is a re-render, clear previous output and move cursor back up.
	fmt.Fprintf(&b, "\x1b[%dA", lines) // move up
	b.WriteString("\x1b[0J")           // clear from cursor to end

	// Title.
	if title != "" {
		b.WriteString("\x1b[1m") // bold
		b.WriteString(title)
		b.WriteString("\x1b[0m\r\n")
	}

	// Options.
	for i, opt := range options {
		// Clear line first.
		b.WriteString("\x1b[2K")

		if i == selected {
			b.WriteString("\x1b[7m") // reverse video for highlight
		}

		prefix := "  "
		if i == selected {
			prefix = "❯ "
		}
		b.WriteString(prefix)

		// Shortcut key hint.
		if i < 9 {
			fmt.Fprintf(&b, "%d) ", i+1)
		} else {
			b.WriteString("   ")
		}

		b.WriteString(opt.Label)

		if opt.Description != "" {
			b.WriteString(" — ")
			b.WriteString(opt.Description)
		}

		if i == selected {
			b.WriteString("\x1b[0m") // reset reverse video
		}

		if i < len(options)-1 {
			b.WriteString("\r\n")
		}
	}

	// Hint footer.
	b.WriteString("\r\n\x1b[2K")
	b.WriteString("  ↑/↓ navigate  ↵ select  esc cancel")

	// Move cursor back up to the first option.
	cursorUp := len(options) + 1 // options + footer
	if title != "" {
		cursorUp++
	}
	fmt.Fprintf(&b, "\x1b[%dA", cursorUp)

	_, _ = fmt.Fprint(out, b.String())
}

func eraseSelect(out io.Writer, optionCount int) {
	// Clear the select UI: move cursor to start of options area and clear to end.
	lines := optionCount + 1 // options + footer
	if lines > 0 {
		_, _ = fmt.Fprintf(out, "\x1b[%dB\x1b[%dA\x1b[0J", lines-1, lines)
	}
}

func isEnter(key []byte) bool {
	return len(key) == 1 && (key[0] == '\r' || key[0] == '\n')
}

func isEscape(key []byte) bool {
	return len(key) == 1 && key[0] == 27
}

func isUp(key []byte) bool {
	return len(key) == 3 && key[0] == 27 && key[1] == '[' && key[2] == 'A'
}

func isDown(key []byte) bool {
	return len(key) == 3 && key[0] == 27 && key[1] == '[' && key[2] == 'B'
}

func isCtrlC(key []byte) bool {
	return len(key) == 1 && key[0] == 3
}
