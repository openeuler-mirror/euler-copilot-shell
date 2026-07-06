package daemon

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"os"
	"path/filepath"
	"sync"
)

// IPCServer listens on a Unix domain socket and serves requests from the
// witty CLI for server status, lifecycle, and touch operations.
type IPCServer struct {
	supervisor *Supervisor
	socketPath string
	logger     *slog.Logger
	mu         sync.Mutex
	listener   net.Listener
}

// IPCOptions configures the IPC server.
type IPCOptions struct {
	// SocketPath is the path to the Unix domain socket.
	SocketPath string
	// Logger receives operational messages.
	Logger *slog.Logger
}

// NewIPCServer creates an IPC server.
func NewIPCServer(supervisor *Supervisor, opts IPCOptions) *IPCServer {
	logger := opts.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &IPCServer{
		supervisor: supervisor,
		socketPath: opts.SocketPath,
		logger:     logger,
	}
}

// request is an incoming IPC message.
type request struct {
	Method string `json:"method"`
}

// statusResponse is the data payload for a STATUS response.
type statusResponse struct {
	Running   bool   `json:"running"`
	Port      int    `json:"port"`
	PID       int    `json:"pid"`
	StartedAt string `json:"started_at"`
}

// restartResponse is the data payload for a RESTART response.
type restartResponse struct {
	URL  string `json:"url"`
	Port int    `json:"port"`
}

// response is the envelope for all IPC responses.
type response struct {
	OK    bool   `json:"ok"`
	Data  any    `json:"data,omitempty"`
	Error string `json:"error,omitempty"`
}

// Listen starts accepting connections on the Unix socket. It blocks until
// ctx is cancelled.
func (s *IPCServer) Listen(ctx context.Context) error {
	// Remove stale socket file.
	_ = os.Remove(s.socketPath)

	dir := filepath.Dir(s.socketPath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create socket directory %s: %w", dir, err)
	}

	lc := net.ListenConfig{}
	ln, err := lc.Listen(ctx, "unix", s.socketPath)
	if err != nil {
		return fmt.Errorf("listen on %s: %w", s.socketPath, err)
	}

	s.mu.Lock()
	s.listener = ln
	s.mu.Unlock()

	s.logger.Info("IPC server listening", "socket", s.socketPath)

	go func() {
		<-ctx.Done()
		s.mu.Lock()
		if s.listener != nil {
			s.listener.Close()
		}
		s.mu.Unlock()
	}()

	for {
		conn, err := ln.Accept()
		if err != nil {
			select {
			case <-ctx.Done():
				return nil
			default:
				return fmt.Errorf("accept: %w", err)
			}
		}
		go s.handleConn(conn)
	}
}

func (s *IPCServer) handleConn(conn net.Conn) {
	defer conn.Close()
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		line := scanner.Bytes()
		var req request
		if err := json.Unmarshal(line, &req); err != nil {
			s.writeResponse(conn, response{OK: false, Error: "invalid json: " + err.Error()})
			continue
		}
		s.writeResponse(conn, s.dispatch(req))
	}
}

func (s *IPCServer) dispatch(req request) response {
	switch req.Method {
	case "PING":
		return response{OK: true}

	case "TOUCH":
		s.supervisor.TouchLastUsed()
		return response{OK: true}

	case "STOP":
		if err := s.supervisor.Stop(context.Background()); err != nil {
			return response{OK: false, Error: err.Error()}
		}
		return response{OK: true}

	case "RESTART":
		conn, err := s.supervisor.Restart(context.Background())
		if err != nil {
			return response{OK: false, Error: err.Error()}
		}
		return response{OK: true, Data: restartResponse{
			URL:  conn.URL,
			Port: extractPort(conn.URL),
		}}

	case "STATUS":
		st := s.supervisor.Status(context.Background())
		return response{OK: true, Data: statusResponse{
			Running:   st.Running,
			Port:      st.Port,
			PID:       st.PID,
			StartedAt: st.StartedAt,
		}}

	default:
		return response{OK: false, Error: "unknown method: " + req.Method}
	}
}

func (s *IPCServer) writeResponse(conn net.Conn, resp response) {
	data, err := json.Marshal(resp)
	if err != nil {
		return
	}
	data = append(data, '\n')
	_, _ = conn.Write(data)
}

// extractPort parses the port number from a URL like "http://127.0.0.1:4099".
func extractPort(url string) int {
	for i := len(url) - 1; i >= 0; i-- {
		if url[i] == ':' {
			var port int
			fmt.Sscanf(url[i+1:], "%d", &port)
			return port
		}
	}
	return 0
}
