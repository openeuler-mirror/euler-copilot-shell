package permission

import (
	"bytes"
	"context"
	"errors"
	"reflect"
	"strings"
	"testing"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/event"
	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
)

func TestManager_HandlePermission_ApproveAfterRetry(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	transport := &fakeTransport{}
	prompt := &scriptedPrompt{responses: []string{"later", "o"}}
	manager := mustManager(t, Options{
		Transport:   transport,
		Prompt:      prompt,
		Writer:      &out,
		Interactive: true,
	})

	err := manager.HandlePermission(context.Background(), event.PermissionAskedPayload{
		RequestID:  "per_1",
		Permission: "tool",
		Patterns:   []string{"bash"},
	})
	if err != nil {
		t.Fatalf("HandlePermission() error = %v", err)
	}
	if len(transport.permissionReplies) != 1 {
		t.Fatalf("permission replies = %+v, want 1", transport.permissionReplies)
	}
	if got := transport.permissionReplies[0]; got.requestID != "per_1" || got.decision.Reply != "once" {
		t.Fatalf("permission reply = %+v, want once", got)
	}
	if !strings.Contains(out.String(), "invalid response") {
		t.Fatalf("output = %q, want retry hint", out.String())
	}
}

func TestManager_HandlePermission_NonInteractiveRejects(t *testing.T) {
	t.Parallel()

	var out bytes.Buffer
	transport := &fakeTransport{}
	manager := mustManager(t, Options{
		Transport: transport,
		Writer:    &out,
	})

	err := manager.HandlePermission(context.Background(), event.PermissionAskedPayload{
		RequestID:  "per_2",
		Permission: "tool",
	})
	if err != nil {
		t.Fatalf("HandlePermission() error = %v", err)
	}
	if len(transport.permissionReplies) != 1 || transport.permissionReplies[0].decision.Reply != "reject" {
		t.Fatalf("permission replies = %+v, want reject", transport.permissionReplies)
	}
	if !strings.Contains(out.String(), "non-interactive mode") {
		t.Fatalf("output = %q, want non-interactive note", out.String())
	}
}

func TestManager_HandleQuestion_ReplySingleChoice(t *testing.T) {
	t.Parallel()

	transport := &fakeTransport{}
	prompt := &scriptedPrompt{responses: []string{"1"}}
	manager := mustManager(t, Options{
		Transport:   transport,
		Prompt:      prompt,
		Writer:      &bytes.Buffer{},
		Interactive: true,
	})

	err := manager.HandleQuestion(context.Background(), event.QuestionAskedPayload{
		RequestID: "que_1",
		Questions: []event.QuestionInfo{{
			Question: "Continue?",
			Options:  []event.QuestionOption{{Label: "yes", Description: "do it"}, {Label: "no", Description: "stop"}},
		}},
	})
	if err != nil {
		t.Fatalf("HandleQuestion() error = %v", err)
	}
	want := [][][]string{{{"yes"}}}
	if !reflect.DeepEqual(transport.questionReplies, want) {
		t.Fatalf("question replies = %#v, want %#v", transport.questionReplies, want)
	}
}

func TestManager_HandleQuestion_ReplyMultipleAndCustom(t *testing.T) {
	t.Parallel()

	transport := &fakeTransport{}
	prompt := &scriptedPrompt{responses: []string{"1, custom answer"}}
	manager := mustManager(t, Options{
		Transport:   transport,
		Prompt:      prompt,
		Writer:      &bytes.Buffer{},
		Interactive: true,
	})

	err := manager.HandleQuestion(context.Background(), event.QuestionAskedPayload{
		RequestID: "que_2",
		Questions: []event.QuestionInfo{{
			Header:   "Approval",
			Question: "Which actions should run?",
			Options:  []event.QuestionOption{{Label: "read"}, {Label: "write"}},
			Multiple: true,
			Custom:   true,
		}},
	})
	if err != nil {
		t.Fatalf("HandleQuestion() error = %v", err)
	}
	want := [][][]string{{{"read", "custom answer"}}}
	if !reflect.DeepEqual(transport.questionReplies, want) {
		t.Fatalf("question replies = %#v, want %#v", transport.questionReplies, want)
	}
}

