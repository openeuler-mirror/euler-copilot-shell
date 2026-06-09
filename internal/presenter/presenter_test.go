package presenter

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/event"
	"atomgit.com/openeuler/witty-cli/internal/transport"
)

var updatePresenterGolden = flag.Bool("update", false, "update presenter golden files")

func TestPresenter_Golden(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: true})
	ctx := context.Background()

	events := []event.AppEvent{
		{Kind: event.EventStepStarted},
		{Kind: event.EventStepEnded, Payload: event.StepEndedPayload{Cost: 1.25, Tokens: event.StepTokens{Input: 1, Output: 2, Reasoning: 3}}},
		{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "bash", CallID: "call_1", Input: json.RawMessage(`{"cmd":"ls"}`)}},
		{Kind: event.EventToolSucceeded, Payload: event.ToolResultPayload{CallID: "call_1", Output: "ok"}},
		{Kind: event.EventToolFailed, Payload: event.ToolResultPayload{CallID: "call_2", Error: "permission denied"}},
		{Kind: event.EventPermissionAsked, Payload: event.PermissionAskedPayload{RequestID: "per_1", Permission: "tool", Patterns: []string{"bash", "read"}}},
		{Kind: event.EventQuestionAsked, Payload: event.QuestionAskedPayload{RequestID: "que_1", Questions: []event.QuestionInfo{{Question: "Continue?", Options: []event.QuestionOption{{Label: "yes", Description: "do it"}}, Multiple: false, Custom: true}}}},
	}
	for _, evt := range events {
		if err := p.PresentEvent(ctx, evt); err != nil {
			t.Fatalf("PresentEvent(%s) error = %v", evt.Kind, err)
		}
	}

	errs := []error{
		&UserError{Op: "ask", Err: errors.New("prompt is required")},
		&url.Error{Op: "Get", URL: "http://127.0.0.1:4096", Err: errors.New("connection refused")},
		&transport.HTTPError{StatusCode: 500, Endpoint: "/session", Summary: "boom"},
		&SchemaError{Op: "normalize event", Err: errors.New("invalid json")},
	}
	for _, err := range errs {
		if err := p.PresentError(ctx, err); err != nil {
			t.Fatalf("PresentError(%T) error = %v", err, err)
		}
	}

	assertGolden(t, filepath.Join("..", "..", "test", "testdata", "presenter", "basic_ansi.golden"), out.Bytes())
}

func TestPresenter_NonTTYOutputHasNoANSI(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	p := NewPresenter(Options{Writer: &out, IsTTY: false})
	ctx := context.Background()

	if err := p.PresentEvent(ctx, event.AppEvent{Kind: event.EventToolCalled, Payload: event.ToolCalledPayload{ToolName: "bash", CallID: "call_1", Input: json.RawMessage(`{"cmd":"pwd"}`)}}); err != nil {
		t.Fatalf("PresentEvent() error = %v", err)
	}
	if err := p.PresentError(ctx, &transport.HTTPError{StatusCode: 500, Endpoint: "/event", Summary: "boom"}); err != nil {
		t.Fatalf("PresentError() error = %v", err)
	}

	got := out.String()
	if strings.Contains(got, "\x1b[") {
		t.Fatalf("non-TTY output = %q, want no ANSI", got)
	}
	if !strings.Contains(got, "[tool] bash call=call_1 input={\"cmd\":\"pwd\"}") {
		t.Fatalf("non-TTY output = %q, want readable tool line", got)
	}
	if !strings.Contains(got, "[server] http /event: status 500: boom") {
		t.Fatalf("non-TTY output = %q, want readable error line", got)
	}
}

func assertGolden(t *testing.T, path string, got []byte) {
	t.Helper()
	if *updatePresenterGolden {
		if err := os.WriteFile(path, got, 0o644); err != nil {
			t.Fatalf("write golden %s: %v", path, err)
		}
	}
	want, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read golden %s: %v", path, err)
	}
	if !bytes.Equal(got, want) {
		t.Fatalf("golden mismatch for %s\n--- got ---\n%s\n--- want ---\n%s", path, got, want)
	}
}
