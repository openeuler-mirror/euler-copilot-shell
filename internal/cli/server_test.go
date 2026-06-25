package cli

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/spf13/cobra"

	"atomgit.com/openeuler/euler-copilot-shell/internal/app"
	"atomgit.com/openeuler/euler-copilot-shell/internal/server"
	"atomgit.com/openeuler/euler-copilot-shell/internal/version"
)

// fakeServerManager is a test double for server.Manager.
type fakeServerManager struct {
	status server.Status
	stopFn func() error
}

func (f *fakeServerManager) Ensure(context.Context) (server.Connection, error) {
	return server.Connection{}, nil
}

func (f *fakeServerManager) Stop(context.Context) error {
	if f.stopFn != nil {
		return f.stopFn()
	}
	return nil
}

func (f *fakeServerManager) Status(context.Context) server.Status {
	return f.status
}

func (f *fakeServerManager) TouchLastUsed() {}

func (f *fakeServerManager) Close() {}

func TestServerStatusCommand_ManagedServer(t *testing.T) {
	var out, errOut bytes.Buffer
	mgr := &fakeServerManager{
		status: server.Status{
			Running:   true,
			Port:      4097,
			PID:       12345,
			Managed:   true,
			StartedAt: "2026-06-25T10:30:00+08:00",
		},
	}
	fake := &fakeContainer{serverMgr: mgr}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"server", "status"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server status) error = %v", err)
	}

	got := out.String()
	for _, want := range []string{
		"Running:    yes",
		"Port:       4097",
		"PID:        12345",
		"Managed:    yes",
		"StartedAt:  2026-06-25T10:30:00+08:00",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("server status output missing %q\ngot: %s", want, got)
		}
	}
}

func TestServerStatusCommand_NotRunning(t *testing.T) {
	var out, errOut bytes.Buffer
	mgr := &fakeServerManager{
		status: server.Status{
			Running:   false,
			Port:      0,
			PID:       0,
			Managed:   false,
			StartedAt: "",
		},
	}
	fake := &fakeContainer{serverMgr: mgr}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"server", "status"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server status) error = %v", err)
	}

	got := out.String()
	for _, want := range []string{"Running:    no", "Managed:    no"} {
		if !strings.Contains(got, want) {
			t.Errorf("server status output missing %q\ngot: %s", want, got)
		}
	}
}

func TestServerStatusCommand_NoServerManager(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{serverMgr: nil}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"server", "status"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server status) error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "not available") {
		t.Errorf("expected 'not available' message, got: %s", got)
	}
}

func TestServerStopCommand_ManagedServer(t *testing.T) {
	var out, errOut bytes.Buffer
	stopped := false
	mgr := &fakeServerManager{
		status: server.Status{Running: true, Managed: true},
		stopFn: func() error {
			stopped = true
			return nil
		},
	}
	fake := &fakeContainer{serverMgr: mgr}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"server", "stop"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server stop) error = %v", err)
	}

	if !stopped {
		t.Fatal("server was not stopped")
	}

	got := out.String()
	if !strings.Contains(got, "Server stopped.") {
		t.Errorf("expected 'Server stopped.', got: %s", got)
	}
}

func TestServerStopCommand_NonManagedServer(t *testing.T) {
	var out, errOut bytes.Buffer
	stopped := false
	// After P4-6e, `server stop` no longer refuses non-managed servers: it
	// reads the state file and disposes the server cross-process. The command
	// calls Stop directly without a managed-only precondition.
	mgr := &fakeServerManager{
		status: server.Status{Running: true, Managed: false},
		stopFn: func() error {
			stopped = true
			return nil
		},
	}
	fake := &fakeContainer{serverMgr: mgr}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"server", "stop"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server stop) error = %v", err)
	}

	if !stopped {
		t.Fatal("expected Stop to be called for non-managed server")
	}

	got := out.String()
	if !strings.Contains(got, "Server stopped.") {
		t.Errorf("expected 'Server stopped.', got: %s", got)
	}
}

func TestServerStopCommand_NoServerManager(t *testing.T) {
	var out, errOut bytes.Buffer
	fake := &fakeContainer{serverMgr: nil}
	cmd := newRootCommandWithOptions(&rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
		loadAppFn: func(context.Context, *cobra.Command) (app.Container, error) {
			return fake, nil
		},
	})
	cmd.SetArgs([]string{"server", "stop"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server stop) error = %v", err)
	}

	got := out.String()
	if !strings.Contains(got, "not available") {
		t.Errorf("expected 'not available' message, got: %s", got)
	}
}

func TestServerCommand_Help(t *testing.T) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{version: version.New("dev", "none", "unknown"), stdout: &out, stderr: &errOut}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"server", "--help"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server --help) error = %v", err)
	}

	got := out.String()
	for _, want := range []string{"status", "stop", "Manage opencode server lifecycle"} {
		if !strings.Contains(got, want) {
			t.Errorf("server help output missing %q\ngot: %s", want, got)
		}
	}
}

// TestServerStatusCommand_SkipsEnsure verifies that `server status` sets
// skipServerEnsure so loadApp does not call Ensure() (no server-start side effect).
func TestServerStatusCommand_SkipsEnsure(t *testing.T) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
	}
	var sawSkipEnsure bool
	opts.loadAppFn = func(_ context.Context, _ *cobra.Command) (app.Container, error) {
		sawSkipEnsure = opts.skipServerEnsure
		return &fakeContainer{serverMgr: &fakeServerManager{}}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"server", "status"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server status) error = %v", err)
	}
	if !sawSkipEnsure {
		t.Fatal("server status did not set skipServerEnsure=true before loadApp")
	}
}

// TestServerStopCommand_SkipsEnsure verifies that `server stop` sets
// skipServerEnsure so loadApp does not call Ensure() (no server-start side effect).
func TestServerStopCommand_SkipsEnsure(t *testing.T) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
	}
	var sawSkipEnsure bool
	opts.loadAppFn = func(_ context.Context, _ *cobra.Command) (app.Container, error) {
		sawSkipEnsure = opts.skipServerEnsure
		return &fakeContainer{serverMgr: &fakeServerManager{stopFn: func() error { return nil }}}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"server", "stop"})

	if err := cmd.ExecuteContext(context.Background()); err != nil {
		t.Fatalf("Execute(server stop) error = %v", err)
	}
	if !sawSkipEnsure {
		t.Fatal("server stop did not set skipServerEnsure=true before loadApp")
	}
}

// TestAskCommand_DoesNotSkipEnsure verifies that normal commands like `ask`
// do not set skipServerEnsure (Ensure is called as usual).
func TestAskCommand_DoesNotSkipEnsure(t *testing.T) {
	var out, errOut bytes.Buffer
	opts := &rootOptions{
		version: version.New("dev", "none", "unknown"),
		stdout:  &out,
		stderr:  &errOut,
	}
	var sawSkipEnsure = true // expect false for ask
	opts.loadAppFn = func(_ context.Context, _ *cobra.Command) (app.Container, error) {
		sawSkipEnsure = opts.skipServerEnsure
		return &fakeContainer{}, nil
	}
	cmd := newRootCommandWithOptions(opts)
	cmd.SetArgs([]string{"ask", "hello"})

	_ = cmd.ExecuteContext(context.Background())
	if sawSkipEnsure {
		t.Fatal("ask command set skipServerEnsure=true, want false")
	}
}