func TestManager_HandleQuestion_Rejects(t *testing.T) {
	t.Parallel()

	transport := &fakeTransport{}
	prompt := &scriptedPrompt{responses: []string{"reject"}}
	manager := mustManager(t, Options{
		Transport:   transport,
		Prompt:      prompt,
		Writer:      &bytes.Buffer{},
		Interactive: true,
	})

	err := manager.HandleQuestion(context.Background(), event.QuestionAskedPayload{
		RequestID: "que_3",
		Questions: []event.QuestionInfo{{Question: "Continue?", Options: []event.QuestionOption{{Label: "yes"}}}},
	})
	if err != nil {
		t.Fatalf("HandleQuestion() error = %v", err)
	}
	if !reflect.DeepEqual(transport.questionRejects, []string{"que_3"}) {
		t.Fatalf("question rejects = %#v, want que_3", transport.questionRejects)
	}
}

func TestManager_HandleEvent_ContextCanceled(t *testing.T) {
	transport := &fakeTransport{}
	prompt := &blockingPrompt{started: make(chan struct{}), done: make(chan struct{})}
	manager := mustManager(t, Options{
		Transport:   transport,
		Prompt:      prompt,
		Writer:      &bytes.Buffer{},
		Interactive: true,
	})

	ctx, cancel := context.WithCancel(context.Background())
	result := make(chan error, 1)
	go func() {
		result <- manager.HandleEvent(ctx, event.AppEvent{
			Kind:    event.EventPermissionAsked,
			Payload: event.PermissionAskedPayload{RequestID: "per_4", Permission: "tool"},
		})
	}()

	select {
	case <-prompt.started:
	case <-time.After(time.Second):
		t.Fatal("blocking prompt was not entered")
	}

	cancel()

	select {
	case err := <-result:
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("HandleEvent() error = %v, want context.Canceled", err)
		}
	case <-time.After(time.Second):
		t.Fatal("HandleEvent() did not return after cancel")
	}

	select {
	case <-prompt.done:
	case <-time.After(time.Second):
		t.Fatal("blocking prompt was not released")
	}

	if len(transport.permissionReplies) != 0 {
		t.Fatalf("permission replies = %+v, want none on cancel", transport.permissionReplies)
	}
}

func mustManager(t *testing.T, opts Options) Manager {
	t.Helper()
	manager, err := NewManager(opts)
	if err != nil {
		t.Fatalf("NewManager() error = %v", err)
	}
	return manager
}

type fakeTransport struct {
	permissionReplies []permissionReply
	questionReplies   [][][]string
	questionRejects   []string
}

type permissionReply struct {
	requestID string
	decision  transport.PermissionDecision
}

func (f *fakeTransport) ReplyPermission(_ context.Context, requestID string, _ string, decision transport.PermissionDecision) (bool, error) {
	f.permissionReplies = append(f.permissionReplies, permissionReply{requestID: requestID, decision: decision})
	return true, nil
}

func (f *fakeTransport) ReplyQuestion(_ context.Context, requestID string, _ string, answers [][]string) (bool, error) {
	copied := make([][]string, 0, len(answers))
	for _, answer := range answers {
		copied = append(copied, append([]string(nil), answer...))
	}
	f.questionReplies = append(f.questionReplies, copied)
	return true, nil
}

func (f *fakeTransport) RejectQuestion(_ context.Context, requestID string, _ string) (bool, error) {
	f.questionRejects = append(f.questionRejects, requestID)
	return true, nil
}

type scriptedPrompt struct {
	responses []string
	calls     int
}

func (p *scriptedPrompt) ReadLine(context.Context, string) (string, error) {
	if p.calls >= len(p.responses) {
		return "", errors.New("no scripted response available")
	}
	response := p.responses[p.calls]
	p.calls++
	return response, nil
}

type blockingPrompt struct {
	started chan struct{}
	done    chan struct{}
}

func (p *blockingPrompt) ReadLine(ctx context.Context, _ string) (string, error) {
	select {
	case <-p.started:
	default:
		close(p.started)
	}
	<-ctx.Done()
	select {
	case <-p.done:
	default:
		close(p.done)
	}
	return "", ctx.Err()
}
