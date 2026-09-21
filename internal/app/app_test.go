package app

import (
	"bufio"
	"bytes"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"buddy.tool/cli/internal/httpclient"
	"buddy.tool/cli/internal/serverapi"
)

// withServer 起测试节点服务器并指向 ServerListURL。
//
// usageFn 为 nil 时 /v1/usage 返回 200（校验通过）。
func withServer(t *testing.T, creditsFn, modelsFn func(w http.ResponseWriter, r *http.Request)) *httptest.Server {
	return withUsageServer(t, nil, creditsFn, modelsFn)
}

// withUsageServer 同上，并可自定义 /v1/usage 行为。
func withUsageServer(t *testing.T, usageFn, creditsFn, modelsFn func(w http.ResponseWriter, r *http.Request)) *httptest.Server {
	t.Helper()
	var srv *httptest.Server
	handler := http.NewServeMux()
	handler.HandleFunc("/api/server_endpoints", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"success":true,"data":[
			{"id":"1","name":"北京节点","url":"%s","sortOrder":0,"region":"北京"},
			{"id":"2","name":"上海节点","url":"%s","sortOrder":1,"region":"上海"}
		]}`, srv.URL, srv.URL)
	})
	if usageFn == nil {
		usageFn = func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprint(w, `{"is_active":true,"balance":100}`)
		}
	}
	handler.HandleFunc("/v1/usage", usageFn)
	if creditsFn != nil {
		handler.HandleFunc("/api/user/credits", creditsFn)
	}
	if modelsFn != nil {
		handler.HandleFunc("/api/proxy/models", modelsFn)
	}
	srv = httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	httpclient.ServerListURL = srv.URL + "/api/server_endpoints"
	httpclient.ResetNodeCacheForTest()
	return srv
}

func TestRunHelp(t *testing.T) {
	out := captureStdout(func() {
		if code := Run([]string{"help"}); code != 0 {
			t.Fatalf("help exit=%d", code)
		}
	})
	if !strings.Contains(out, "BuddyToolNew CLI") {
		t.Errorf("help missing title: %s", out)
	}
	for _, cmd := range []string{"info", "credits", "config-workbuddy"} {
		if !strings.Contains(out, cmd) {
			t.Errorf("help missing %s: %s", cmd, out)
		}
	}
}

func TestRunUnknownCommand(t *testing.T) {
	out := captureStdout(func() {
		if code := Run([]string{"nonexist"}); code != 1 {
			t.Fatalf("unknown exit=%d", code)
		}
	})
	if !strings.Contains(out, "未知命令: nonexist") {
		t.Errorf("missing unknown msg: %s", out)
	}
	if !strings.Contains(out, "可用命令") {
		t.Errorf("missing available msg: %s", out)
	}
}

func TestRunInfo(t *testing.T) {
	out := captureStdout(func() {
		if code := Run([]string{"info"}); code != 0 {
			t.Fatalf("info exit=%d", code)
		}
	})
	for _, want := range []string{"当前信息", "版本号", "（未设置）"} {
		if !strings.Contains(out, want) {
			t.Errorf("info missing %q: %s", want, out)
		}
	}
}

func TestInteractiveFlow(t *testing.T) {
	withServer(t, nil, nil)
	// 交互输入: 选择节点回车(默认1) + apikey + 主菜单0退出
	input := "\nsk-demo-key-12345\n0\n"
	s := &Session{reader: bufio.NewReader(strings.NewReader(input))}
	code := s.interactive()
	if code != 0 {
		t.Fatalf("interactive exit=%d", code)
	}
	if s.SessionKey != "sk-demo-key-12345" {
		t.Errorf("session key = %q", s.SessionKey)
	}
	if s.SelectedNodeURL == "" {
		t.Error("selected node url should be set")
	}
}

func TestInteractiveEmptyKeyExits(t *testing.T) {
	s := &Session{reader: bufio.NewReader(strings.NewReader("\n\n"))}
	if code := s.interactive(); code != 0 {
		t.Fatalf("exit=%d", code)
	}
}

// TestLoginPageRetriesOn401 校验 401 时提示 Key 不正确并允许重新输入。
func TestLoginPageRetriesOn401(t *testing.T) {
	usageFn := func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer sk-good" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"is_active":true,"balance":1}`)
	}
	withUsageServer(t, usageFn, nil, nil)

	s := &Session{reader: bufio.NewReader(strings.NewReader("sk-bad\nsk-good\n"))}
	var ok bool
	out := captureStdout(func() { ok = s.loginPage() })
	if !ok {
		t.Fatal("loginPage should succeed after retry")
	}
	if s.SessionKey != "sk-good" {
		t.Errorf("session key = %q", s.SessionKey)
	}
	if !strings.Contains(out, "API Key 不正确，请重新输入") {
		t.Errorf("missing retry hint: %s", out)
	}
}

