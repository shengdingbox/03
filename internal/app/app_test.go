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
)

// withServer 起测试节点服务器并指向 ServerListURL。
func withServer(t *testing.T, creditsFn, modelsFn func(w http.ResponseWriter, r *http.Request)) *httptest.Server {
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
