package modelconfig

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBuildConfigModelsDefaults(t *testing.T) {
	server := []map[string]any{
		{"id": "glm-5.2", "name": "GLM-5.2", "vendor": "Buddy",
			"maxInputTokens": 128000, "maxOutputTokens": 8192},
	}
	models := BuildConfigModels("sk-test", server, "https://node.example", "")
	if len(models) != 1 {
		t.Fatalf("want 1 model, got %d", len(models))
	}
	e := models[0]
	if e.ID != "glm-5.2" || e.Name != "GLM-5.2" {
		t.Errorf("id/name wrong: %+v", e)
	}
	if e.Vendor != "Buddy" {
		t.Errorf("vendor default wrong: %q", e.Vendor)
	}
	if e.URL != "https://node.example/v1/chat/completions" {
		t.Errorf("url wrong: %q", e.URL)
	}
	if e.APIKey != "sk-test" {
		t.Errorf("apiKey wrong: %q", e.APIKey)
	}
	if e.MaxInputTokens != 128000 || e.MaxOutputTokens != 8192 {
		t.Errorf("token limits wrong: %+v", e)
	}
	if !e.SupportsToolCall || !e.SupportsImages || !e.SupportsReasoning {
		t.Errorf("capabilities should default true: %+v", e)
	}
}

func TestBuildConfigModelsSkippingNoID(t *testing.T) {
	server := []map[string]any{
		{"id": "a"},
		{"name": "no-id"},
		{},
	}
	models := BuildConfigModels("k", server, "http://x", "")
	if len(models) != 1 {
		t.Fatalf("want 1 model, got %d", len(models))
	}
	if models[0].ID != "a" {
		t.Errorf("id wrong: %q", models[0].ID)
	}
}

func TestBuildConfigModelsPrefix(t *testing.T) {
	server := []map[string]any{{"id": "glm-5.2", "name": "GLM-5.2"}}
	models := BuildConfigModels("k", server, "http://x", "p_")
	if models[0].ID != "p_glm-5.2" || models[0].Name != "p_GLM-5.2" {
		t.Errorf("prefix not applied: %+v", models[0])
	}
}

func TestBuildConfigModelsTags(t *testing.T) {
	server := []map[string]any{{
		"id": "m1",
		"tags": []any{
			map[string]any{"color": "#7900c6", "text": "官方推荐"},
			map[string]any{"text": "低消耗"},
			"plain",
		},
	}}
	models := BuildConfigModels("k", server, "http://x", "")
	if len(models[0].Tags) != 3 {
		t.Fatalf("want 3 tags, got %v", models[0].Tags)
	}
	if models[0].Tags[0] != "badge:官方推荐:#7900c6" {
		t.Errorf("tag0 wrong: %q", models[0].Tags[0])
	}
	if models[0].Tags[1] != "badge:低消耗" {
		t.Errorf("tag1 wrong: %q", models[0].Tags[1])
	}
	if models[0].Tags[2] != "plain" {
		t.Errorf("tag2 wrong: %q", models[0].Tags[2])
	}
}

func TestBuildConfigModelsNoTags(t *testing.T) {
	server := []map[string]any{{"id": "m1"}}
	models := BuildConfigModels("k", server, "http://x", "")
	if models[0].Tags != nil {
		t.Errorf("tags should be nil, got %v", models[0].Tags)
	}
	b, _ := json.Marshal(models[0])
	if strings.Contains(string(b), "tags") {
		t.Errorf("tags field should be omitted, got %s", b)
	}
}

func TestFormatTags(t *testing.T) {
	cases := []struct {
		name string
		in   any
		want []string
	}{
		{"nil", nil, nil},
		{"empty", []any{}, nil},
		{"dict-with-color", []any{map[string]any{"color": "#724bff", "text": "高消耗"}}, []string{"badge:高消耗:#724bff"}},
		{"dict-no-color", []any{map[string]any{"text": "高消耗"}}, []string{"badge:高消耗"}},
		{"dict-empty-text", []any{map[string]any{"text": ""}}, nil},
		{"string", []any{"abc"}, []string{"abc"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := formatTags(c.in)
			if len(got) != len(c.want) {
				t.Fatalf("want %v, got %v", c.want, got)
			}
			for i := range got {
				if got[i] != c.want[i] {
					t.Errorf("want %v, got %v", c.want, got)
				}
			}
		})
	}
}

