// Package settings 读取本地设置。
//
// 替代原 Python SQLite settings 表（CLI 只读 model_prefix 一个键，从不写）。
// 存储为 ~/.buddytoolnew/settings.json。
package settings

import (
	"encoding/json"
	"os"
	"path/filepath"
)

// Settings 本地设置结构。
type Settings struct {
	ModelPrefix string `json:"model_prefix"`
}

// filePathVar 返回 settings.json 路径；测试可覆盖。
var filePath = func() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return ""
	}
	return filepath.Join(home, ".buddytoolnew", "settings.json")
}

// Load 读取本地设置；文件不存在或解析失败时返回空结构。
func Load() Settings {
	p := filePath()
	if p == "" {
		return Settings{}
	}
	data, err := os.ReadFile(p)
	if err != nil {
		return Settings{}
	}
	var s Settings
	if err := json.Unmarshal(data, &s); err != nil {
		return Settings{}
	}
	return s
}

// LoadModelPrefix 返回 model_prefix 设置；未设置时返回空串。
func LoadModelPrefix() string {
	return Load().ModelPrefix
}
