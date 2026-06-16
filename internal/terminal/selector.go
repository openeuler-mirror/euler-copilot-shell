package terminal

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/mattn/go-runewidth"
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

	termWidth := Width(out)

	cursor := 0
	render := func() {
		var buf strings.Builder
		if title != "" {
			buf.WriteString("\x1b[G")  // move to column 1
			buf.WriteString("\x1b[1m") // bold
			buf.WriteString(title)
			buf.WriteString("\x1b[0m") // reset
			buf.WriteString("\x1b[K")  // clear to end of line
			buf.WriteString("\r\n")
		}
		for i, opt := range options {
			buf.WriteString("\x1b[G") // move to column 1
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
			buf.WriteString("\x1b[K") // clear to end of line
			buf.WriteString("\r\n")
		}
		// Move cursor back up to start for next render.
		// Count physical screen lines, accounting for line wrapping.
		totalLines := selectorScreenLines(title, options, termWidth)
		buf.WriteString(fmt.Sprintf("\x1b[%dA", totalLines))
		fmt.Fprint(out, buf.String())
	}

	// Initial render: clear from cursor to end of screen so stale prompt
	// content does not interfere with the selector display.
	fmt.Fprint(out, "\x1b[0J")
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
			clearSelectorLines(out, title, options, termWidth)
			return nil, nil
		case isKey(seq, 'q'), isKey(seq, 'Q'):
			clearSelectorLines(out, title, options, termWidth)
			return nil, nil
		case isEnter(seq):
			moveToSelectorEnd(out, title, options, cursor, termWidth)
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

// selectorScreenLines computes how many physical screen lines the selector
// occupies, accounting for line wrapping when termWidth is known.
func selectorScreenLines(title string, options []ListOption, termWidth int) int {
	total := 0
	if title != "" {
		total++
	}
	if termWidth <= 0 {
		return total + len(options)
	}
	for _, opt := range options {
		// +3 for the 3-char prefix (" > " or "   ")
		labelW := runewidth.StringWidth(opt.Label) + 3
		lines := (labelW + termWidth - 1) / termWidth
		if lines < 1 {
			lines = 1
		}
		total += lines
	}
	return total
}

// clearSelectorLines clears the area occupied by the selector.
func clearSelectorLines(out *os.File, title string, options []ListOption, termWidth int) {
	total := selectorScreenLines(title, options, termWidth)
	fmt.Fprint(out, strings.Repeat("\x1b[B", total))
	fmt.Fprint(out, strings.Repeat("\x1b[A\x1b[2K", total))
}

// moveToSelectorEnd moves the cursor past the selector display area.
func moveToSelectorEnd(out *os.File, title string, options []ListOption, cursor int, termWidth int) {
	totalLines := selectorScreenLines(title, options, termWidth)
	cursorLine := 0
	if title != "" {
		cursorLine++
	}
	for i := 0; i < cursor; i++ {
		labelW := runewidth.StringWidth(options[i].Label) + 3
		if termWidth > 0 {
			lines := (labelW + termWidth - 1) / termWidth
			if lines < 1 {
				lines = 1
			}
			cursorLine += lines
		} else {
			cursorLine++
		}
	}
	remaining := totalLines - cursorLine
	if remaining > 0 {
		fmt.Fprint(out, strings.Repeat("\x1b[B", remaining))
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
