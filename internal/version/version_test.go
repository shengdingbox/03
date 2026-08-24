package version

import (
	"os"
	"path/filepath"
	"testing"
)

func withCandidates(t *testing.T, paths map[string]string) {
	t.Helper()
	old := candidates
	candidates = func() []string {
		var out []string
		for p := range paths {
			out = append(out, p)
		}
		return out
	}
	t.Cleanup(func() { candidates = old })
	// 写入测试文件
	for p, content := range paths {
		os.MkdirAll(filepath.Dir(p), 0o755)
		os.WriteFile(p, []byte(content), 0o644)
	}
}

func TestCurrentReadsVersionFile(t *testing.T) {
	dir := t.TempDir()
	withCandidates(t, map[string]string{
		filepath.Join(dir, "VERSION"): "9.9.9",
	})
	if got := Current(); got != "9.9.9" {
		t.Fatalf("want 9.9.9, got %q", got)
	}
}

func TestCurrentEmptyFileFallsThrough(t *testing.T) {
	dir := t.TempDir()
	withCandidates(t, map[string]string{
		filepath.Join(dir, "VERSION"): "   ",
		filepath.Join(dir, "src", "VERSION"): "1.2.3",
	})
	if got := Current(); got != "1.2.3" {
		t.Fatalf("want 1.2.3, got %q", got)
	}
}

func TestCurrentInjectedFallback(t *testing.T) {
	withCandidates(t, map[string]string{})
	old := injectedVersion
	injectedVersion = "7.7.7"
	t.Cleanup(func() { injectedVersion = old })
	if got := Current(); got != "7.7.7" {
		t.Fatalf("want 7.7.7, got %q", got)
	}
}

func TestCurrentZeroZeroZero(t *testing.T) {
	withCandidates(t, map[string]string{})
	old := injectedVersion
	injectedVersion = ""
	t.Cleanup(func() { injectedVersion = old })
	if got := Current(); got != "0.0.0" {
		t.Fatalf("want 0.0.0, got %q", got)
	}
}
