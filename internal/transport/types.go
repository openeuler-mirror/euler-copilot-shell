package transport

import (
	"encoding/json"
	"errors"
	"sort"
	"time"

	"atomgit.com/openeuler/euler-copilot-shell/internal/transport/generated"
)

// ErrNoConnectedModels indicates that the server exposes no models from
// connected providers, so an interactive model selector has nothing to show.
var ErrNoConnectedModels = errors.New("no models available from connected providers")

const DefaultTimeout = 30 * time.Second

// Health describes the opencode server health endpoint response.
type Health struct {
	Healthy bool   `json:"healthy"`
	Version string `json:"version"`
}

// SessionFilter contains query parameters supported by session list/create endpoints.
type SessionFilter struct {
	Directory string
	Workspace string
	Scope     string
	Path      string
	Roots     *bool
	Start     *float64
	Search    string
	Limit     *float64
}

// Session aliases the generated opencode Session model while keeping generated
// types scoped to transport.
type Session = generated.Session

type Provider = generated.Provider
type ProviderAuthMethod = generated.ProviderAuthMethod
type Agent = generated.Agent
type Model = generated.Model

// QuestionRequest is a pending question that blocks its session until it is
// answered or rejected. It is used to recover sessions left behind by a
// disconnected client.
type QuestionRequest = generated.QuestionRequest

// PermissionRequest is a pending permission request that blocks its session
// until it is answered or rejected.
type PermissionRequest = generated.PermissionRequest

const (
	AgentModeSubagent = generated.AgentModeSubagent
	AgentModePrimary  = generated.AgentModePrimary
	AgentModeAll      = generated.AgentModeAll
)

type ProviderAuthMethods map[string][]ProviderAuthMethod

// ModelOption identifies one model exposed by a connected provider.
type ModelOption struct {
	ProviderID string
	ModelID    string
	Name       string
}

// ConnectedModelOptions returns the models of connected providers in a
// deterministic provider/model order.
func ConnectedModelOptions(providers ProviderList) []ModelOption {
	connected := make(map[string]struct{}, len(providers.Connected))
	for _, id := range providers.Connected {
		connected[id] = struct{}{}
	}
	options := make([]ModelOption, 0)
	for _, provider := range providers.All {
		if _, ok := connected[provider.ID]; !ok {
			continue
		}
		models, _ := ProviderModels(provider)
		for _, model := range models {
			options = append(options, ModelOption{
				ProviderID: provider.ID,
				ModelID:    model.ID,
				Name:       model.Name,
			})
		}
	}
	sort.Slice(options, func(i, j int) bool {
		if options[i].ProviderID != options[j].ProviderID {
			return options[i].ProviderID < options[j].ProviderID
		}
		return options[i].ModelID < options[j].ModelID
	})
	return options
}

// ProviderModels extracts Model objects from a Provider's Models map.
func ProviderModels(p Provider) ([]Model, error) {
	if p.Models == nil {
		return nil, nil
	}
	result := make([]Model, 0, len(p.Models))
	for modelID, raw := range p.Models {
		data, err := json.Marshal(raw)
		if err != nil {
			continue
		}
		var m Model
		if err := json.Unmarshal(data, &m); err != nil {
			continue
		}
		if m.ID == "" {
			m.ID = modelID
		}
		if m.ProviderID == "" {
			m.ProviderID = p.ID
		}
		result = append(result, m)
	}
	return result, nil
}

type CreateSessionRequest struct {
	Directory   string          `json:"-"`
	Workspace   string          `json:"-"`
	ParentID    string          `json:"parentID,omitempty"`
	Title       string          `json:"title,omitempty"`
	Agent       string          `json:"agent,omitempty"`
	Model       *SessionModel   `json:"model,omitempty"`
	Metadata    json.RawMessage `json:"metadata,omitempty"`
	Permission  json.RawMessage `json:"permission,omitempty"`
	WorkspaceID string          `json:"workspaceID,omitempty"`
}

type SessionModel struct {
	ID         string `json:"id,omitempty"`
	ProviderID string `json:"providerID,omitempty"`
	Variant    string `json:"variant,omitempty"`
}

type PromptRequest struct {
	Directory string          `json:"-"`
	Workspace string          `json:"-"`
	MessageID string          `json:"messageID,omitempty"`
	Model     *PromptModel    `json:"model,omitempty"`
	Agent     string          `json:"agent,omitempty"`
	NoReply   *bool           `json:"noReply,omitempty"`
	Tools     map[string]bool `json:"tools,omitempty"`
	Format    json.RawMessage `json:"format,omitempty"`
	System    string          `json:"system,omitempty"`
	Variant   string          `json:"variant,omitempty"`
	Parts     []PromptPart    `json:"parts,omitempty"`
}

type PromptModel struct {
	ProviderID string `json:"providerID"`
	ModelID    string `json:"modelID"`
}

type ProviderDefaults struct {
	Default   map[string]string `json:"default"`
	Connected []string          `json:"connected"`
}

type ProviderList struct {
	All       []Provider        `json:"all"`
	Default   map[string]string `json:"default"`
	Connected []string          `json:"connected"`
}

type PromptPart struct {
	Type string `json:"type"`
	Text string `json:"text,omitempty"`
}

type PermissionDecision struct {
	Reply   string `json:"reply"`
	Message string `json:"message,omitempty"`
}

type EventFilter struct {
	Directory string
	Workspace string
}

type RawEvent struct {
	ID   string
	Type string
	Data []byte
}
