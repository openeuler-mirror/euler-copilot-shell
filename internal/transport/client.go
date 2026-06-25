package transport

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const defaultUserAgent = "witty-cli/dev"

// Client wraps opencode HTTP APIs used by Witty. SSE parsing remains handwritten
// and no generated typed-client path is used for streaming.
type Client interface {
	Health(ctx context.Context) (Health, error)
	ProbeEndpoint(ctx context.Context, endpoint string) (int, error)
	CreateSession(ctx context.Context, req CreateSessionRequest) (Session, error)
	GetSession(ctx context.Context, sessionID string) (Session, error)
	ListSessions(ctx context.Context, filter SessionFilter) ([]Session, error)
	ProviderDefaults(ctx context.Context, directory, workspace string) (ProviderDefaults, error)
	ListProviders(ctx context.Context, directory, workspace string) (ProviderList, error)
	ListProviderAuthMethods(ctx context.Context, directory, workspace string) (ProviderAuthMethods, error)
	SetProviderAPIKey(ctx context.Context, providerID, apiKey string) error
	SendPromptAsync(ctx context.Context, sessionID string, req PromptRequest) error
	ReplyPermission(ctx context.Context, requestID string, directory string, decision PermissionDecision) (bool, error)
	ReplyQuestion(ctx context.Context, requestID string, directory string, answers [][]string) (bool, error)
	RejectQuestion(ctx context.Context, requestID string, directory string) (bool, error)
	SubscribeEvents(ctx context.Context, filter EventFilter) (<-chan RawEvent, <-chan error)
	ListAgents(ctx context.Context, directory, workspace string) ([]Agent, error)
}

type Options struct {
	BaseURL    string
	Timeout    time.Duration
	UserAgent  string
	HTTPClient *http.Client
	SSEClient  *http.Client
	Logger     *slog.Logger

	// Password is the HTTP Basic Auth password for the opencode server.
	// When non-empty, every request includes an Authorization header.
	Password string
}

type client struct {
	baseURL    *url.URL
	httpClient *http.Client
	sseClient  *http.Client
	userAgent  string
	logger     *slog.Logger
	password   string
}

func NewClient(opts Options) (Client, error) {
	base := opts.BaseURL
	if base == "" {
		base = "http://127.0.0.1:4096"
	}
	parsed, err := url.Parse(base)
	if err != nil {
		return nil, fmt.Errorf("parse base url: %w", err)
	}
	if parsed.Scheme == "" || parsed.Host == "" {
		return nil, fmt.Errorf("parse base url: missing scheme or host")
	}

	timeout := opts.Timeout
	if timeout <= 0 {
		timeout = DefaultTimeout
	}
	httpClient := opts.HTTPClient
	if httpClient == nil {
		httpClient = &http.Client{Timeout: timeout}
	}
	sseClient := opts.SSEClient
	if sseClient == nil {
		sseClient = newSSEHTTPClient(timeout)
	}
	userAgent := opts.UserAgent
	if userAgent == "" {
		userAgent = defaultUserAgent
	}
	logger := opts.Logger
	if logger == nil {
		logger = slog.New(slog.NewTextHandler(io.Discard, nil))
	}

	return &client{
		baseURL:    parsed,
		httpClient: httpClient,
		sseClient:  sseClient,
		userAgent:  userAgent,
		logger:     logger,
		password:   opts.Password,
	}, nil
}

func (c *client) Health(ctx context.Context) (Health, error) {
	var health Health
	if err := c.doJSON(ctx, http.MethodGet, "/global/health", nil, nil, &health, http.StatusOK); err != nil {
		return Health{}, err
	}
	return health, nil
}

// ProbeEndpoint sends a GET request to endpoint and returns the HTTP status code.
// It does not read the response body, making it suitable for probing SSE streams
// like /event and documentation endpoints like /doc.
func (c *client) ProbeEndpoint(ctx context.Context, endpoint string) (int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.endpointURL(endpoint, nil), nil)
	if err != nil {
		return 0, fmt.Errorf("build probe request %s: %w", endpoint, err)
	}
	c.setHeaders(req, false)

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, fmt.Errorf("probe %s: %w", endpoint, err)
	}
	defer func() { _ = resp.Body.Close() }()
	return resp.StatusCode, nil
}

func (c *client) CreateSession(ctx context.Context, req CreateSessionRequest) (Session, error) {
	query := url.Values{}
	addString(query, "directory", req.Directory)
	addString(query, "workspace", req.Workspace)
	var session Session
	if err := c.doJSON(ctx, http.MethodPost, "/session", query, req, &session, http.StatusOK); err != nil {
		return Session{}, err
	}
	return session, nil
}

