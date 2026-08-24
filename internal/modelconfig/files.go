package modelconfig

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// 路径常量（对应 Python model_config 模块级常量）。
var (
	WorkbuddyPath = func() string {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, ".workbuddy", "models.json")
	}()
	CodebuddyPath = func() string {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, ".codebuddy", "models.json")
	}()
	BackupDir = func() string {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, ".buddytoolnew", "config_backups")
	}()
)

// TargetPath 返回指定客户端的 models.json 路径。
func TargetPath(client string) string {
	if client == "workbuddy" {
		return WorkbuddyPath
	}
	return CodebuddyPath
}

// ReadExisting 读取 models.json 中已有的模型列表。
//
// 兼容两种格式：WorkBuddy 裸数组、CodeBuddy 包裹对象 {"models":[...]}。
// 文件不存在或解析失败时返回空列表（不报错）。
func ReadExisting(targetPath string) ([]ModelEntry, error) {
	data, err := os.ReadFile(targetPath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil
		}
		return nil, nil // 解析/读取失败同样返回空，对应 Python return []
	}
	var raw any
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, nil
	}
	switch v := raw.(type) {
	case []any:
		return anyToEntries(v), nil
	case map[string]any:
		if models, ok := v["models"].([]any); ok {
			return anyToEntries(models), nil
		}
	}
	return nil, nil
}

// anyToEntries 把 []any 转为 []ModelEntry（保留 Extra 字段）。
func anyToEntries(list []any) []ModelEntry {
	entries := make([]ModelEntry, 0, len(list))
	for _, item := range list {
		m, ok := item.(map[string]any)
		if !ok {
			continue
		}
		entries = append(entries, entryFromMap(m))
	}
	return entries
}

// entryFromMap 把 JSON 对象转为 ModelEntry，未列出的键进 Extra。
func entryFromMap(m map[string]any) ModelEntry {
	e := ModelEntry{
		Extra: map[string]any{},
	}
	known := map[string]bool{}
	assign := func(key string, dst *string) {
		if v, ok := m[key].(string); ok {
			*dst = v
			known[key] = true
		}
	}
	assign("id", &e.ID)
	assign("name", &e.Name)
	assign("vendor", &e.Vendor)
	assign("apiKey", &e.APIKey)
	assign("url", &e.URL)
	if v, ok := m["maxInputTokens"].(float64); ok {
		e.MaxInputTokens = int(v)
		known["maxInputTokens"] = true
	}
	if v, ok := m["maxOutputTokens"].(float64); ok {
		e.MaxOutputTokens = int(v)
		known["maxOutputTokens"] = true
	}
	for _, key := range []string{"supportsToolCall", "supportsImages", "supportsReasoning"} {
		if v, ok := m[key].(bool); ok {
			switch key {
			case "supportsToolCall":
				e.SupportsToolCall = v
			case "supportsImages":
				e.SupportsImages = v
			case "supportsReasoning":
				e.SupportsReasoning = v
			}
			known[key] = true
		}
	}
	if v, ok := m["tags"].([]any); ok {
		var tags []string
		for _, t := range v {
			if s, ok := t.(string); ok {
				tags = append(tags, s)
			}
		}
		e.Tags = tags
		known["tags"] = true
	}
	for k, v := range m {
		if !known[k] {
			e.Extra[k] = v
		}
	}
	return e
}

// IncrementalMerge 增量合并模型列表。
//
// 匹配规则：id 与 name 都相同视为同一模型：
//   - 命中：旧条目为底，新字段覆盖，旧条目独有字段（Extra）保留，replaced+1
//   - 未命中：追加到末尾，added+1
func IncrementalMerge(existing, newEntries []ModelEntry) (merged []ModelEntry, replaced, added int) {
	merged = append(merged, existing...)
	// (id, name) -> 首次出现索引
	index := map[string]int{}
	for i, m := range merged {
		key := mergeKey(m.ID, m.Name)
		if _, ok := index[key]; !ok {
			index[key] = i
		}
	}
	for _, entry := range newEntries {
		key := mergeKey(entry.ID, entry.Name)
		if idx, ok := index[key]; ok {
			base := merged[idx]
			// 旧 Extra 与新 Extra 合并：新覆盖同名键
			if entry.Extra == nil {
				entry.Extra = map[string]any{}
			}
			for k, v := range base.Extra {
				if _, ok := entry.Extra[k]; !ok {
					entry.Extra[k] = v
				}
			}
			merged[idx] = entry
			replaced++
		} else {
			merged = append(merged, entry)
			index[key] = len(merged) - 1
			added++
		}
	}
	return merged, replaced, added
}

func mergeKey(id, name string) string {
	return strings.TrimSpace(id) + "\x00" + strings.TrimSpace(name)
}

// WriteClientConfig 写入客户端 models.json（自动备份原文件）。
//
// 返回目标路径。
func WriteClientConfig(client string, merged []ModelEntry) (string, error) {
	BackupConfig(client)
	target := TargetPath(client)
	wrapper := "array"
	if client != "workbuddy" {
		wrapper = "object"
	}
	if err := writeModelsJSON(target, merged, wrapper); err != nil {
		return "", err
	}
	return target, nil
}

// BackupConfig 备份目标客户端的 models.json 到备份目录。
//
// 无原文件时返回空串，不报错。
func BackupConfig(client string) string {
	src := TargetPath(client)
	if _, err := os.Stat(src); err != nil {
		return ""
	}
	if err := os.MkdirAll(BackupDir, 0o755); err != nil {
		return ""
	}
	ts := time.Now().Format("20060102_150405")
	dst := filepath.Join(BackupDir, fmt.Sprintf("%s_%s.json", client, ts))
	if err := copyFile(src, dst); err != nil {
		return ""
	}
	return dst
}

// RestoreConfig 从备份目录还原指定客户端最近一次备份。
//
// 返回还原目标路径；无备份时返回错误（对应 Python FileNotFoundError）。
func RestoreConfig(client string) (string, error) {
	if _, err := os.Stat(BackupDir); err != nil {
		return "", fmt.Errorf("备份目录不存在: %s", BackupDir)
	}
	prefix := client + "_"
	var backups []string
	entries, _ := os.ReadDir(BackupDir)
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		if strings.HasPrefix(e.Name(), prefix) && strings.HasSuffix(e.Name(), ".json") {
			backups = append(backups, filepath.Join(BackupDir, e.Name()))
		}
	}
	if len(backups) == 0 {
		return "", fmt.Errorf("未找到 %s 的备份文件", client)
	}
	sort.Slice(backups, func(i, j int) bool {
		si, _ := os.Stat(backups[i])
		sj, _ := os.Stat(backups[j])
		return si.ModTime().After(sj.ModTime())
	})
	target := TargetPath(client)
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return "", err
	}
	if err := copyFile(backups[0], target); err != nil {
		return "", err
	}
	return target, nil
}

func writeModelsJSON(target string, merged []ModelEntry, wrapper string) error {
	if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
		return err
	}
	var data []byte
	var err error
	if wrapper == "object" {
		data, err = json.MarshalIndent(map[string]any{"models": merged}, "", "  ")
	} else {
		data, err = json.MarshalIndent(merged, "", "  ")
	}
	if err != nil {
		return err
	}
	return os.WriteFile(target, data, 0o644)
}

func copyFile(src, dst string) error {
	data, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	return os.WriteFile(dst, data, 0o644)
}