func TestIncrementalMergeReplaceWithFieldMerge(t *testing.T) {
	existing := []ModelEntry{
		{ID: "glm-5.2", Name: "glm-5.2", URL: "http://old/v1", Extra: map[string]any{"favorite": true}},
	}
	newEntries := []ModelEntry{
		{ID: "glm-5.2", Name: "glm-5.2", URL: "http://new/v1", APIKey: "sk-new"},
	}
	merged, replaced, added := IncrementalMerge(existing, newEntries)
	if replaced != 1 || added != 0 || len(merged) != 1 {
		t.Fatalf("replaced=%d added=%d len=%d", replaced, added, len(merged))
	}
	e := merged[0]
	if e.URL != "http://new/v1" || e.APIKey != "sk-new" {
		t.Errorf("new fields not applied: %+v", e)
	}
	if e.Extra["favorite"] != true {
		t.Errorf("old unique field not preserved: %+v", e.Extra)
	}
}

func TestIncrementalMergeAppendWhenNotExist(t *testing.T) {
	existing := []ModelEntry{{ID: "a", Name: "a"}}
	newEntries := []ModelEntry{{ID: "b", Name: "b"}}
	merged, replaced, added := IncrementalMerge(existing, newEntries)
	if replaced != 0 || added != 1 || len(merged) != 2 {
		t.Fatalf("replaced=%d added=%d len=%d", replaced, added, len(merged))
	}
}

func TestIncrementalMergePreservesUnselected(t *testing.T) {
	existing := []ModelEntry{
		{ID: "glm-5.2", Name: "glm-5.2"},
		{ID: "user-custom", Name: "我的自定义模型", URL: "http://x"},
	}
	newEntries := []ModelEntry{{ID: "glm-5.2", Name: "glm-5.2", APIKey: "sk"}}
	merged, replaced, added := IncrementalMerge(existing, newEntries)
	if replaced != 1 || added != 0 || len(merged) != 2 {
		t.Fatalf("replaced=%d added=%d len=%d", replaced, added, len(merged))
	}
	custom := merged[1]
	if custom.ID != "user-custom" || custom.Name != "我的自定义模型" || custom.URL != "http://x" {
		t.Errorf("custom not preserved: %+v", custom)
	}
}

func TestIncrementalMergeSameIDDifferentNameAppends(t *testing.T) {
	existing := []ModelEntry{{ID: "glm-5.2", Name: "glm-5.2"}}
	newEntries := []ModelEntry{{ID: "glm-5.2", Name: "GLM-5.2"}}
	merged, replaced, added := IncrementalMerge(existing, newEntries)
	if replaced != 0 || added != 1 || len(merged) != 2 {
		t.Fatalf("replaced=%d added=%d len=%d", replaced, added, len(merged))
	}
}

func TestIncrementalMergeEmptyExisting(t *testing.T) {
	newEntries := []ModelEntry{{ID: "a", Name: "a"}, {ID: "b", Name: "b"}}
	merged, replaced, added := IncrementalMerge(nil, newEntries)
	if replaced != 0 || added != 2 || len(merged) != 2 {
		t.Fatalf("replaced=%d added=%d len=%d", replaced, added, len(merged))
	}
}

func TestReadExistingBareArray(t *testing.T) {
	p := filepath.Join(t.TempDir(), "models.json")
	os.WriteFile(p, []byte(`[{"id":"a","name":"a"}]`), 0o644)
	entries, _ := ReadExisting(p)
	if len(entries) != 1 || entries[0].ID != "a" {
		t.Fatalf("got %+v", entries)
	}
}

func TestReadExistingWrappedObject(t *testing.T) {
	p := filepath.Join(t.TempDir(), "models.json")
	os.WriteFile(p, []byte(`{"models":[{"id":"b","name":"b"}]}`), 0o644)
	entries, _ := ReadExisting(p)
	if len(entries) != 1 || entries[0].ID != "b" {
		t.Fatalf("got %+v", entries)
	}
}

func TestReadExistingMissingFile(t *testing.T) {
	entries, _ := ReadExisting(filepath.Join(t.TempDir(), "nope.json"))
	if len(entries) != 0 {
		t.Fatalf("want empty, got %+v", entries)
	}
}

func TestReadExistingCorruptFile(t *testing.T) {
	p := filepath.Join(t.TempDir(), "models.json")
	os.WriteFile(p, []byte("{not valid json"), 0o644)
	entries, _ := ReadExisting(p)
	if len(entries) != 0 {
		t.Fatalf("want empty, got %+v", entries)
	}
}

func TestWriteClientConfigWorkbuddyArray(t *testing.T) {
	// 覆盖路径常量，指向临时目录
	oldWB, oldCB := WorkbuddyPath, CodebuddyPath
	oldBD := BackupDir
	t.Cleanup(func() {
		WorkbuddyPath, CodebuddyPath, BackupDir = oldWB, oldCB, oldBD
	})
	tmp := t.TempDir()
	WorkbuddyPath = filepath.Join(tmp, "wb", "models.json")
	CodebuddyPath = filepath.Join(tmp, "cb", "models.json")
	BackupDir = filepath.Join(tmp, "backups")

	merged := []ModelEntry{{ID: "a", Name: "a"}}
	if _, err := WriteClientConfig("workbuddy", merged); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(WorkbuddyPath)
	var raw any
	json.Unmarshal(data, &raw)
	if _, ok := raw.([]any); !ok {
		t.Fatalf("workbuddy should be bare array, got %s", data)
	}
}