func (c *client) GetSession(ctx context.Context, sessionID string) (Session, error) {
	if sessionID == "" {
		return Session{}, fmt.Errorf("session id is required")
	}
	var session Session
	endpoint := "/session/" + url.PathEscape(sessionID)
	if err := c.doJSON(ctx, http.MethodGet, endpoint, nil, nil, &session, http.StatusOK); err != nil {
		return Session{}, err
	}
	return session, nil
}

func (c *client) ListSessions(ctx context.Context, filter SessionFilter) ([]Session, error) {
	query := url.Values{}
	addString(query, "directory", filter.Directory)
	addString(query, "workspace", filter.Workspace)
	addString(query, "scope", filter.Scope)
	addString(query, "path", filter.Path)
	addString(query, "search", filter.Search)
	if filter.Roots != nil {
		query.Set("roots", strconv.FormatBool(*filter.Roots))
	}
	if filter.Start != nil {
		query.Set("start", strconv.FormatFloat(*filter.Start, 'f', -1, 64))
	}
	if filter.Limit != nil {
		query.Set("limit", strconv.FormatFloat(*filter.Limit, 'f', -1, 64))
	}

	var sessions []Session
	if err := c.doJSON(ctx, http.MethodGet, "/session", query, nil, &sessions, http.StatusOK); err != nil {
		return nil, err
	}
	return sessions, nil
}

func (c *client) ProviderDefaults(ctx context.Context, directory, workspace string) (ProviderDefaults, error) {
	providers, err := c.ListProviders(ctx, directory, workspace)
	if err != nil {
		return ProviderDefaults{}, err
	}
	return ProviderDefaults{Default: providers.Default, Connected: providers.Connected}, nil
}

func (c *client) ListProviders(ctx context.Context, directory, workspace string) (ProviderList, error) {
	query := url.Values{}
	addString(query, "directory", directory)
	addString(query, "workspace", workspace)
	var providers ProviderList
	if err := c.doJSON(ctx, http.MethodGet, "/provider", query, nil, &providers, http.StatusOK); err != nil {
		return ProviderList{}, err
	}
	if providers.All == nil {
		providers.All = []Provider{}
	}
	if providers.Default == nil {
		providers.Default = map[string]string{}
	}
	if providers.Connected == nil {
		providers.Connected = []string{}
	}
	return providers, nil
}

func (c *client) ListProviderAuthMethods(ctx context.Context, directory, workspace string) (ProviderAuthMethods, error) {
	query := url.Values{}
	addString(query, "directory", directory)
	addString(query, "workspace", workspace)
	var methods ProviderAuthMethods
	if err := c.doJSON(ctx, http.MethodGet, "/provider/auth", query, nil, &methods, http.StatusOK); err != nil {
		return nil, err
	}
	if methods == nil {
		methods = ProviderAuthMethods{}
	}
	return methods, nil
}

func (c *client) ListAgents(ctx context.Context, directory, workspace string) ([]Agent, error) {
	query := url.Values{}
	addString(query, "directory", directory)
	addString(query, "workspace", workspace)
	var agents []Agent
	if err := c.doJSON(ctx, http.MethodGet, "/agent", query, nil, &agents, http.StatusOK); err != nil {
		return nil, err
	}
	return agents, nil
}

func (c *client) SetProviderAPIKey(ctx context.Context, providerID, apiKey string) error {
	providerID = strings.TrimSpace(providerID)
	apiKey = strings.TrimSpace(apiKey)
	if providerID == "" {
		return fmt.Errorf("provider id is required")
	}
	if apiKey == "" {
		return fmt.Errorf("api key is required")
	}
	var ok bool
	endpoint := "/auth/" + url.PathEscape(providerID)
	body := struct {
		Type string `json:"type"`
		Key  string `json:"key"`
	}{Type: "api", Key: apiKey}
	if err := c.doJSON(ctx, http.MethodPut, endpoint, nil, body, &ok, http.StatusOK); err != nil {
		return err
	}
	if !ok {
		return fmt.Errorf("provider %s was not connected", providerID)
	}
	return nil
}

func (c *client) SendPromptAsync(ctx context.Context, sessionID string, req PromptRequest) error {
	if sessionID == "" {
		return fmt.Errorf("session id is required")
	}
	query := url.Values{}
	addString(query, "directory", req.Directory)
	addString(query, "workspace", req.Workspace)
	endpoint := "/session/" + url.PathEscape(sessionID) + "/prompt_async"
	return c.doJSON(ctx, http.MethodPost, endpoint, query, req, nil, http.StatusNoContent)
}

