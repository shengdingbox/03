// Package modelconfig 生成 WorkBuddy / CodeBuddy 的 models.json 配置。
//
// 对应原 Python src/utils/model_config.py 的纯逻辑部分。
package modelconfig

import (
	"bytes"
	"encoding/json"
	"strings"
)

// ModelEntry 是 models.json 中的一条模型配置。
//
// 固定字段顺序与 Python 的插入序一致（id, name, vendor, apiKey, url,
// maxInputTokens, maxOutputTokens, supportsToolCall, supportsImages,
// supportsReasoning, tags）。Extra 存放服务端下发但未在此列出的字段，
// 序列化时排到 tags 之后，用于增量合并保留旧条目的独有字段。
type ModelEntry struct {
	ID                string
	Name              string
	Vendor            string
	APIKey            string
	URL               string
	MaxInputTokens    int
	MaxOutputTokens   int
	SupportsToolCall  bool
	SupportsImages    bool
	SupportsReasoning bool
	Tags              []string
	Extra             map[string]any
}

// MarshalJSON 输出固定字段序（id…tags），Extra 字段追加在末尾。
func (m ModelEntry) MarshalJSON() ([]byte, error) {
	pairs := [][2]any{
		{"id", m.ID},
		{"name", m.Name},
		{"vendor", m.Vendor},
		{"apiKey", m.APIKey},
		{"url", m.URL},
		{"maxInputTokens", m.MaxInputTokens},
		{"maxOutputTokens", m.MaxOutputTokens},
		{"supportsToolCall", m.SupportsToolCall},
		{"supportsImages", m.SupportsImages},
		{"supportsReasoning", m.SupportsReasoning},
	}
	if len(m.Tags) > 0 {
		pairs = append(pairs, [2]any{"tags", m.Tags})
	}
	for k, v := range m.Extra {
		pairs = append(pairs, [2]any{k, v})
	}
	return marshalOrdered(pairs)
}

// marshalOrdered 将有序键值对序列化为 JSON 对象（保序）。
func marshalOrdered(pairs [][2]any) ([]byte, error) {
	var buf bytes.Buffer
	buf.WriteByte('{')
	for i, kv := range pairs {
		if i > 0 {
			buf.WriteByte(',')
		}
		k, err := json.Marshal(kv[0])
		if err != nil {
			return nil, err
		}
		buf.Write(k)
		buf.WriteByte(':')
		v, err := json.Marshal(kv[1])
		if err != nil {
			return nil, err
		}
		buf.Write(v)
	}
	buf.WriteByte('}')
	return buf.Bytes(), nil
}

// BuildConfigModels 根据服务端模型列表生成 models 配置。
//
// 对应 Python build_config_models(api_key, server_models, upstream_base, prefix)。
// 返回生成的条目列表。
func BuildConfigModels(apiKey string, serverModels []map[string]any, upstreamBase, prefix string) []ModelEntry {
	url := strings.TrimRight(upstreamBase, "/") + "/v1/chat/completions"
	var models []ModelEntry
	for _, m := range serverModels {
		id, _ := m["id"].(string)
		if id == "" {
			continue
		}
		name, _ := m["name"].(string)
		if name == "" {
			name = id
		}
		if prefix != "" {
			id = prefix + id
			name = prefix + name
		}
		entry := ModelEntry{
			ID:                id,
			Name:              name,
			Vendor:            getString(m, "vendor", "Buddy"),
			APIKey:            apiKey,
			URL:               url,
			MaxInputTokens:    getInt(m, "maxInputTokens", 128000),
			MaxOutputTokens:   getInt(m, "maxOutputTokens", 8192),
			SupportsToolCall:  getBool(m, "supportsToolCall", true),
			SupportsImages:    getBool(m, "supportsImages", true),
			SupportsReasoning: getBool(m, "supportsReasoning", true),
		}
		if tags := formatTags(m["tags"]); len(tags) > 0 {
			entry.Tags = tags
		}
		models = append(models, entry)
	}
	return models
}

// formatTags 将服务端 tags 转为 badge 格式。
//
// 输入 [{"color":"#724bff","text":"高消耗"}, ...] 或 ["字符串"] 或 nil。
// 输出 ["badge:高消耗:#724bff", ...]。
func formatTags(tags any) []string {
	list, ok := tags.([]any)
	if !ok {
		return nil
	}
	var out []string
	for _, t := range list {
		switch v := t.(type) {
		case map[string]any:
			text, _ := v["text"].(string)
			if strings.TrimSpace(text) == "" {
				continue
			}
			color, _ := v["color"].(string)
			if color != "" {
				out = append(out, "badge:"+text+":"+color)
			} else {
				out = append(out, "badge:"+text)
			}
		case string:
			if strings.TrimSpace(v) != "" {
				out = append(out, strings.TrimSpace(v))
			}
		}
	}
	return out
}

func getString(m map[string]any, key, def string) string {
	if v, ok := m[key].(string); ok && v != "" {
		return v
	}
	return def
}

func getInt(m map[string]any, key string, def int) int {
	switch v := m[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	}
	return def
}

func getBool(m map[string]any, key string, def bool) bool {
	if v, ok := m[key].(bool); ok {
		return v
	}
	return def
}
