package event

import "encoding/json"

type AppEventKind string

const (
	EventTextDelta       AppEventKind = "text.delta"
	EventReasoningDelta  AppEventKind = "reasoning.delta"
	EventStepStarted     AppEventKind = "step.started"
	EventStepEnded       AppEventKind = "step.ended"
	EventToolCalled      AppEventKind = "tool.called"
	EventToolSucceeded   AppEventKind = "tool.succeeded"
	EventToolFailed      AppEventKind = "tool.failed"
	EventPermissionAsked AppEventKind = "permission.asked"
	EventQuestionAsked   AppEventKind = "question.asked"
	EventSessionIdle     AppEventKind = "session.idle"
	EventUnknown         AppEventKind = "unknown"
)

type AppEvent struct {
	Kind      AppEventKind
	SessionID string
	Payload   any
}

type TextDeltaPayload struct {
	Delta     string
	PartID    string
	MessageID string
}

type ToolCalledPayload struct {
	ToolName string
	CallID   string
	Input    json.RawMessage
	PartID   string
}

type ToolResultPayload struct {
	CallID string
	PartID string
	Output string
	Error  string
}

type StepEndedPayload struct {
	Cost   float64
	Tokens StepTokens
}

type StepTokens struct {
	Input     int
	Output    int
	Reasoning int
}

type PermissionAskedPayload struct {
	RequestID  string
	Permission string
	Patterns   []string
}

type QuestionAskedPayload struct {
	RequestID string
	Questions []QuestionInfo
}

type QuestionInfo struct {
	Question string           `json:"question"`
	Header   string           `json:"header"`
	Options  []QuestionOption `json:"options"`
	Multiple bool             `json:"multiple"`
	Custom   bool             `json:"custom"`
}

type QuestionOption struct {
	Label       string `json:"label"`
	Description string `json:"description"`
}

type UnknownPayload struct {
	Type    string
	Summary string
	Raw     json.RawMessage
}
