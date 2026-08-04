package shellbridge

import (
	"strconv"
	"strings"
)

// BashKeywordCase generates the case pattern for __witty_is_shell_keyword.
func BashKeywordCase(keywords []string) string {
	return bashLiteralCase(keywords)
}

// BashCommandCase generates the case pattern for __witty_is_shell_command.
func BashCommandCase(commands []string) string {
	return bashLiteralCase(commands)
}

func bashLiteralCase(values []string) string {
	parts := make([]string, len(values))
	for i, value := range values {
		parts[i] = `"` + value + `"`
	}
	return strings.Join(parts, " | ")
}

// BashNLPhraseCase generates the case pattern for __witty_has_nl_signal.
func BashNLPhraseCase(phrases []NLPhrase) string {
	parts := make([]string, len(phrases))
	for i, p := range phrases {
		if p.Prefix {
			parts[i] = `"` + p.Pattern + `"*`
		} else {
			parts[i] = `*` + p.Pattern + `*`
		}
	}
	return strings.Join(parts, " | ")
}

// BashCommandNLPhraseCase generates command-and-prefix patterns for
// __witty_has_command_nl_signal.
func BashCommandNLPhraseCase(phrases []CommandNLPhrase) string {
	parts := make([]string, len(phrases))
	for i, p := range phrases {
		command := `*:"`
		if p.Command != "" {
			command = `"` + p.Command + `:`
		}
		parts[i] = command + p.Pattern + `"*`
	}
	return strings.Join(parts, " | ")
}

// BashControlCase generates accepted command, subcommand, and word-count
// patterns for __witty_is_control.
func BashControlCase(rules []ControlRule) string {
	parts := make([]string, 0, len(rules))
	for _, rule := range rules {
		prefix := `"` + rule.Command + `:`
		switch {
		case rule.Subcommand != "":
			parts = append(parts, prefix+rule.Subcommand+`:`+strconv.Itoa(rule.MinWords)+`"`)
		case rule.MinWords == 1 && rule.MaxWords == 1:
			parts = append(parts, prefix+`:`+strconv.Itoa(rule.MinWords)+`"`)
		case rule.MinWords == 1 && rule.MaxWords == 0:
			parts = append(parts, prefix+`"*`)
		case rule.MinWords == 2 && rule.MaxWords == 0:
			parts = append(parts, prefix+`"?*":"*`)
		default:
			parts = append(parts, prefix+`?*:`+strconv.Itoa(rule.MinWords)+`"`)
		}
	}
	return strings.Join(parts, " | ")
}
