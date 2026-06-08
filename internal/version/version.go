package version

import "fmt"

const (
	defaultVersion = "dev"
	defaultCommit  = "none"
	defaultDate    = "unknown"
)

// Info describes the build metadata shown to users and injected by release builds.
type Info struct {
	Version string
	Commit  string
	Date    string
}

// New returns build metadata with development fallbacks for local builds.
func New(version, commit, date string) Info {
	info := Info{Version: version, Commit: commit, Date: date}
	if info.Version == "" {
		info.Version = defaultVersion
	}
	if info.Commit == "" {
		info.Commit = defaultCommit
	}
	if info.Date == "" {
		info.Date = defaultDate
	}
	return info
}

func (i Info) String() string {
	return fmt.Sprintf("version: %s\ncommit: %s\ndate: %s", i.Version, i.Commit, i.Date)
}
