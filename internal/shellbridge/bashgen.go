package shellbridge

import "strings"

var bashReserved = map[string]bool{
	"if": true, "then": true, "else": true, "elif": true, "fi": true,
	"for": true, "while": true, "until": true, "do": true, "done": true,
	"case": true, "esac": true, "in": true, "function": true,
	"time": true, "coproc": true, "select": true,
}

func needsBashQuote(word string) bool {
	return bashReserved[word] || word == "."
}

// BashKeywordCase generates the case pattern for __witty_is_shell_keyword.
func BashKeywordCase(keywords []string) string {
	parts := make([]string, len(keywords))
	for i, kw := range keywords {
		if needsBashQuote(kw) {
			parts[i] = `"` + kw + `"`
		} else {
			parts[i] = kw
		}
	}
	return strings.Join(parts, " | ")
}

// BashCommandCase generates the case pattern for __witty_is_shell_command.
func BashCommandCase(commands []string) string {
	parts := make([]string, len(commands))
	for i, c := range commands {
		if needsBashQuote(c) {
			parts[i] = `"` + c + `"`
		} else {
			parts[i] = c
		}
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
