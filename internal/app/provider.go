package app

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"sort"
	"strings"

	"atomgit.com/openeuler/euler-copilot-shell/internal/transport"
)

type ProviderStatus struct {
	ID           string
	Name         string
	DefaultModel string
	Connected    bool
	Env          []string
}

func (a *App) ListProviders(ctx context.Context) ([]ProviderStatus, error) {
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	cwd, err := os.Getwd()
	if err != nil {
		return nil, fmt.Errorf("resolve cwd: %w", err)
	}
	statuses, err := a.listAPIKeyProviders(ctx, cwd)
	if err == nil {
		return statuses, nil
	}
	// A concurrent witty command (provider connect, server stop, config
	// refresh) can restart the server between Ensure and this request. The new
	// server has a new password, so the in-flight client receives 401. Re-run
	// Ensure once and retry with the refreshed connection before surfacing the
	// error. Explicit --server-url connections have no manager to refresh.
	if a.serverMgr == nil || !isServerAuthError(err) {
		return nil, err
	}
	if refreshErr := a.refreshServerConnection(ctx); refreshErr != nil {
		return nil, err
	}
	return a.listAPIKeyProviders(ctx, cwd)
}

// refreshServerConnection re-runs server discovery and replaces the transport
// client with the current URL and password.
func (a *App) refreshServerConnection(ctx context.Context) error {
	conn, err := a.serverMgr.Ensure(ctx)
	if err != nil {
		return fmt.Errorf("refresh opencode server connection: %w", err)
	}
	client, err := transport.NewClient(transport.Options{
		BaseURL:          conn.URL,
		Logger:           a.logger,
		Password:         conn.Password,
		OnRequestSuccess: a.serverMgr.TouchLastUsed,
	})
	if err != nil {
		return fmt.Errorf("reconnect opencode server: %w", err)
	}
	a.transport = client
	return nil
}

func isServerAuthError(err error) bool {
	var httpErr *transport.HTTPError
	return errors.As(err, &httpErr) && httpErr.StatusCode == http.StatusUnauthorized
}

func (a *App) ConnectProviderWithAPIKey(ctx context.Context, input, apiKey string) (ProviderStatus, error) {
	if err := ctx.Err(); err != nil {
		return ProviderStatus{}, err
	}
	cwd, err := os.Getwd()
	if err != nil {
		return ProviderStatus{}, fmt.Errorf("resolve cwd: %w", err)
	}
	providers, authMethods, err := a.loadProviderCatalog(ctx, cwd)
	if err != nil {
		return ProviderStatus{}, err
	}
	provider, err := resolveProvider(providers.All, input)
	if err != nil {
		return ProviderStatus{}, err
	}
	providerStatus := newProviderStatus(provider, providers)
	if !providerStatus.Connected && !providerIsAPIKeyCapable(provider, authMethods) {
		return ProviderStatus{}, fmt.Errorf("the current provider does not support API key authentication")
	}
	key := strings.TrimSpace(apiKey)
	if key == "" {
		key = lookupProviderAPIKey(providerStatus)
	}
	if key == "" {
		envNames := providerEnvNames(providerStatus)
		if len(envNames) == 0 {
			return ProviderStatus{}, fmt.Errorf("API key is required; pass --key, pipe it on stdin, or enter it interactively")
		}
		return ProviderStatus{}, fmt.Errorf("API key is required; pass --key, pipe it on stdin, enter it interactively, or set one of: %s", strings.Join(envNames, ", "))
	}
	if err := a.transport.SetProviderAPIKey(ctx, providerStatus.ID, key); err != nil {
		return ProviderStatus{}, fmt.Errorf("connect provider %s: verify API key and provider availability: %w", providerStatus.ID, err)
	}
	refreshed, err := a.listAPIKeyProviders(ctx, cwd)
	if err != nil {
		return ProviderStatus{}, err
	}
	providerStatus, err = resolveProviderStatus(refreshed, providerStatus.ID)
	if err != nil {
		return ProviderStatus{}, err
	}
	if !providerStatus.Connected && a.serverMgr != nil {
		if stopErr := a.serverMgr.Stop(ctx); stopErr != nil {
			a.logger.Debug("stop server before credentials reload", "error", stopErr)
		}
		conn, ensureErr := a.serverMgr.Ensure(ctx)
		if ensureErr != nil {
			return ProviderStatus{}, fmt.Errorf("restart server to activate credentials: %w", ensureErr)
		}
		newTransport, newTransportErr := transport.NewClient(transport.Options{
			BaseURL:  conn.URL,
			Logger:   a.logger,
			Password: conn.Password,
		})
		if newTransportErr != nil {
			return ProviderStatus{}, fmt.Errorf("reconnect after server restart: %w", newTransportErr)
		}
		a.transport = newTransport
		refreshed, err = a.listAPIKeyProviders(ctx, cwd)
		if err != nil {
			return ProviderStatus{}, err
		}
		providerStatus, err = resolveProviderStatus(refreshed, providerStatus.ID)
		if err != nil {
			return ProviderStatus{}, err
		}
	}
	if !providerStatus.Connected {
		return ProviderStatus{}, fmt.Errorf("provider %s did not appear connected after updating credentials", providerStatus.ID)
	}
	return providerStatus, nil
}

