package server

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"
)

const stateFileName = "server-state.json"

// State is the persistent server state written to disk.
type State struct {
	Port      int       `json:"port"`
	Password  string    `json:"password"`
	PID       int       `json:"pid"`
	StartedAt time.Time `json:"started_at"`
	LastUsed  time.Time `json:"last_used"`
}

type stateStore struct {
	path string
}

func newStateStore(stateDir string) (*stateStore, error) {
	if stateDir == "" {
		return nil, fmt.Errorf("state directory is required")
	}
	if err := os.MkdirAll(stateDir, 0o700); err != nil {
		return nil, fmt.Errorf("create state directory %q: %w", stateDir, err)
	}
	return &stateStore{path: filepath.Join(stateDir, stateFileName)}, nil
}

// DefaultServerStateDir resolves the directory for server state files.
// WITTY_STATE_PATH is treated as a full file path (consistent with
// session.DefaultStatePath); the server state file (server-state.json) is
// placed in the same directory. When WITTY_STATE_PATH is unset, the directory
// falls back to $XDG_STATE_HOME/witty or ~/.local/state/witty.
func DefaultServerStateDir(lookupEnv func(string) (string, bool), userHomeDir func() (string, error)) (string, error) {
	if lookupEnv == nil {
		lookupEnv = os.LookupEnv
	}
	// WITTY_STATE_PATH is a full file path (matching session.DefaultStatePath);
	// the server state file lives in the same directory.
	if value, ok := lookupEnv("WITTY_STATE_PATH"); ok && value != "" {
		return filepath.Dir(value), nil
	}
	if value, ok := lookupEnv("XDG_STATE_HOME"); ok && value != "" {
		return filepath.Join(value, "witty"), nil
	}
	if userHomeDir == nil {
		userHomeDir = os.UserHomeDir
	}
	home, err := userHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve server state dir: %w", err)
	}
	if home == "" {
		return "", fmt.Errorf("resolve server state dir: home directory is empty")
	}
	return filepath.Join(home, ".local", "state", "witty"), nil
}

func (s *stateStore) load() (State, error) {
	var result State
	data, err := os.ReadFile(s.path)
	if err != nil {
		if os.IsNotExist(err) {
			return result, nil
		}
		return result, fmt.Errorf("load server state %q: %w", s.path, err)
	}
	if len(data) == 0 {
		return result, nil
	}
	if err := json.Unmarshal(data, &result); err != nil {
		return State{}, fmt.Errorf("decode server state %q: %w", s.path, err)
	}
	return result, nil
}

func (s *stateStore) save(value State) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return fmt.Errorf("encode server state: %w", err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(s.path, data, 0o600); err != nil {
		return fmt.Errorf("write server state %q: %w", s.path, err)
	}
	return nil
}

func (s *stateStore) remove() error {
	if err := os.Remove(s.path); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("remove server state %q: %w", s.path, err)
	}
	return nil
}
