package transport

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const sseBufferSize = 32 * 1024

type SSEEvent struct {
	ID    string
	Type  string
	Data  string
	Retry time.Duration
}

type sseEnvelope struct {
	ID         string          `json:"id"`
	Type       string          `json:"type"`
	Properties json.RawMessage `json:"properties"`
}

func ParseStream(ctx context.Context, r io.Reader, out chan<- SSEEvent) error {
	reader := bufio.NewReaderSize(r, sseBufferSize)
	state := sseState{}

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		default:
		}

		line, err := reader.ReadString('\n')
		if err != nil && !(err == io.EOF && line != "") {
			if err == io.EOF {
				return state.dispatch(ctx, out)
			}
			return fmt.Errorf("read sse: %w", err)
		}

		if err := state.processLine(ctx, strings.TrimRight(line, "\r\n"), out); err != nil {
			return err
		}
		if err == io.EOF {
			return state.dispatch(ctx, out)
		}
	}
}

type sseState struct {
	id        string
	eventType string
	dataLines []string
	retry     time.Duration
}

func (s *sseState) processLine(ctx context.Context, line string, out chan<- SSEEvent) error {
	if line == "" {
		return s.dispatch(ctx, out)
	}
	if strings.HasPrefix(line, ":") {
		return nil
	}

	field, value, ok := strings.Cut(line, ":")
	if !ok {
		field = line
		value = ""
	} else if strings.HasPrefix(value, " ") {
		value = value[1:]
	}

	switch field {
	case "event":
		s.eventType = value
	case "data":
		s.dataLines = append(s.dataLines, value)
	case "id":
		s.id = value
	case "retry":
		retryMs, err := strconv.Atoi(value)
		if err == nil && retryMs >= 0 {
			s.retry = time.Duration(retryMs) * time.Millisecond
		}
	}
	return nil
}

func (s *sseState) dispatch(ctx context.Context, out chan<- SSEEvent) error {
	if len(s.dataLines) == 0 {
		s.eventType = ""
		return nil
	}
	evt := SSEEvent{
		ID:    s.id,
		Type:  s.eventType,
		Data:  strings.Join(s.dataLines, "\n"),
		Retry: s.retry,
	}
	s.eventType = ""
	s.dataLines = s.dataLines[:0]

	select {
	case <-ctx.Done():
		return ctx.Err()
	case out <- evt:
		return nil
	}
}

func newSSEHTTPClient(connectTimeout time.Duration) *http.Client {
	if connectTimeout <= 0 {
		connectTimeout = DefaultTimeout
	}
	return &http.Client{Transport: &http.Transport{
		DialContext: (&net.Dialer{
			Timeout:   connectTimeout,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		TLSHandshakeTimeout: connectTimeout,
	}}
}

func (c *client) SubscribeEvents(ctx context.Context, filter EventFilter) (<-chan RawEvent, <-chan error) {
	events := make(chan RawEvent, 64)
	errs := make(chan error, 1)

	body, err := c.openEventStream(ctx, filter)
	if err != nil {
		close(events)
		errs <- err
		close(errs)
		return events, errs
	}

	go func() {
		defer close(events)
		defer close(errs)
		if err := c.streamEvents(ctx, body, events); err != nil && ctx.Err() == nil {
			errs <- err
		}
	}()
	return events, errs
}

func (c *client) openEventStream(ctx context.Context, filter EventFilter) (io.ReadCloser, error) {
	query := url.Values{}
	addString(query, "directory", filter.Directory)
	addString(query, "workspace", filter.Workspace)
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.endpointURL("/event", query), nil)
	if err != nil {
		return nil, fmt.Errorf("build sse request: %w", err)
	}
	req.Header.Set("Accept", "text/event-stream")
	req.Header.Set("Cache-Control", "no-cache")
	req.Header.Set("Connection", "keep-alive")
	req.Header.Set("User-Agent", c.userAgent)

	resp, err := c.sseClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("sse connect: %w", err)
	}
	if resp.StatusCode != http.StatusOK {
		defer resp.Body.Close()
		return nil, c.httpError("/event", resp)
	}
	return resp.Body, nil
}

func (c *client) streamEvents(ctx context.Context, body io.ReadCloser, out chan<- RawEvent) error {
	defer body.Close()

	raw := make(chan SSEEvent, 32)
	parseErr := make(chan error, 1)
	go func() {
		defer close(raw)
		parseErr <- ParseStream(ctx, body, raw)
		close(parseErr)
	}()

	for evt := range raw {
		if evt.Data == "" {
			continue
		}
		var env sseEnvelope
		if err := json.Unmarshal([]byte(evt.Data), &env); err != nil {
			return fmt.Errorf("parse sse event json: %w", err)
		}
		eventID := evt.ID
		if eventID == "" {
			eventID = env.ID
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case out <- RawEvent{ID: eventID, Type: env.Type, Data: []byte(evt.Data)}:
		}
	}
	if err := <-parseErr; err != nil {
		return err
	}
	return nil
}