func (a *App) listAPIKeyProviders(ctx context.Context, cwd string) ([]ProviderStatus, error) {
	providers, authMethods, err := a.loadProviderCatalog(ctx, cwd)
	if err != nil {
		return nil, err
	}
	connectedSet := make(map[string]struct{}, len(providers.Connected))
	for _, id := range providers.Connected {
		connectedSet[strings.TrimSpace(id)] = struct{}{}
	}
	statuses := make([]ProviderStatus, 0, len(providers.All))
	for _, provider := range providers.All {
		providerID := strings.TrimSpace(provider.ID)
		if providerID == "" {
			continue
		}
		_, isConnected := connectedSet[providerID]
		if !isConnected && !providerIsAPIKeyCapable(provider, authMethods) {
			continue
		}
		statuses = append(statuses, newProviderStatus(provider, providers))
	}
	sort.Slice(statuses, func(i, j int) bool {
		if statuses[i].Connected != statuses[j].Connected {
			return statuses[i].Connected
		}
		left := strings.ToLower(displayProviderName(statuses[i]))
		right := strings.ToLower(displayProviderName(statuses[j]))
		if left == right {
			return statuses[i].ID < statuses[j].ID
		}
		return left < right
	})
	return statuses, nil
}

func (a *App) loadProviderCatalog(ctx context.Context, cwd string) (transport.ProviderList, transport.ProviderAuthMethods, error) {
	providers, err := a.transport.ListProviders(ctx, cwd, "")
	if err != nil {
		return transport.ProviderList{}, nil, fmt.Errorf("list providers: %w", serverAuthHint(err))
	}
	authMethods, err := a.transport.ListProviderAuthMethods(ctx, cwd, "")
	if err != nil {
		return transport.ProviderList{}, nil, fmt.Errorf("list provider auth methods: %w", serverAuthHint(err))
	}
	return providers, authMethods, nil
}

// serverAuthHint turns a bare HTTP 401 from the opencode server into an
// actionable message. A 401 here usually means the client password and the
// running server's password disagree (for example after a manual restart or a
// state file written by another user), not that the AI provider key is bad.
func serverAuthHint(err error) error {
	var httpErr *transport.HTTPError
	if !errors.As(err, &httpErr) || httpErr.StatusCode != http.StatusUnauthorized {
		return err
	}
	return fmt.Errorf("%w (the opencode server rejected authentication; run 'witty doctor', then 'witty server stop' and retry, or check server.password / OPENCODE_SERVER_PASSWORD)", err)
}

func newProviderStatus(provider transport.Provider, providers transport.ProviderList) ProviderStatus {
	connected := false
	for _, id := range providers.Connected {
		if strings.TrimSpace(id) == strings.TrimSpace(provider.ID) {
			connected = true
			break
		}
	}
	return ProviderStatus{
		ID:           strings.TrimSpace(provider.ID),
		Name:         strings.TrimSpace(provider.Name),
		DefaultModel: strings.TrimSpace(providers.Default[strings.TrimSpace(provider.ID)]),
		Connected:    connected,
		Env:          append([]string(nil), provider.Env...),
	}
}

func supportsAPIKey(methods []transport.ProviderAuthMethod) bool {
	for _, method := range methods {
		if !strings.EqualFold(strings.TrimSpace(method.Type), "api") {
			continue
		}
		if len(method.Prompts) == 0 {
			return true
		}
	}
	return false
}

