package terminal

import (
	"fmt"
	"io"
	"os"
	"strings"

	"golang.org/x/term"
)

// ListOption represents a single selectable item in the interactive list.
type ListOption struct {
	Label string
	Value string
}

// SelectResult contains the outcome of an interactive selection.
type SelectResult struct {
	Index int
	Value string
}

// RunSelector displays an interactive list and returns the user's selection.
// Returns nil if the user cancels (Ctrl+C, Escape, or q).
func RunSelector(in *os.File, out *os.File, title string, options []ListOption) (*SelectResult, error) {
	if len(options) == 0 {
		return nil, fmt.Errorf("no options to select from")
	}
	if !IsTerminal(in) || !IsTerminal(out) {
		return nil, fmt.Errorf("interactive selection requires a terminal")
	}

	fd := int(in.Fd())
	oldState, err := term.MakeRaw(fd)
	if err != nil {
		return nil, fmt.Errorf("enable raw mode: %w", err)
	}
	defer func() {
		_ = term.Restore(fd, oldState)
		fmt.Fprint(out, "\r\n")
	}()

	cursor := 0
	render := func() {
		var buf strings.Builder
		// Clear screen area and move to top
		buf.WriteString("\r")
		if title != "" {
			buf.WriteString("\x1b[1m") // bold
			buf.WriteString(title)
			buf.WriteString("\x1b[0m\r\n")
		}
		for i, opt := range options {
			if i == cursor {
				buf.WriteString("\x1b[7m") // reverse video
				buf.WriteString(" > ")
			} else {
				buf.WriteString("   ")
			}
			buf.WriteString(opt.Label)
			if i == cursor {
				buf.WriteString("\x1b[0m")
			}
			buf.WriteString("\r\n")
		}
		// Move cursor back up to start for next render
		lines := len(options)
		if title != "" {
			lines++
		}
		buf.WriteString(fmt.Sprintf("\x1b[%dA", lines))
		fmt.Fprint(out, buf.String())
	}

	render()

	buf := make([]byte, 6)
	for {
		n, err := in.Read(buf)
		if err != nil {
			if err == io.EOF {
				return nil, nil
			}
			return nil, fmt.Errorf("read input: %w", err)
		}

		seq := buf[:n]
		switch {
		case isKey(seq, 3), isKey(seq, 27): // Ctrl+C or Escape
			// Clear the selector area
			lines := len(options)
			if title != "" {
				lines++
			}
			fmt.Fprint(out, strings.Repeat("\x1b[B", lines))        // move down
			fmt.Fprint(out, strings.Repeat("\x1b[A\x1b[2K", lines)) // clear lines
			return nil, nil
		case isKey(seq, 'q'), isKey(seq, 'Q'):
			lines := len(options)
			if title != "" {
				lines++
			}
			fmt.Fprint(out, strings.Repeat("\x1b[B", lines))
			fmt.Fprint(out, strings.Repeat("\x1b[A\x1b[2K", lines))
			return nil, nil
		case isEnter(seq):
			// Move cursor to end of list before returning
			lines := len(options)
			if title != "" {
				lines++
			}
			fmt.Fprint(out, strings.Repeat("\x1b[B", lines-cursor))
			fmt.Fprint(out, "\r\n")
			return &SelectResult{Index: cursor, Value: options[cursor].Value}, nil
		case isUpArrow(seq):
			if cursor > 0 {
				cursor--
			}
			render()
		case isDownArrow(seq):
			if cursor < len(options)-1 {
				cursor++
			}
			render()
		case isKey(seq, 'j'), isKey(seq, 'J'):
			if cursor < len(options)-1 {
				cursor++
			}
			render()
		case isKey(seq, 'k'), isKey(seq, 'K'):
			if cursor > 0 {
				cursor--
			}
			render()
		}
	}
}

func isKey(seq []byte, key byte) bool {
	return len(seq) == 1 && seq[0] == key
}

func isEnter(seq []byte) bool {
	return len(seq) == 1 && (seq[0] == '\r' || seq[0] == '\n')
}

func isUpArrow(seq []byte) bool {
	return len(seq) == 3 && seq[0] == 27 && seq[1] == '[' && seq[2] == 'A'
}

func isDownArrow(seq []byte) bool {
	return len(seq) == 3 && seq[0] == 27 && seq[1] == '[' && seq[2] == 'B'
}
