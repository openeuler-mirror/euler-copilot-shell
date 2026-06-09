package renderer

import (
	"os"
	"strings"

	"charm.land/glamour/v2"
	"charm.land/lipgloss/v2"
)

type markdownEngine interface {
	Render(in string) (string, error)
}

func newMarkdownEngine(theme string, noColor bool, width int, inputFile, outputFile *os.File) (markdownEngine, error) {
	style := resolveStyle(theme, noColor, inputFile, outputFile)
	return glamour.NewTermRenderer(
		glamour.WithStandardStyle(style),
		glamour.WithWordWrap(width),
	)
}

func resolveStyle(theme string, noColor bool, inputFile, outputFile *os.File) string {
	if noColor {
		return "notty"
	}

	normalized := strings.ToLower(strings.TrimSpace(theme))
	switch normalized {
	case "", "auto":
		if inputFile != nil && outputFile != nil && lipgloss.HasDarkBackground(inputFile, outputFile) {
			return "dark"
		}
		if inputFile != nil && outputFile != nil {
			return "light"
		}
		return "dark"
	default:
		return normalized
	}
}
