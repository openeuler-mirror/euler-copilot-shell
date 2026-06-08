package transport

import "fmt"

const maxResponseSummaryBytes = 4096

type HTTPError struct {
	StatusCode int
	Endpoint   string
	Summary    string
}

func (e *HTTPError) Error() string {
	if e.Summary == "" {
		return fmt.Sprintf("http %s: status %d", e.Endpoint, e.StatusCode)
	}
	return fmt.Sprintf("http %s: status %d: %s", e.Endpoint, e.StatusCode, e.Summary)
}
