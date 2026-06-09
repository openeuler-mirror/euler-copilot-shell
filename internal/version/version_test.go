package version

import "testing"

func TestNew_UsesFallbacks(t *testing.T) {
	info := New("", "", "")

	if info.Version != "dev" {
		t.Fatalf("Version = %q, want dev", info.Version)
	}
	if info.Commit != "none" {
		t.Fatalf("Commit = %q, want none", info.Commit)
	}
	if info.Date != "unknown" {
		t.Fatalf("Date = %q, want unknown", info.Date)
	}
}

func TestInfoString_IncludesAllFields(t *testing.T) {
	got := New("1.2.3", "abc123", "2026-06-08").String()
	want := "version: 1.2.3\ncommit: abc123\ndate: 2026-06-08"
	if got != want {
		t.Fatalf("String() = %q, want %q", got, want)
	}
}
