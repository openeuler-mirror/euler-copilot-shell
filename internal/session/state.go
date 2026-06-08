package session

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

const stateFileName = "state.json"

type state struct {
	CurrentByDirectory map[string]string `json:"current_by_directory"`
}

type stateStore struct {
	path string
}

func newStateStore(path string) *stateStore {
	return &stateStore{path: path}
}

func DefaultStatePath(lookupEnv func(string) (string, bool), userHomeDir func() (string, error)) (string, error) {
	if lookupEnv == nil {
		lookupEnv = os.LookupEnv
	}
	if value, ok := lookupEnv("WITTY_STATE_PATH"); ok && value != "" {
		return value, nil
	}
	if value, ok := lookupEnv("XDG_STATE_HOME"); ok && value != "" {
		return filepath.Join(value, "witty", stateFileName), nil
	}
	if userHomeDir == nil {
		userHomeDir = os.UserHomeDir
	}
	home, err := userHomeDir()
	if err != nil {
		return "", fmt.Errorf("resolve state path: %w", err)
	}
	if home == "" {
		return "", fmt.Errorf("resolve state path: home directory is empty")
	}
	return filepath.Join(home, ".local", "state", "witty", stateFileName), nil
}

func (s *stateStore) load() (state, error) {
	result := state{CurrentByDirectory: map[string]string{}}
	data, err := os.ReadFile(s.path)
	if err != nil {
		if os.IsNotExist(err) {
			return result, nil
		}
		return result, fmt.Errorf("load session state %q: %w", s.path, err)
	}
	if len(data) == 0 {
		return result, nil
	}
	if err := json.Unmarshal(data, &result); err != nil {
		return state{}, fmt.Errorf("decode session state %q: %w", s.path, err)
	}
	if result.CurrentByDirectory == nil {
		result.CurrentByDirectory = map[string]string{}
	}
	return result, nil
}

func (s *stateStore) save(value state) error {
	if value.CurrentByDirectory == nil {
		value.CurrentByDirectory = map[string]string{}
	}
	if err := os.MkdirAll(filepath.Dir(s.path), 0o700); err != nil {
		return fmt.Errorf("create session state dir: %w", err)
	}
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return fmt.Errorf("encode session state: %w", err)
	}
	data = append(data, '\n')
	if err := os.WriteFile(s.path, data, 0o600); err != nil {
		return fmt.Errorf("write session state %q: %w", s.path, err)
	}
	return nil
}
