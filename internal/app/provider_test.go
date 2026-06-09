package app

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	"atomgit.com/openeuler/witty-cli/internal/config"
)

func TestListProviders_FiltersToAPIKeyProviders(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/provider":
			_, _ = w.Write([]byte(`{"all":[{"id":"deepseek","name":"DeepSeek","source":"api","env":["DEEPSEEK_API_KEY"],"options":{},"models":{}},{"id":"zhipuai","name":"ZhipuAI","source":"api","env":["ZHIPUAI_API_KEY"],"options":{},"models":{}},{"id":"anthropic","name":"Anthropic","source":"api","env":["ANTHROPIC_API_KEY"],"options":{},"models":{}},{"id":"azure","name":"Azure","source":"api","env":["AZURE_OPENAI_API_KEY"],"options":{},"models":{}},{"id":"github","name":"GitHub","source":"api","env":[],"options":{},"models":{}}],"default":{"deepseek":"deepseek-chat","zhipuai":"glm-5v-turbo","anthropic":"claude-sonnet-4-6","azure":"gpt-4.1","github":"gpt-4.1"},"connected":["deepseek","zhipuai"]}`))
		case "/provider/auth":
			_, _ = w.Write([]byte(`{"deepseek":[{"type":"api","label":"API Key"}],"azure":[{"type":"api","label":"API key","prompts":[{"type":"text","key":"resourceName","message":"Enter Azure Resource Name"}]}],"github":[{"type":"oauth","label":"OAuth"}]}`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{ConfigFiles: []string{}, Overrides: config.Overrides{ServerURL: server.URL}},
		Stdout: &bytes.Buffer{},
		Stderr: &bytes.Buffer{},
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	providers, err := container.ListProviders(context.Background())
	if err != nil {
		t.Fatalf("ListProviders() error = %v", err)
	}
	if len(providers) != 3 {
		t.Fatalf("providers len = %d, want 3 (connected deepseek + connected zhipuai + github with env fallback)", len(providers))
	}
	if providers[0].ID != "deepseek" || !providers[0].Connected {
		t.Fatalf("provider[0] = %+v, want connected deepseek", providers[0])
	}
	if providers[1].ID != "zhipuai" || !providers[1].Connected {
		t.Fatalf("provider[1] = %+v, want connected zhipuai", providers[1])
	}
	if providers[2].ID != "anthropic" || providers[2].Connected {
		t.Fatalf("provider[2] = %+v, want not-connected anthropic (fallback)", providers[2])
	}
}

func TestConnectProviderWithAPIKey_UsesEnvFallback(t *testing.T) {
	t.Setenv("DEEPSEEK_API_KEY", "sk-env")
	var authCalls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/provider":
			if authCalls.Load() == 0 {
				_, _ = w.Write([]byte(`{"all":[{"id":"deepseek","name":"DeepSeek","source":"api","env":["DEEPSEEK_API_KEY"],"options":{},"models":{}}],"default":{"deepseek":"deepseek-chat"},"connected":[]}`))
				return
			}
			_, _ = w.Write([]byte(`{"all":[{"id":"deepseek","name":"DeepSeek","source":"api","env":["DEEPSEEK_API_KEY"],"options":{},"models":{}}],"default":{"deepseek":"deepseek-chat"},"connected":["deepseek"]}`))
		case "/provider/auth":
			_, _ = w.Write([]byte(`{"deepseek":[{"type":"api","label":"API Key"}]}`))
		case "/auth/deepseek":
			authCalls.Add(1)
			var body struct {
				Type string `json:"type"`
				Key  string `json:"key"`
			}
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatalf("decode body: %v", err)
			}
			if body.Type != "api" || body.Key != "sk-env" {
				t.Fatalf("body = %#v, want api/sk-env", body)
			}
			_, _ = w.Write([]byte(`true`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{ConfigFiles: []string{}, Overrides: config.Overrides{ServerURL: server.URL}},
		Stdout: &bytes.Buffer{},
		Stderr: &bytes.Buffer{},
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	provider, err := container.ConnectProviderWithAPIKey(context.Background(), "deepseek", "")
	if err != nil {
		t.Fatalf("ConnectProviderWithAPIKey() error = %v", err)
	}
	if provider.ID != "deepseek" || !provider.Connected {
		t.Fatalf("provider = %+v, want connected deepseek", provider)
	}
	if authCalls.Load() != 1 {
		t.Fatalf("auth calls = %d, want 1", authCalls.Load())
	}
}

func TestConnectProviderWithAPIKey_RejectsUnknownProvider(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/provider":
			_, _ = w.Write([]byte(`{"all":[{"id":"deepseek","name":"DeepSeek","source":"api","env":["DEEPSEEK_API_KEY"],"options":{},"models":{}}],"default":{"deepseek":"deepseek-chat"},"connected":[]}`))
		case "/provider/auth":
			_, _ = w.Write([]byte(`{"deepseek":[{"type":"api","label":"API Key"}]}`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{ConfigFiles: []string{}, Overrides: config.Overrides{ServerURL: server.URL}},
		Stdout: &bytes.Buffer{},
		Stderr: &bytes.Buffer{},
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	_, err = container.ConnectProviderWithAPIKey(context.Background(), "nonexistent", "sk-test")
	if err == nil {
		t.Fatal("ConnectProviderWithAPIKey() error = nil, want not found error")
	}
	if !strings.Contains(err.Error(), "provider \"nonexistent\" not found") {
		t.Fatalf("error = %q, want not found guidance", err)
	}
}

func TestConnectProviderWithAPIKey_RejectsUnsupportedAuth(t *testing.T) {
	var authCalls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/provider":
			_, _ = w.Write([]byte(`{"all":[{"id":"github","name":"GitHub","source":"api","env":[],"options":{},"models":{}}],"default":{},"connected":[]}`))
		case "/provider/auth":
			_, _ = w.Write([]byte(`{"github":[{"type":"oauth","label":"OAuth"}]}`))
		case "/auth/github":
			authCalls.Add(1)
			_, _ = w.Write([]byte(`true`))
		default:
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
	}))
	defer server.Close()

	container, err := New(context.Background(), Options{
		Config: config.LoadOptions{ConfigFiles: []string{}, Overrides: config.Overrides{ServerURL: server.URL}},
		Stdout: &bytes.Buffer{},
		Stderr: &bytes.Buffer{},
	})
	if err != nil {
		t.Fatalf("New() error = %v", err)
	}

	_, err = container.ConnectProviderWithAPIKey(context.Background(), "github", "sk-test")
	if err == nil {
		t.Fatal("ConnectProviderWithAPIKey() error = nil, want unsupported auth error")
	}
	if !strings.Contains(err.Error(), "当前 Provider 暂不支持 API Key 认证方式") {
		t.Fatalf("error = %q, want unsupported auth guidance", err)
	}
	if authCalls.Load() != 0 {
		t.Fatalf("auth calls = %d, want 0", authCalls.Load())
	}
}