// TestLoginPageSkipsValidationOnNetworkError 网络异常时不阻塞用户。
func TestLoginPageSkipsValidationOnNetworkError(t *testing.T) {
	srv := withUsageServer(t, nil, nil, nil)
	srv.Close() // 关掉服务，模拟节点不可用

	s := &Session{reader: bufio.NewReader(strings.NewReader("sk-any\n"))}
	out := captureStdout(func() {
		if !s.loginPage() {
			t.Fatal("loginPage should pass through on network error")
		}
	})
	if s.SessionKey != "sk-any" {
		t.Errorf("session key = %q", s.SessionKey)
	}
	if !strings.Contains(out, "跳过校验") {
		t.Errorf("missing skip hint: %s", out)
	}
}

// TestMainMenuExitsAfterConfig 配置成功后直接提示退出，不再回到菜单。
func TestMainMenuExitsAfterConfig(t *testing.T) {
	modelsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"object":"list","data":[{"id":"glm-5.2","name":"GLM-5.2"}]}`)
	}
	srv := withServer(t, nil, modelsFn)
	serverapi.ProxyModelsURL = srv.URL + "/api/proxy/models"

	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)

	// 选择 "1" 配置 WorkBuddy，随后任意键退出
	s := &Session{SessionKey: "sk-key", SelectedNodeURL: srv.URL, reader: bufio.NewReader(strings.NewReader("1\nx"))}
	var exited bool
	out := captureStdout(func() { exited = s.mainMenu() })
	if !exited {
		t.Fatal("mainMenu should return true (exit) after successful config")
	}
	if !strings.Contains(out, "✅ 配置成功") {
		t.Errorf("missing success prompt: %s", out)
	}
	if !strings.Contains(out, "任意键退出脚本") {
		t.Errorf("missing exit prompt: %s", out)
	}
	// 菜单只应渲染一次（配置后不再重复输出菜单）
	if n := strings.Count(out, "BuddyToolNew 菜单"); n != 1 {
		t.Errorf("menu rendered %d times, want 1:\n%s", n, out)
	}
}

// TestMainMenuStaysOnConfigFailure 配置失败（模型列表拉取失败）时保留菜单。
func TestMainMenuStaysOnConfigFailure(t *testing.T) {
	srv := withServer(t, nil, nil) // 未注册 /api/proxy/models → 404
	serverapi.ProxyModelsURL = srv.URL + "/api/proxy/models"

	s := &Session{SessionKey: "sk-key", SelectedNodeURL: srv.URL, reader: bufio.NewReader(strings.NewReader("1\n0\n"))}
	out := captureStdout(func() {
		if !s.mainMenu() {
			t.Fatal("want exit via menu option 0")
		}
	})
	if n := strings.Count(out, "BuddyToolNew 菜单"); n != 2 {
		t.Errorf("menu rendered %d times, want 2 (config failed, then exit):\n%s", n, out)
	}
}

func TestCreditsCommandWithSessionKey(t *testing.T) {
	creditsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"credits":120,"totalUsed":30,"totalRecharged":150,"todayUsed":5,"todayRank":3,"userKey":"k"}`)
	}
	withServer(t, creditsFn, nil)

	s := &Session{SessionKey: "sk-key", reader: bufio.NewReader(strings.NewReader(""))}
	out := captureStdout(func() {
		if code := cmdCredits(s, nil, context.Background()); code != 0 {
			t.Fatalf("credits exit=%d", code)
		}
	})
	for _, want := range []string{"剩余积分: 120", "累计充值: 150", "今日使用: 5", "今日排名: 3"} {
		if !strings.Contains(out, want) {
			t.Errorf("credits missing %q: %s", want, out)
		}
	}
}

// captureStdout 捕获 stdout 输出。
func captureStdout(fn func()) string {
	old := stdout
	var buf bytes.Buffer
	stdout = &buf
	defer func() { stdout = old }()
	fn()
	return buf.String()
}
