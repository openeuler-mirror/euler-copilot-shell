package server

import (
	"fmt"
	"os"
	"testing"
	"time"
)

func TestStateStore_SaveNeverExposesPartialFile(t *testing.T) {
	store, err := newStateStore(t.TempDir())
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}
	if err := store.save(State{Port: 1, Password: "initial"}); err != nil {
		t.Fatalf("initial save() error = %v", err)
	}

	done := make(chan struct{})
	readErr := make(chan error, 1)
	go func() {
		for {
			select {
			case <-done:
				return
			default:
			}
			state, err := store.load()
			if err != nil {
				select {
				case readErr <- err:
				default:
				}
				return
			}
			if state.Port == 0 {
				select {
				case readErr <- fmt.Errorf("read an empty or truncated state file"):
				default:
				}
				return
			}
		}
	}()

	for i := 2; i < 500; i++ {
		if err := store.save(State{Port: i, Password: "p"}); err != nil {
			close(done)
			t.Fatalf("save() error = %v", err)
		}
	}
	close(done)

	select {
	case err := <-readErr:
		t.Fatalf("concurrent load observed a partial state: %v", err)
	default:
	}
}

func TestStateStore_ClearEndpointKeepsPassword(t *testing.T) {
	store, err := newStateStore(t.TempDir())
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}
	if err := store.save(State{Port: 4096, Password: "keep-me", PID: 123, StartedAt: time.Now()}); err != nil {
		t.Fatalf("save() error = %v", err)
	}
	if err := store.clearEndpoint(); err != nil {
		t.Fatalf("clearEndpoint() error = %v", err)
	}
	state, err := store.load()
	if err != nil {
		t.Fatalf("load() error = %v", err)
	}
	if state.Port != 0 || state.PID != 0 {
		t.Fatalf("endpoint = %d/%d, want 0/0", state.Port, state.PID)
	}
	if state.Password != "keep-me" {
		t.Fatalf("password = %q, want keep-me", state.Password)
	}
	if !state.StartedAt.IsZero() {
		t.Fatalf("StartedAt = %v, want zero", state.StartedAt)
	}
}

func TestStateStore_SaveLeavesNoTempFile(t *testing.T) {
	dir := t.TempDir()
	store, err := newStateStore(dir)
	if err != nil {
		t.Fatalf("newStateStore() error = %v", err)
	}
	if err := store.save(State{Port: 4096, Password: "p"}); err != nil {
		t.Fatalf("save() error = %v", err)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}
	for _, entry := range entries {
		if entry.Name() != stateFileName && entry.Name() != stateFileName+".lock" {
			t.Fatalf("unexpected file left in state dir: %q", entry.Name())
		}
	}
}
