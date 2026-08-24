package settings

import (
	"os"
	"path/filepath"
	"testing"
)

func withSettingsFile(t *testing.T, content string) string {
	t.Helper()
	dir := t.TempDir()
	p := filepath.Join(dir, "settings.json")
	if content != "" {
		os.MkdirAll(filepath.Dir(p), 0o755)
		os.WriteFile(p, []byte(content), 0o644)
	}
	old := filePath
	filePath = func() string { return p }
	t.Cleanup(func() { filePath = old })
	return p
}

func TestLoadModelPrefix(t *testing.T) {
	withSettingsFile(t, `{"model_prefix": "p_"}`)
	if got := LoadModelPrefix(); got != "p_" {
		t.Fatalf("want p_, got %q", got)
	}
}

func TestLoadModelPrefixMissing(t *testing.T) {
	withSettingsFile(t, `{}`)
	if got := LoadModelPrefix(); got != "" {
		t.Fatalf("want empty, got %q", got)
	}
}

func TestLoadModelPrefixNoFile(t *testing.T) {
	withSettingsFile(t, "")
	if got := LoadModelPrefix(); got != "" {
		t.Fatalf("want empty, got %q", got)
	}
}

func TestLoadModelPrefixCorrupt(t *testing.T) {
	withSettingsFile(t, `{not json`)
	if got := LoadModelPrefix(); got != "" {
		t.Fatalf("want empty, got %q", got)
	}
}
