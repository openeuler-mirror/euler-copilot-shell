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

// IPCServer listens on a Unix domain socket for witty CLI processes to
// report activity (TOUCH) and query server status.
type IPCServer struct {
	monitor    *Monitor
	socketPath string
	logger     *slog.Logger
	mu         sync.Mutex
	listener   net.Listener
}

// IPCOptions configures the IPC server.
type IPCOptions struct {
	SocketPath string
	Logger     *slog.Logger
}

// NewIPCServer creates an IPC server.
func NewIPCServer(monitor *Monitor, opts IPCOptions) *IPCServer {
	logger := opts.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &IPCServer{
		monitor:    monitor,
		socketPath: opts.SocketPath,
		logger:     logger,
	}
}

type request struct {
	Method string `json:"method"`
	Port   int    `json:"port,omitempty"`
}

type statusItem struct {
	Port int `json:"port"`
	PID  int `json:"pid"`
}

type response struct {
	OK    bool   `json:"ok"`
	Data  any    `json:"data,omitempty"`
	Error string `json:"error,omitempty"`
}

// Listen starts accepting connections. Blocks until ctx is cancelled.
func (s *IPCServer) Listen(ctx context.Context) error {
	_ = os.Remove(s.socketPath)

	dir := filepath.Dir(s.socketPath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("create socket dir %s: %w", dir, err)
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
			_ = s.listener.Close()
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
		go s.handle(conn)
	}
}

func (s *IPCServer) handle(conn net.Conn) {
	defer func() { _ = conn.Close() }()
	scanner := bufio.NewScanner(conn)
	for scanner.Scan() {
		var req request
		if err := json.Unmarshal(scanner.Bytes(), &req); err != nil {
			s.reply(conn, response{OK: false, Error: "invalid json: " + err.Error()})
			continue
		}
		s.reply(conn, s.dispatch(req))
	}
	if err := scanner.Err(); err != nil {
		s.logger.Warn("IPC scanner error", "error", err)
	}
}

func (s *IPCServer) dispatch(req request) response {
	switch req.Method {
	case "PING":
		return response{OK: true}

	case "TOUCH":
		if req.Port == 0 {
			return response{OK: false, Error: "TOUCH requires port"}
		}
		s.monitor.Touch(req.Port)
		return response{OK: true}

	case "SERVERS":
		all := s.monitor.All()
		items := make([]statusItem, len(all))
		for i, srv := range all {
			items[i] = statusItem{Port: srv.Port, PID: srv.PID}
		}
		return response{OK: true, Data: items}

	default:
		return response{OK: false, Error: "unknown method: " + req.Method}
	}
}

func (s *IPCServer) reply(conn net.Conn, resp response) {
	data, _ := json.Marshal(resp)
	data = append(data, '\n')
	_, _ = conn.Write(data)
}
