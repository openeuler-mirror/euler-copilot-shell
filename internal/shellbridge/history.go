package shellbridge

import (
	"fmt"
	"strings"
)

// ShellQuote returns a single-quoted Bash literal for generated wrapper lines.
func ShellQuote(value string) string {
	return "'" + strings.ReplaceAll(value, "'", "'\"'\"'") + "'"
}

// WrapperLine returns the Bash wrapper line used for agent/control dispatch.
func WrapperLine(route Route, raw string) (string, bool) {
	switch route {
	case RouteAgent, RouteControl:
		return fmt.Sprintf("__witty_shell_dispatch %s -- %s", route, ShellQuote(raw)), true
	default:
		return "", false
	}
}