func providerIsAPIKeyCapable(provider transport.Provider, authMethods transport.ProviderAuthMethods) bool {
	methodList, hasAuthEntry := authMethods[strings.TrimSpace(provider.ID)]
	if hasAuthEntry {
		return supportsAPIKey(methodList)
	}
	return len(provider.Env) > 0
}

func resolveProvider(providers []transport.Provider, input string) (transport.Provider, error) {
	needle := strings.TrimSpace(input)
	if needle == "" {
		return transport.Provider{}, fmt.Errorf("provider is required")
	}
	for _, provider := range providers {
		if strings.TrimSpace(provider.ID) == needle {
			return provider, nil
		}
	}
	var matches []transport.Provider
	for _, provider := range providers {
		if strings.EqualFold(strings.TrimSpace(provider.ID), needle) || strings.EqualFold(strings.TrimSpace(provider.Name), needle) {
			matches = append(matches, provider)
		}
	}
	switch len(matches) {
	case 0:
		return transport.Provider{}, fmt.Errorf("provider %q not found; run `witty provider list` to see supported providers", needle)
	case 1:
		return matches[0], nil
	default:
		ids := make([]string, 0, len(matches))
		for _, match := range matches {
			ids = append(ids, strings.TrimSpace(match.ID))
		}
		sort.Strings(ids)
		return transport.Provider{}, fmt.Errorf("provider %q is ambiguous; matched ids: %s", needle, strings.Join(ids, ", "))
	}
}

func resolveProviderStatus(providers []ProviderStatus, input string) (ProviderStatus, error) {
	needle := strings.TrimSpace(input)
	if needle == "" {
		return ProviderStatus{}, fmt.Errorf("provider is required")
	}
	for _, provider := range providers {
		if provider.ID == needle {
			return provider, nil
		}
	}
	var matches []ProviderStatus
	for _, provider := range providers {
		if strings.EqualFold(provider.ID, needle) || strings.EqualFold(provider.Name, needle) {
			matches = append(matches, provider)
		}
	}
	switch len(matches) {
	case 0:
		return ProviderStatus{}, fmt.Errorf("provider %q not found; run `witty provider list` to see supported providers", needle)
	case 1:
		return matches[0], nil
	default:
		ids := make([]string, 0, len(matches))
		for _, match := range matches {
			ids = append(ids, match.ID)
		}
		sort.Strings(ids)
		return ProviderStatus{}, fmt.Errorf("provider %q is ambiguous; matched ids: %s", needle, strings.Join(ids, ", "))
	}
}

func lookupProviderAPIKey(provider ProviderStatus) string {
	for _, envName := range providerEnvNames(provider) {
		if value := strings.TrimSpace(os.Getenv(envName)); value != "" {
			return value
		}
	}
	return ""
}

func providerEnvNames(provider ProviderStatus) []string {
	seen := map[string]struct{}{}
	var names []string
	for _, envName := range provider.Env {
		trimmed := strings.TrimSpace(envName)
		if trimmed == "" {
			continue
		}
		if _, ok := seen[trimmed]; ok {
			continue
		}
		seen[trimmed] = struct{}{}
		names = append(names, trimmed)
	}
	fallback := conventionalProviderAPIKeyEnv(provider.ID)
	if fallback != "" {
		if _, ok := seen[fallback]; !ok {
			names = append(names, fallback)
		}
	}
	return names
}

func conventionalProviderAPIKeyEnv(providerID string) string {
	providerID = strings.TrimSpace(providerID)
	if providerID == "" {
		return ""
	}
	mapped := strings.Map(func(r rune) rune {
		switch {
		case r >= 'a' && r <= 'z':
			return r - ('a' - 'A')
		case r >= 'A' && r <= 'Z', r >= '0' && r <= '9':
			return r
		default:
			return '_'
		}
	}, providerID)
	mapped = strings.Trim(mapped, "_")
	mapped = strings.ReplaceAll(mapped, "__", "_")
	if mapped == "" {
		return ""
	}
	return mapped + "_API_KEY"
}

func displayProviderName(provider ProviderStatus) string {
	if strings.TrimSpace(provider.Name) != "" {
		return provider.Name
	}
	return provider.ID
}
