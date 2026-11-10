package server

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"syscall"
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
	path     string
	lockPath string
}

func newStateStore(stateDir string) (*stateStore, error) {
	if stateDir == "" {
		return nil, fmt.Errorf("state directory is required")
	}
	if err := os.MkdirAll(stateDir, 0o700); err != nil {
		return nil, fmt.Errorf("create state directory %q: %w", stateDir, err)
	}
	return &stateStore{
		path:     filepath.Join(stateDir, stateFileName),
		lockPath: filepath.Join(stateDir, stateFileName+".lock"),
	}, nil
}

// withLock serializes read-modify-write sequences on the shared state file.
// Every witty process running as the same user uses the same state directory,
// so password creation and last_used updates must not interleave. The lock is
// advisory (flock) and is released automatically when the file is closed or
// the process exits, so a crashed process cannot leave a stale lock behind.
func (s *stateStore) withLock(fn func() error) error {
	f, err := os.OpenFile(s.lockPath, os.O_CREATE|os.O_RDWR, 0o600)
	if err != nil {
		return fmt.Errorf("open server state lock %q: %w", s.lockPath, err)
	}
	defer func() { _ = f.Close() }()

	for {
		err = syscall.Flock(int(f.Fd()), syscall.LOCK_EX)
		if err != syscall.EINTR {
			break
		}
	}
	if err != nil {
		return fmt.Errorf("lock server state %q: %w", s.lockPath, err)
	}
	defer func() { _ = syscall.Flock(int(f.Fd()), syscall.LOCK_UN) }()
	return fn()
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

	// Write-and-rename so concurrent readers never observe a truncated file.
	// Server state is shared by every witty process of the same user, and a
	// low-performance host with several concurrent users makes an interleaved
	// read of a partially written file much more likely.
	dir := filepath.Dir(s.path)
	tmp, err := os.CreateTemp(dir, ".server-state-*.tmp")
	if err != nil {
		return fmt.Errorf("create temporary server state in %q: %w", dir, err)
	}
	tmpName := tmp.Name()
	defer func() { _ = os.Remove(tmpName) }()

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return fmt.Errorf("write temporary server state %q: %w", tmpName, err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("close temporary server state %q: %w", tmpName, err)
	}
	if err := os.Rename(tmpName, s.path); err != nil {
		return fmt.Errorf("replace server state %q: %w", s.path, err)
	}
	return nil
}

func (s *stateStore) remove() error {
	if err := os.Remove(s.path); err != nil && !os.IsNotExist(err) {
		return fmt.Errorf("remove server state %q: %w", s.path, err)
	}
	return nil
}

// clearEndpoint drops a stale port/PID while preserving the password. Keeping
// the password across endpoint invalidation prevents concurrent witty
// processes from generating different passwords (and starting servers that
// reject each other) when a recorded port turns out to belong to another
// server or a dead process.
func (s *stateStore) clearEndpoint() error {
	return s.withLock(func() error {
		state, err := s.load()
		if err != nil {
			return err
		}
		state.Port = 0
		state.PID = 0
		state.StartedAt = time.Time{}
		return s.save(state)
	})
}
