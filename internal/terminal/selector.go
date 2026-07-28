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
//
// Rendering uses the alternate screen buffer (DECSET 1049) to avoid terminal
// scrolling from interfering with cursor position tracking. On exit the main
// screen buffer is restored automatically.
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

	// Enter alternate screen buffer before defer so exit happens last (LIFO).
	_, _ = fmt.Fprint(p.out, "\x1b[?1049h\x1b[H")
	defer func() {
		_, _ = fmt.Fprint(p.out, "\x1b[?1049l")
		_ = term.Restore(fd, prevState)
	}()

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
	isFirst := true
	renderSelect(p.out, title, options, selected, isFirst)
	isFirst = false

	// Read keys.
	buf := make([]byte, 6)
	for {
		n, err := cancelReader.Read(buf)
		if err != nil {
			if errors.Is(err, cancelreader.ErrCanceled) && ctx.Err() != nil {
				return -1, ctx.Err()
			}
			if errors.Is(err, io.EOF) {
				return -1, nil
			}
			return -1, fmt.Errorf("select: read input: %w", err)
		}

		key := buf[:n]

		switch {
		case isEnter(key):
			return selected, nil
		case isEscape(key):
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
			return -1, context.Canceled
		default:
			// number key quick-select: 1-9 map to indices 0-8
			if len(key) == 1 && key[0] >= '1' && key[0] <= '9' {
				idx := int(key[0] - '1')
				if idx < len(options) {
					return idx, nil
				}
			}
		}

		renderSelect(p.out, title, options, selected, isFirst)
	}
}

// renderSelect draws the select list at the current cursor position.
// It assumes the terminal is in raw mode and uses ANSI escape codes.
//
// On the first render (isFirst=true), it prints at the current cursor position
// without any clearing. On re-renders (isFirst=false), it moves to the top of
// the screen with \x1b[H, clears to end of screen with \x1b[0J, and re-draws.
//
// The select loop uses the alternate screen buffer, so absolute positioning
// (\x1b[H) is reliable — there is no scrollback to interfere.
func renderSelect(out io.Writer, title string, options []SelectOption, selected int, isFirst bool) {
	var b strings.Builder

	if !isFirst {
		b.WriteString("\x1b[H\x1b[0J")
	}

	// Title — supports multi-line titles where the first line is rendered
	// bold (header) and subsequent lines are rendered as normal-indented
	// body text. A blank separator is inserted between the title block
	// and the options.
	if title != "" {
		titleLines := strings.Split(title, "\n")
		// Header (first line): bold.
		b.WriteString("\x1b[1m")
		b.WriteString(titleLines[0])
		b.WriteString("\x1b[0m\r\n")
		// Body (remaining lines): normal, indented 2 spaces.
		for _, line := range titleLines[1:] {
			b.WriteString("\x1b[2K  ")
			b.WriteString(line)
			b.WriteString("\r\n")
		}
		// Blank separator between title block and options.
		b.WriteString("\x1b[2K\r\n")
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

	_, _ = fmt.Fprint(out, b.String())
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