func TestWriteClientConfigCodebuddyObject(t *testing.T) {
	oldWB, oldCB := WorkbuddyPath, CodebuddyPath
	oldBD := BackupDir
	t.Cleanup(func() {
		WorkbuddyPath, CodebuddyPath, BackupDir = oldWB, oldCB, oldBD
	})
	tmp := t.TempDir()
	WorkbuddyPath = filepath.Join(tmp, "wb", "models.json")
	CodebuddyPath = filepath.Join(tmp, "cb", "models.json")
	BackupDir = filepath.Join(tmp, "backups")

	merged := []ModelEntry{{ID: "a", Name: "a"}}
	if _, err := WriteClientConfig("codebuddy", merged); err != nil {
		t.Fatal(err)
	}
	data, _ := os.ReadFile(CodebuddyPath)
	var m map[string]any
	json.Unmarshal(data, &m)
	if _, ok := m["models"].([]any); !ok {
		t.Fatalf("codebuddy should be wrapped object, got %s", data)
	}
}

func TestMarshalJSONFieldOrder(t *testing.T) {
	e := ModelEntry{
		ID: "x", Name: "y", Vendor: "Buddy", APIKey: "k", URL: "http://u",
		MaxInputTokens: 1, MaxOutputTokens: 2,
		SupportsToolCall: true, SupportsImages: true, SupportsReasoning: true,
		Tags: []string{"badge:a"},
		Extra: map[string]any{"favorite": true},
	}
	b, err := json.Marshal(e)
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	order := []string{`"id"`, `"name"`, `"vendor"`, `"apiKey"`, `"url"`,
		`"maxInputTokens"`, `"maxOutputTokens"`, `"supportsToolCall"`,
		`"supportsImages"`, `"supportsReasoning"`, `"tags"`, `"favorite"`}
	pos := -1
	for _, key := range order {
		idx := strings.Index(s, key)
		if idx == -1 {
			t.Fatalf("key %s not in %s", key, s)
		}
		if idx < pos {
			t.Fatalf("field order wrong for %s in %s", key, s)
		}
		pos = idx
	}
}

func TestEndToEndConfig(t *testing.T) {
	oldWB, oldCB := WorkbuddyPath, CodebuddyPath
	oldBD := BackupDir
	t.Cleanup(func() {
		WorkbuddyPath, CodebuddyPath, BackupDir = oldWB, oldCB, oldBD
	})
	tmp := t.TempDir()
	WorkbuddyPath = filepath.Join(tmp, "wb", "models.json")
	BackupDir = filepath.Join(tmp, "backups")

	// 预置现有配置：一个会被替换的模型 + 一个自定义模型
	existing := []ModelEntry{
		{ID: "glm-5.2", Name: "glm-5.2", URL: "http://old/v1", Extra: map[string]any{"note": "keep"}},
		{ID: "my-model", Name: "我的模型", URL: "http://x"},
	}
	os.MkdirAll(filepath.Dir(WorkbuddyPath), 0o755)
	data, _ := json.MarshalIndent(existing, "", "  ")
	os.WriteFile(WorkbuddyPath, data, 0o644)

	server := []map[string]any{
		{"id": "glm-5.2", "name": "glm-5.2"},
		{"id": "hy3", "name": "Hy3"},
	}
	models := BuildConfigModels("sk-new", server, "http://127.0.0.1:8080", "")
	current, _ := ReadExisting(WorkbuddyPath)
	merged, replaced, added := IncrementalMerge(current, models)
	if _, err := WriteClientConfig("workbuddy", merged); err != nil {
		t.Fatal(err)
	}

	final, _ := ReadExisting(WorkbuddyPath)
	byID := map[string]ModelEntry{}
	for _, e := range final {
		byID[e.ID] = e
	}
	if _, ok := byID["glm-5.2"]; !ok {
		t.Fatal("glm-5.2 missing after merge")
	}
	if _, ok := byID["hy3"]; !ok {
		t.Fatal("hy3 missing after merge")
	}
	if _, ok := byID["my-model"]; !ok {
		t.Fatal("my-model should be preserved")
	}
	if replaced != 1 || added != 1 {
		t.Fatalf("replaced=%d added=%d", replaced, added)
	}
	g := byID["glm-5.2"]
	if g.URL != "http://127.0.0.1:8080/v1/chat/completions" {
		t.Errorf("url not updated: %q", g.URL)
	}
	if g.Extra["note"] != "keep" {
		t.Errorf("old field note not preserved: %+v", g.Extra)
	}
	if !g.SupportsImages {
		t.Error("supportsImages should be true")
	}
}
