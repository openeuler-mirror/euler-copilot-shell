package transport

import (
	"reflect"
	"testing"
)

func TestConnectedModelOptions_FiltersAndSorts(t *testing.T) {
	providers := ProviderList{
		Connected: []string{"deepseek", "opencode"},
		All: []Provider{
			{
				ID: "deepseek",
				Models: map[string]any{
					"deepseek-v4": map[string]any{"id": "deepseek-v4", "name": "DeepSeek V4"},
					"deepseek-v3": map[string]any{"id": "deepseek-v3", "name": "DeepSeek V3"},
				},
			},
			{
				ID: "opencode",
				Models: map[string]any{
					"big-pickle": map[string]any{"id": "big-pickle", "name": "Big Pickle"},
				},
			},
			{
				ID: "unconnected",
				Models: map[string]any{
					"hidden": map[string]any{"id": "hidden", "name": "Hidden"},
				},
			},
		},
	}

	got := ConnectedModelOptions(providers)
	want := []ModelOption{
		{ProviderID: "deepseek", ModelID: "deepseek-v3", Name: "DeepSeek V3"},
		{ProviderID: "deepseek", ModelID: "deepseek-v4", Name: "DeepSeek V4"},
		{ProviderID: "opencode", ModelID: "big-pickle", Name: "Big Pickle"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("ConnectedModelOptions() = %#v, want %#v", got, want)
	}
}

func TestConnectedModelOptions_NoConnected(t *testing.T) {
	got := ConnectedModelOptions(ProviderList{
		All: []Provider{{ID: "deepseek", Models: map[string]any{"m": map[string]any{"id": "m"}}}},
	})
	if len(got) != 0 {
		t.Fatalf("ConnectedModelOptions() = %#v, want empty", got)
	}
}
