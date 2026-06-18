package renderer

import (
	"strings"

	"github.com/mattn/go-runewidth"

	wittyterm "atomgit.com/openeuler/witty-cli/internal/terminal"
)

func init() {
	cjkCondition = runewidth.NewCondition()
	cjkCondition.EastAsianWidth = true
}

var cjkCondition *runewidth.Condition

type RowTracker struct {
	width     int
	cursorCol int
	rows      int
}

func NewRowTracker(width int) *RowTracker {
	if width <= 0 {
		width = wittyterm.DefaultWidth
	}
	return &RowTracker{width: width}
}

func (t *RowTracker) Reset() {
	t.cursorCol = 0
	t.rows = 0
}

func (t *RowTracker) Rows() int {
	return t.rows
}

func (t *RowTracker) Track(text string) {
	for _, r := range text {
		switch r {
		case '\n':
			t.rows++
			t.cursorCol = 0
		case '\r':
			t.cursorCol = 0
		default:
			w := runeWidth(r)
			t.cursorCol += w
			if t.cursorCol > t.width {
				t.rows++
				t.cursorCol = w
			}
		}
	}
}

func (t *RowTracker) SetWidth(width int) {
	if width <= 0 {
		width = wittyterm.DefaultWidth
	}
	t.width = width
}

func CountRows(text string, width int) int {
	if width <= 0 {
		width = wittyterm.DefaultWidth
	}
	tracker := NewRowTracker(width)
	tracker.Track(text)
	if tracker.cursorCol > 0 {
		tracker.rows++
	}
	return tracker.rows
}

func StripANSI(text string) string {
	var b strings.Builder
	b.Grow(len(text))
	inEscape := false
	for i := 0; i < len(text); i++ {
		c := text[i]
		if inEscape {
			if c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z' {
				inEscape = false
			}
			continue
		}
		if c == '\x1b' && i+1 < len(text) && text[i+1] == '[' {
			inEscape = true
			continue
		}
		b.WriteByte(c)
	}
	return b.String()
}

func runeWidth(r rune) int {
	w := cjkCondition.RuneWidth(r)
	if w < 1 {
		return 1
	}
	return w
}
