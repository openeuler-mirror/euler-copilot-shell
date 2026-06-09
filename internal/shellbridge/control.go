package shellbridge

import (
	"fmt"
	"strings"
)

// ControlKind identifies a supported slash control command.
type ControlKind string

const (
	ControlAsk             ControlKind = "ask"
	ControlAgent           ControlKind = "agent"
	ControlModel           ControlKind = "model"
	ControlSessionList     ControlKind = "session_list"
	ControlSessionContinue ControlKind = "session_continue"
	ControlNew             ControlKind = "new"
	ControlHelp            ControlKind = "help"
)

// ControlAction is the normalized form of a whitelisted slash command.
type ControlAction struct {
	Kind      ControlKind
	Raw       string
	Prompt    string
	Value     string
	SessionID string
}

// ParseControl parses slash commands that the shell adapter is allowed to dispatch.
func ParseControl(raw string) (ControlAction, error) {
	line := strings.TrimSpace(raw)
	if line == "" {
		return ControlAction{}, fmt.Errorf("shell control command is required")
	}
	fields := strings.Fields(line)
	if len(fields) == 0 {
		return ControlAction{}, fmt.Errorf("shell control command is required")
	}

	switch fields[0] {
	case "/ask":
		prompt := strings.TrimSpace(strings.TrimPrefix(line, "/ask"))
		if prompt == "" {
			return ControlAction{}, fmt.Errorf("/ask requires a prompt")
		}
		return ControlAction{Kind: ControlAsk, Raw: line, Prompt: prompt}, nil
	case "/agent":
		return ControlAction{Kind: ControlAgent, Raw: line, Value: strings.TrimSpace(strings.TrimPrefix(line, "/agent"))}, nil
	case "/model":
		return ControlAction{Kind: ControlModel, Raw: line, Value: strings.TrimSpace(strings.TrimPrefix(line, "/model"))}, nil
	case "/new":
		if len(fields) != 1 {
			return ControlAction{}, fmt.Errorf("/new does not accept arguments")
		}
		return ControlAction{Kind: ControlNew, Raw: line}, nil
	case "/help":
		if len(fields) != 1 {
			return ControlAction{}, fmt.Errorf("/help does not accept arguments")
		}
		return ControlAction{Kind: ControlHelp, Raw: line}, nil
	case "/session":
		return parseSessionControl(line, fields)
	default:
		return ControlAction{}, fmt.Errorf("unsupported shell control command %q", fields[0])
	}
}

func parseSessionControl(line string, fields []string) (ControlAction, error) {
	if len(fields) < 2 {
		return ControlAction{}, fmt.Errorf("/session requires a subcommand")
	}
	switch fields[1] {
	case "list":
		if len(fields) != 2 {
			return ControlAction{}, fmt.Errorf("/session list does not accept arguments")
		}
		return ControlAction{Kind: ControlSessionList, Raw: line}, nil
	case "continue":
		if len(fields) != 3 {
			return ControlAction{}, fmt.Errorf("/session continue requires exactly one session id")
		}
		return ControlAction{Kind: ControlSessionContinue, Raw: line, SessionID: fields[2]}, nil
	default:
		return ControlAction{}, fmt.Errorf("unsupported /session subcommand %q", fields[1])
	}
}

// HelpText returns the shell adapter slash command help shown by shell-control.
func HelpText() string {
	return strings.TrimSpace(`Witty shell controls:
  /ask <prompt>              Ask opencode explicitly
  /agent [name]              Show or set the default agent for future phases
  /model [provider/model]    Show or set the default model for future phases
  /session list              List opencode sessions
  /session continue <id>     Continue a session by id
  /new                       Start a fresh ask on the next prompt
  /help                      Show this help`)
}
