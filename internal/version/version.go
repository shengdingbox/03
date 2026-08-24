// Package version 读取应用版本号。
//
// 候选顺序（对应 Python updater.get_current_version）：
//   exe 同级 /src/VERSION、exe 同级 /VERSION、cwd /src/VERSION、cwd /VERSION
//   → 编译期 ldflags 注入值 → "0.0.0"
package version

import (
	"os"
	"path/filepath"
	"strings"
)

// injectedVersion 由构建时 -ldflags "-X buddy.tool/cli/internal/version.injectedVersion=..." 注入。
var injectedVersion = ""

// candidates 返回 VERSION 文件候选路径（exe 同级优先，其次 cwd）。
var candidates = func() []string {
	var paths []string
	if exe, err := os.Executable(); err == nil {
		exeDir := filepath.Dir(exe)
		paths = append(paths,
			filepath.Join(exeDir, "src", "VERSION"),
			filepath.Join(exeDir, "VERSION"),
		)
	}
	if cwd, err := os.Getwd(); err == nil {
		paths = append(paths,
			filepath.Join(cwd, "src", "VERSION"),
			filepath.Join(cwd, "VERSION"),
		)
	}
	return paths
}

// Current 返回当前版本号。
func Current() string {
	for _, p := range candidates() {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		v := strings.TrimSpace(string(data))
		if v != "" {
			return v
		}
	}
	if injectedVersion != "" {
		return injectedVersion
	}
	return "0.0.0"
}