func (c *client) ReplyPermission(ctx context.Context, requestID string, directory string, decision PermissionDecision) (bool, error) {
	if requestID == "" {
		return false, fmt.Errorf("request id is required")
	}
	query := url.Values{}
	addString(query, "directory", directory)
	var ok bool
	endpoint := "/permission/" + url.PathEscape(requestID) + "/reply"
	if err := c.doJSON(ctx, http.MethodPost, endpoint, query, decision, &ok, http.StatusOK); err != nil {
		return false, err
	}
	return ok, nil
}

func (c *client) ReplyQuestion(ctx context.Context, requestID string, directory string, answers [][]string) (bool, error) {
	if requestID == "" {
		return false, fmt.Errorf("request id is required")
	}
	query := url.Values{}
	addString(query, "directory", directory)
	var ok bool
	body := struct {
		Answers [][]string `json:"answers"`
	}{Answers: answers}
	endpoint := "/question/" + url.PathEscape(requestID) + "/reply"
	if err := c.doJSON(ctx, http.MethodPost, endpoint, query, body, &ok, http.StatusOK); err != nil {
		return false, err
	}
	return ok, nil
}

func (c *client) RejectQuestion(ctx context.Context, requestID string, directory string) (bool, error) {
	if requestID == "" {
		return false, fmt.Errorf("request id is required")
	}
	query := url.Values{}
	addString(query, "directory", directory)
	var ok bool
	endpoint := "/question/" + url.PathEscape(requestID) + "/reject"
	if err := c.doJSON(ctx, http.MethodPost, endpoint, query, nil, &ok, http.StatusOK); err != nil {
		return false, err
	}
	return ok, nil
}

func (c *client) doJSON(ctx context.Context, method, endpoint string, query url.Values, body any, out any, expectedStatus int) error {
	var requestBody io.Reader
	if body != nil {
		payload, err := json.Marshal(body)
		if err != nil {
			return fmt.Errorf("marshal request %s: %w", endpoint, err)
		}
		requestBody = bytes.NewReader(payload)
	}

	requestURL := c.endpointURL(endpoint, query)
	req, err := http.NewRequestWithContext(ctx, method, requestURL, requestBody)
	if err != nil {
		return fmt.Errorf("build request %s: %w", endpoint, err)
	}
	c.setHeaders(req, body != nil)

	start := time.Now()
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request %s %s: %w", method, endpoint, err)
	}
	defer func() { _ = resp.Body.Close() }()
	c.logger.Debug("transport request", "method", method, "endpoint", endpoint, "status", resp.StatusCode, "duration", time.Since(start))

	if resp.StatusCode != expectedStatus {
		return c.httpError(endpoint, resp)
	}
	if out == nil || resp.StatusCode == http.StatusNoContent {
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return fmt.Errorf("decode response %s: %w", endpoint, err)
	}
	return nil
}

func (c *client) endpointURL(endpoint string, query url.Values) string {
	u := *c.baseURL
	basePath := strings.TrimRight(u.Path, "/")
	u.Path = basePath + endpoint
	if len(query) > 0 {
		u.RawQuery = query.Encode()
	} else {
		u.RawQuery = ""
	}
	return u.String()
}

func (c *client) setHeaders(req *http.Request, hasBody bool) {
	req.Header.Set("Accept", "application/json")
	req.Header.Set("User-Agent", c.userAgent)
	if hasBody {
		req.Header.Set("Content-Type", "application/json")
	}
	if c.password != "" {
		req.Header.Set("Authorization", basicAuthHeader(c.password))
	}
}

func (c *client) httpError(endpoint string, resp *http.Response) error {
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxResponseSummaryBytes+1))
	if err != nil {
		return &HTTPError{StatusCode: resp.StatusCode, Endpoint: endpoint, Summary: "read error response: " + err.Error()}
	}
	summary := strings.TrimSpace(string(body))
	if len(summary) > maxResponseSummaryBytes {
		summary = summary[:maxResponseSummaryBytes] + "..."
	}
	return &HTTPError{StatusCode: resp.StatusCode, Endpoint: endpoint, Summary: summary}
}

func addString(query url.Values, key, value string) {
	if value != "" {
		query.Set(key, value)
	}
}

// basicAuthHeader returns the value for an HTTP Authorization header using
// the Basic scheme with username "opencode".
func basicAuthHeader(password string) string {
	auth := "opencode:" + password
	return "Basic " + base64.StdEncoding.EncodeToString([]byte(auth))
}
