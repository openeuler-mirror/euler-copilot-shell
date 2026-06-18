package renderer

import (
	"strings"
	"testing"
)

func TestRowTracker_SingleLine(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(80)
	tracker.Track("hello world\n")
	if tracker.Rows() != 1 {
		t.Fatalf("rows = %d, want 1", tracker.Rows())
	}
}

func TestRowTracker_MultipleLines(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(80)
	tracker.Track("line1\nline2\nline3\n")
	if tracker.Rows() != 3 {
		t.Fatalf("rows = %d, want 3", tracker.Rows())
	}
}

func TestRowTracker_Wrapping(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(10)
	tracker.Track("hello world")
	if tracker.Rows() != 1 {
		t.Fatalf("rows = %d, want 1 (wrap)", tracker.Rows())
	}
}

func TestRowTracker_CJKWidth(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(10)
	tracker.Track("你好你好你好")
	if tracker.Rows() != 1 {
		t.Fatalf("rows = %d, want 1 (CJK wrap)", tracker.Rows())
	}
	if tracker.cursorCol != 2 {
		t.Fatalf("cursorCol = %d, want 2 (last char on wrapped line)", tracker.cursorCol)
	}
}

func TestRowTracker_Reset(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(80)
	tracker.Track("hello\nworld\n")
	if tracker.Rows() != 2 {
		t.Fatalf("rows before reset = %d, want 2", tracker.Rows())
	}
	tracker.Reset()
	if tracker.Rows() != 0 {
		t.Fatalf("rows after reset = %d, want 0", tracker.Rows())
	}
}

func TestRowTracker_SetWidth(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(80)
	tracker.SetWidth(40)
	if tracker.width != 40 {
		t.Fatalf("width = %d, want 40", tracker.width)
	}
}

func TestCountRows(t *testing.T) {
	t.Parallel()

	tests := []struct {
		text  string
		width int
		want  int
	}{
		{"hello", 80, 1},
		{"hello\nworld\n", 80, 2},
		{"abcdefghij", 5, 2},
		{"你好你好", 4, 2},
		{"", 80, 0},
	}
	for _, tt := range tests {
		got := CountRows(tt.text, tt.width)
		if got != tt.want {
			t.Errorf("CountRows(%q, %d) = %d, want %d", tt.text, tt.width, got, tt.want)
		}
	}
}

func TestStripANSI(t *testing.T) {
	t.Parallel()

	tests := []struct {
		input string
		want  string
	}{
		{"hello", "hello"},
		{"\x1b[31mhello\x1b[0m", "hello"},
		{"\x1b[1;94m[step]\x1b[m started", "[step] started"},
		{"no ansi here", "no ansi here"},
		{"\x1b[2K", ""},
	}
	for _, tt := range tests {
		got := StripANSI(tt.input)
		if got != tt.want {
			t.Errorf("StripANSI(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
}

func TestRowTracker_ANSIIgnore(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(80)
	tracker.Track("\x1b[31mhello\x1b[0m world")
	if tracker.Rows() != 0 {
		t.Fatalf("rows = %d, want 0 (ANSI should not count)", tracker.Rows())
	}
}

func TestRowTracker_EmojiWidth(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(80)
	tracker.Track("🎉")
	if tracker.cursorCol < 1 {
		t.Fatalf("cursorCol = %d, want >= 1 for emoji", tracker.cursorCol)
	}
}

func TestRowTracker_LongCJKWrapping(t *testing.T) {
	t.Parallel()

	tracker := NewRowTracker(10)
	text := strings.Repeat("你", 10)
	tracker.Track(text)
	if tracker.Rows() != 1 {
		t.Fatalf("rows = %d, want 1 (10 CJK chars at width 10 wraps once)", tracker.Rows())
	}
}
