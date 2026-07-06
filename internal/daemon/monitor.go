// Package daemon implements the wittyd background service that monitors all
// opencode server processes on the system, enforces per-server idle timeout,
// and handles configuration-triggered server restarts.
package daemon

import (
	"fmt"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"
)

// serverRecord tracks activity for a monitored server.
type serverRecord struct {
	info     ServerInfo
	lastUsed time.Time
}

// ServerInfo describes a discovered opencode server process.
type ServerInfo struct {
	PID      int
	Port     int
	Password string // from /proc/<pid>/environ, empty if unknown
}

// Monitor discovers and tracks opencode server processes on the system.
type Monitor struct {
	mu      sync.Mutex
	servers map[int]*serverRecord // keyed by port
}

// NewMonitor creates a Monitor.
func NewMonitor() *Monitor {
	return &Monitor{servers: make(map[int]*serverRecord)}
}

// Discover finds all opencode server processes by scanning /proc for
// processes whose cmdline contains "opencode serve".
func (m *Monitor) Discover() {
	m.mu.Lock()
	defer m.mu.Unlock()

	entries, err := os.ReadDir("/proc")
	if err != nil {
		return
	}

	seen := make(map[int]bool)

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		pid, err := strconv.Atoi(entry.Name())
		if err != nil {
			continue
		}
		data, err := os.ReadFile(fmt.Sprintf("/proc/%d/cmdline", pid))
		if err != nil {
			continue
		}
		cmdline := strings.ReplaceAll(string(data), "\x00", " ")
		if !strings.Contains(cmdline, "opencode serve") {
			continue
		}
		port := extractPort(cmdline)
		if port == 0 {
			continue
		}
		seen[port] = true
		if rec, ok := m.servers[port]; ok {
			rec.info.PID = pid
			// Refresh password in case it changed.
			if pw := readPassword(pid); pw != "" {
				rec.info.Password = pw
			}
		} else {
			m.servers[port] = &serverRecord{
				info: ServerInfo{PID: pid, Port: port, Password: readPassword(pid)},
			}
		}
	}

	// Remove servers that disappeared.
	for port := range m.servers {
		if !seen[port] {
			delete(m.servers, port)
		}
	}
}

// Touch records activity for a server. The witty CLI transport layer calls
// this via IPC after each successful HTTP request.
func (m *Monitor) Touch(port int) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if rec, ok := m.servers[port]; ok {
		rec.lastUsed = time.Now()
	}
}

// IdleServers returns servers idle longer than timeout. Servers never
// touched (unknown idle status) are excluded.
func (m *Monitor) IdleServers(timeout time.Duration) []ServerInfo {
	m.mu.Lock()
	defer m.mu.Unlock()

	var result []ServerInfo
	now := time.Now()
	for _, rec := range m.servers {
		if rec.lastUsed.IsZero() {
			continue
		}
		if now.Sub(rec.lastUsed) > timeout {
			result = append(result, rec.info)
		}
	}
	return result
}

// All returns all tracked servers.
func (m *Monitor) All() []ServerInfo {
	m.mu.Lock()
	defer m.mu.Unlock()

	result := make([]ServerInfo, 0, len(m.servers))
	for _, rec := range m.servers {
		result = append(result, rec.info)
	}
	return result
}

// extractPort parses --port N from an opencode cmdline.
func extractPort(cmdline string) int {
	idx := strings.Index(cmdline, "--port ")
	if idx < 0 {
		return 0
	}
	rest := cmdline[idx+len("--port "):]
	fields := strings.Fields(rest)
	if len(fields) == 0 {
		return 0
	}
	port, _ := strconv.Atoi(fields[0])
	return port
}

// readPassword reads the OPENCODE_SERVER_PASSWORD from the process
// environment of the given PID. The password is set by witty's server
// manager when spawning the opencode process.
func readPassword(pid int) string {
	data, err := os.ReadFile(fmt.Sprintf("/proc/%d/environ", pid))
	if err != nil {
		return ""
	}
	for _, entry := range strings.Split(string(data), "\x00") {
		if after, ok := strings.CutPrefix(entry, "OPENCODE_SERVER_PASSWORD="); ok {
			return after
		}
	}
	return ""
}
