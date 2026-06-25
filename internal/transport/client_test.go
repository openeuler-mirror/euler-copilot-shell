package transport

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestClient_Health(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			t.Fatalf("method = %s, want GET", r.Method)
		}
		if r.URL.Path != "/global/health" {
			t.Fatalf("path = %s, want /global/health", r.URL.Path)
		}
		if got := r.Header.Get("User-Agent"); got != "test-agent" {
			t.Fatalf("User-Agent = %q, want test-agent", got)
		}
		if got := r.Header.Get("Accept"); got != "application/json" {
			t.Fatalf("Accept = %q, want application/json", got)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"healthy":true,"version":"1.2.3"}`))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL, UserAgent: "test-agent"})
	health, err := client.Health(context.Background())
	if err != nil {
		t.Fatalf("Health() error = %v", err)
	}
	if !health.Healthy || health.Version != "1.2.3" {
		t.Fatalf("Health() = %+v, want healthy 1.2.3", health)
	}
}

func TestClient_ListSessionsBuildsQuery(t *testing.T) {
	roots := true
	start := 2.0
	limit := 10.0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/session" {
			t.Fatalf("request = %s %s, want GET /session", r.Method, r.URL.Path)
		}
		query := r.URL.Query()
		for key, want := range map[string]string{
			"directory": "/work",
			"workspace": "wrk_1",
			"scope":     "project",
			"path":      "main.go",
			"roots":     "true",
			"start":     "2",
			"limit":     "10",
			"search":    "hello",
		} {
			if got := query.Get(key); got != want {
				t.Fatalf("query[%s] = %q, want %q", key, got, want)
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work"}]`))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	sessions, err := client.ListSessions(context.Background(), SessionFilter{
		Directory: "/work",
		Workspace: "wrk_1",
		Scope:     "project",
		Path:      "main.go",
		Roots:     &roots,
		Start:     &start,
		Limit:     &limit,
		Search:    "hello",
	})
	if err != nil {
		t.Fatalf("ListSessions() error = %v", err)
	}
	if len(sessions) != 1 || sessions[0].ID != "ses_1" {
		t.Fatalf("ListSessions() = %+v, want ses_1", sessions)
	}
}

func TestClient_ProviderDefaults(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/provider" {
			t.Fatalf("request = %s %s, want GET /provider", r.Method, r.URL.Path)
		}
		if r.URL.Query().Get("directory") != "/work" {
			t.Fatalf("directory query = %q, want /work", r.URL.Query().Get("directory"))
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"all":[{"id":"zhipuai","name":"ZhipuAI","source":"api","env":["ZHIPUAI_API_KEY"],"options":{},"models":{}}],"default":{"zhipuai":"glm-5v-turbo"},"connected":["zhipuai"]}`))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	defaults, err := client.ProviderDefaults(context.Background(), "/work", "")
	if err != nil {
		t.Fatalf("ProviderDefaults() error = %v", err)
	}
	if len(defaults.Connected) != 1 || defaults.Connected[0] != "zhipuai" {
		t.Fatalf("connected = %#v, want zhipuai", defaults.Connected)
	}
	if defaults.Default["zhipuai"] != "glm-5v-turbo" {
		t.Fatalf("default map = %#v, want zhipuai default", defaults.Default)
	}
}

func TestClient_ListProvidersAndAuthMethods(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/provider":
			if r.Method != http.MethodGet {
				t.Fatalf("provider method = %s, want GET", r.Method)
			}
			_, _ = w.Write([]byte(`{"all":[{"id":"deepseek","name":"DeepSeek","source":"api","env":["DEEPSEEK_API_KEY"],"options":{},"models":{}}],"default":{"deepseek":"deepseek-chat"},"connected":["deepseek"]}`))
		case "/provider/auth":
			if r.Method != http.MethodGet {
				t.Fatalf("provider auth method = %s, want GET", r.Method)
			}
			_, _ = w.Write([]byte(`{"deepseek":[{"type":"api","label":"API Key"}]}`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	providers, err := client.ListProviders(context.Background(), "/work", "")
	if err != nil {
		t.Fatalf("ListProviders() error = %v", err)
	}
	if len(providers.All) != 1 || providers.All[0].ID != "deepseek" {
		t.Fatalf("providers = %#v, want deepseek", providers.All)
	}
	methods, err := client.ListProviderAuthMethods(context.Background(), "/work", "")
	if err != nil {
		t.Fatalf("ListProviderAuthMethods() error = %v", err)
	}
	if len(methods["deepseek"]) != 1 || methods["deepseek"][0].Type != "api" {
		t.Fatalf("methods = %#v, want deepseek api", methods)
	}
}

func TestClient_SetProviderAPIKey(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPut || r.URL.Path != "/auth/deepseek" {
			t.Fatalf("request = %s %s, want PUT /auth/deepseek", r.Method, r.URL.Path)
		}
		var body struct {
			Type string `json:"type"`
			Key  string `json:"key"`
		}
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatalf("decode body: %v", err)
		}
		if body.Type != "api" || body.Key != "sk-test" {
			t.Fatalf("body = %#v, want api/sk-test", body)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`true`))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	if err := client.SetProviderAPIKey(context.Background(), "deepseek", "sk-test"); err != nil {
		t.Fatalf("SetProviderAPIKey() error = %v", err)
	}
}

func TestClient_CreateGetSessionAndPrompt(t *testing.T) {
	var sawCreate, sawGet, sawPrompt bool
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/session":
			sawCreate = true
			if r.Method != http.MethodPost {
				t.Fatalf("create method = %s, want POST", r.Method)
			}
			if r.URL.Query().Get("directory") != "/work" {
				t.Fatalf("create directory query = %q", r.URL.Query().Get("directory"))
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatalf("decode create body: %v", err)
			}
			if body["title"] != "New session" || body["agent"] != "build" {
				t.Fatalf("create body = %#v", body)
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work"}`))
		case "/session/ses_1":
			sawGet = true
			if r.Method != http.MethodGet {
				t.Fatalf("get method = %s, want GET", r.Method)
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(`{"id":"ses_1","slug":"s","projectID":"proj_1","directory":"/work"}`))
		case "/session/ses_1/prompt_async":
			sawPrompt = true
			if r.Method != http.MethodPost {
				t.Fatalf("prompt method = %s, want POST", r.Method)
			}
			if r.URL.Query().Get("workspace") != "wrk_1" {
				t.Fatalf("prompt workspace query = %q", r.URL.Query().Get("workspace"))
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatalf("decode prompt body: %v", err)
			}
			parts, ok := body["parts"].([]any)
			if !ok || len(parts) != 1 {
				t.Fatalf("prompt parts = %#v", body["parts"])
			}
			w.WriteHeader(http.StatusNoContent)
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	session, err := client.CreateSession(context.Background(), CreateSessionRequest{Directory: "/work", Title: "New session", Agent: "build"})
	if err != nil {
		t.Fatalf("CreateSession() error = %v", err)
	}
	if session.ID != "ses_1" {
		t.Fatalf("CreateSession() ID = %q, want ses_1", session.ID)
	}
	got, err := client.GetSession(context.Background(), "ses_1")
	if err != nil {
		t.Fatalf("GetSession() error = %v", err)
	}
	if got.ID != "ses_1" {
		t.Fatalf("GetSession() ID = %q, want ses_1", got.ID)
	}
	if err := client.SendPromptAsync(context.Background(), "ses_1", PromptRequest{Workspace: "wrk_1", Parts: []PromptPart{{Type: "text", Text: "hi"}}}); err != nil {
		t.Fatalf("SendPromptAsync() error = %v", err)
	}
	if !sawCreate || !sawGet || !sawPrompt {
		t.Fatalf("sawCreate=%v sawGet=%v sawPrompt=%v, want all true", sawCreate, sawGet, sawPrompt)
	}
}

func TestClient_PermissionAndQuestionReplies(t *testing.T) {
	paths := map[string]string{
		"/permission/per_1/reply": "POST",
		"/question/que_1/reply":   "POST",
		"/question/que_1/reject":  "POST",
	}
	seen := map[string]bool{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		method, ok := paths[r.URL.Path]
		if !ok {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		if r.Method != method {
			t.Fatalf("method = %s, want %s", r.Method, method)
		}
		seen[r.URL.Path] = true
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`true`))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	if ok, err := client.ReplyPermission(context.Background(), "per_1", "", PermissionDecision{Reply: "once"}); err != nil || !ok {
		t.Fatalf("ReplyPermission() = %v, %v; want true, nil", ok, err)
	}
	if ok, err := client.ReplyQuestion(context.Background(), "que_1", "", [][]string{{"yes"}}); err != nil || !ok {
		t.Fatalf("ReplyQuestion() = %v, %v; want true, nil", ok, err)
	}
	if ok, err := client.RejectQuestion(context.Background(), "que_1", ""); err != nil || !ok {
		t.Fatalf("RejectQuestion() = %v, %v; want true, nil", ok, err)
	}
	for path := range paths {
		if !seen[path] {
			t.Fatalf("path %s was not called", path)
		}
	}
}

func TestClient_HTTPErrorIncludesContext(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "bad things", http.StatusTeapot)
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	_, err := client.Health(context.Background())
	var httpErr *HTTPError
	if !errors.As(err, &httpErr) {
		t.Fatalf("Health() error = %T %v, want HTTPError", err, err)
	}
	if httpErr.StatusCode != http.StatusTeapot || httpErr.Endpoint != "/global/health" || !strings.Contains(httpErr.Summary, "bad things") {
		t.Fatalf("HTTPError = %+v, want status/endpoint/summary", httpErr)
	}
}

func TestClient_ContextCancelInterruptsRequest(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-r.Context().Done()
		w.WriteHeader(http.StatusOK)
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	_, err := client.Health(ctx)
	if err == nil || !strings.Contains(err.Error(), context.Canceled.Error()) {
		t.Fatalf("Health() error = %v, want context canceled", err)
	}
}

func TestClient_DebugLogDoesNotLeakBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	var logs bytes.Buffer
	logger := slog.New(slog.NewTextHandler(&logs, &slog.HandlerOptions{Level: slog.LevelDebug}))
	client := mustClient(t, Options{BaseURL: server.URL, Logger: logger})
	secret := "session-secret-token"
	if err := client.SendPromptAsync(context.Background(), "ses_1", PromptRequest{System: secret}); err != nil {
		t.Fatalf("SendPromptAsync() error = %v", err)
	}
	if strings.Contains(logs.String(), secret) {
		t.Fatalf("debug logs leaked request body: %q", logs.String())
	}
}

func mustClient(t *testing.T, opts Options) Client {
	t.Helper()
	client, err := NewClient(opts)
	if err != nil {
		t.Fatalf("NewClient() error = %v", err)
	}
	return client
}

func TestClient_Dispose(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/global/dispose" {
			t.Fatalf("request = %s %s, want POST /global/dispose", r.Method, r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("true"))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	if err := client.Dispose(context.Background()); err != nil {
		t.Fatalf("Dispose() error = %v", err)
	}
}

func TestClient_Dispose_SendPassword(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		user, pass, ok := r.BasicAuth()
		if !ok || user != "opencode" || pass != "secret" {
			t.Fatalf("missing/incorrect auth: user=%q pass=%q", user, pass)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte("true"))
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL, Password: "secret"})
	if err := client.Dispose(context.Background()); err != nil {
		t.Fatalf("Dispose() error = %v", err)
	}
}

func TestClient_Dispose_ErrorStatus(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer server.Close()

	client := mustClient(t, Options{BaseURL: server.URL})
	if err := client.Dispose(context.Background()); err == nil {
		t.Fatal("Dispose() error = nil, want error for 500")
	}
}

func TestClient_OnRequestSuccess_CalledOnSuccess(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"healthy":true,"version":"1.0.0"}`))
	}))
	defer server.Close()

	calls := 0
	client := mustClient(t, Options{
		BaseURL:          server.URL,
		OnRequestSuccess: func() { calls++ },
	})
	if _, err := client.Health(context.Background()); err != nil {
		t.Fatalf("Health() error = %v", err)
	}
	if calls != 1 {
		t.Fatalf("OnRequestSuccess called %d times, want 1", calls)
	}
}

func TestClient_OnRequestSuccess_NotCalledOnFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		http.Error(w, "bad", http.StatusTeapot)
	}))
	defer server.Close()

	calls := 0
	client := mustClient(t, Options{
		BaseURL:          server.URL,
		OnRequestSuccess: func() { calls++ },
	})
	if _, err := client.Health(context.Background()); err == nil {
		t.Fatal("Health() error = nil, want error")
	}
	if calls != 0 {
		t.Fatalf("OnRequestSuccess called %d times, want 0 on failure", calls)
	}
}

func TestClient_OnRequestSuccess_CalledForNoContent(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	}))
	defer server.Close()

	calls := 0
	client := mustClient(t, Options{
		BaseURL:          server.URL,
		OnRequestSuccess: func() { calls++ },
	})
	if err := client.SendPromptAsync(context.Background(), "ses_1", PromptRequest{Parts: []PromptPart{{Type: "text", Text: "hi"}}}); err != nil {
		t.Fatalf("SendPromptAsync() error = %v", err)
	}
	if calls != 1 {
		t.Fatalf("OnRequestSuccess called %d times, want 1", calls)
	}
}
