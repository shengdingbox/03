package serverapi

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"

	"buddy.tool/cli/internal/httpclient"
)

// newTestServer 起一个测试 HTTP 服务。
//
// 节点列表返回两个节点，url 均指向测试服务自身（这样 credits 请求落在本服务）。
func newTestServer(t *testing.T, creditsFn, modelsFn func(w http.ResponseWriter, r *http.Request)) *httptest.Server {
	t.Helper()
	var srv *httptest.Server
	handler := http.NewServeMux()
	handler.HandleFunc("/api/server_endpoints", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"success":true,"data":[
			{"id":"1","name":"节点A","url":"%s","sortOrder":1,"region":"华南"},
			{"id":"2","name":"节点B","url":"%s","sortOrder":0,"region":"华北"}
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
	return srv
}

// setupServerList 指向测试服务并清空节点缓存。
func setupServerList(t *testing.T, srv *httptest.Server) {
	t.Helper()
	httpclient.ServerListURL = srv.URL + "/api/server_endpoints"
	httpclient.ResetNodeCacheForTest()
}

func TestGetCreditsSuccessOnCreditsKey(t *testing.T) {
	creditsFn := func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("userKey") != "sk-test" {
			t.Errorf("userKey = %q", r.URL.Query().Get("userKey"))
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"credits":1200.5,"totalUsed":300,"totalRecharged":1500,"todayUsed":45,"todayRank":12,"userKey":"sk-test"}`)
	}
	srv := newTestServer(t, creditsFn, nil)
	setupServerList(t, srv)

	data, err := GetCredits(context.Background(), "sk-test")
	if err != nil {
		t.Fatal(err)
	}
	if data["credits"].(float64) != 1200.5 {
		t.Errorf("credits wrong: %v", data["credits"])
	}
	if data["totalUsed"].(float64) != 300 {
		t.Errorf("totalUsed wrong: %v", data["totalUsed"])
	}
}

func TestGetCreditsMissingCreditsKey(t *testing.T) {
	creditsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"error":"账号不存在"}`)
	}
	srv := newTestServer(t, creditsFn, nil)
	setupServerList(t, srv)

	_, err := GetCredits(context.Background(), "sk-x")
	if err == nil {
		t.Fatal("want error")
	}
	if err.Error() != "账号不存在" {
		t.Errorf("error = %q", err.Error())
	}
}

func TestGetCreditsEmptyKey(t *testing.T) {
	_, err := GetCredits(context.Background(), "")
	if err == nil {
		t.Fatal("want error for empty key")
	}
}

func TestGetCreditsNetworkFailover(t *testing.T) {
	// 第一个节点返回 500（连接成功但 JSON 无 credits），第二个节点返回错误 JSON（也无 credits）
	// 为验证 failover，让第二个节点真正成功。
	creditsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"credits":10}`)
	}
	srv := newTestServer(t, creditsFn, nil)
	setupServerList(t, srv)

	data, err := GetCredits(context.Background(), "sk-x")
	if err != nil {
		t.Fatal(err)
	}
	if data["credits"].(float64) != 10 {
		t.Errorf("credits = %v", data["credits"])
	}
}

func TestGetProxyModelsDictData(t *testing.T) {
	modelsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"object":"list","data":[{"id":"glm-5.2","name":"GLM-5.2"},{"id":"hy3"}]}`)
	}
	srv := newTestServer(t, nil, modelsFn)
	ProxyModelsURL = srv.URL + "/api/proxy/models"

	models := GetProxyModels(context.Background())
	if len(models) != 2 {
		t.Fatalf("want 2 models, got %d", len(models))
	}
	if models[0]["id"] != "glm-5.2" {
		t.Errorf("model0 id = %v", models[0]["id"])
	}
}

func TestGetProxyModelsBareList(t *testing.T) {
	modelsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `[{"id":"a"}]`)
	}
	srv := newTestServer(t, nil, modelsFn)
	ProxyModelsURL = srv.URL + "/api/proxy/models"

	models := GetProxyModels(context.Background())
	if len(models) != 1 || models[0]["id"] != "a" {
		t.Fatalf("got %v", models)
	}
}

func TestGetProxyModelsBadFormat(t *testing.T) {
	modelsFn := func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"object":"list","data":"notalist"}`)
	}
	srv := newTestServer(t, nil, modelsFn)
	ProxyModelsURL = srv.URL + "/api/proxy/models"

	models := GetProxyModels(context.Background())
	if models != nil {
		t.Fatalf("want nil, got %v", models)
	}
}

func TestGetProxyModelsServerError(t *testing.T) {
	modelsFn := func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}
	srv := newTestServer(t, nil, modelsFn)
	ProxyModelsURL = srv.URL + "/api/proxy/models"

	models := GetProxyModels(context.Background())
	if models != nil {
		t.Fatalf("want nil on error, got %v", models)
	}
}

// newUsageTestServer 起测试服务，仅注册节点列表与 /v1/usage。
func newUsageTestServer(t *testing.T, usageFn func(w http.ResponseWriter, r *http.Request)) *httptest.Server {
	t.Helper()
	var srv *httptest.Server
	handler := http.NewServeMux()
	handler.HandleFunc("/api/server_endpoints", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"success":true,"data":[{"id":"1","name":"节点A","url":"%s","sortOrder":0,"region":"华南"}]}`, srv.URL)
	})
	handler.HandleFunc("/v1/usage", usageFn)
	srv = httptest.NewServer(handler)
	t.Cleanup(srv.Close)
	setupServerList(t, srv)
	return srv
}

func TestValidateAPIKeyValid(t *testing.T) {
	var gotAuth, gotUA string
	usageFn := func(w http.ResponseWriter, r *http.Request) {
		gotAuth = r.Header.Get("Authorization")
		gotUA = r.Header.Get("User-Agent")
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"is_active":true,"balance":100}`)
	}
	newUsageTestServer(t, usageFn)

	if err := ValidateAPIKey(context.Background(), "sk-valid"); err != nil {
		t.Fatalf("want nil, got %v", err)
	}
	if gotAuth != "Bearer sk-valid" {
		t.Errorf("Authorization = %q", gotAuth)
	}
	if gotUA != "cc-switch/1.0" {
		t.Errorf("User-Agent = %q", gotUA)
	}
}

func TestValidateAPIKeyUnauthorized(t *testing.T) {
	usageFn := func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
	}
	newUsageTestServer(t, usageFn)

	err := ValidateAPIKey(context.Background(), "sk-bad")
	if !errors.Is(err, ErrInvalidKey) {
		t.Fatalf("want ErrInvalidKey, got %v", err)
	}
}

func TestValidateAPIKeyServerError(t *testing.T) {
	usageFn := func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}
	newUsageTestServer(t, usageFn)

	err := ValidateAPIKey(context.Background(), "sk-x")
	if err == nil {
		t.Fatal("want error")
	}
	if errors.Is(err, ErrInvalidKey) {
		t.Errorf("500 不应判定为 Key 无效: %v", err)
	}
}

func TestValidateAPIKeyEmpty(t *testing.T) {
	if err := ValidateAPIKey(context.Background(), ""); err == nil {
		t.Fatal("want error for empty key")
	}
}

// 反序列化验证
func TestCreditsStructMarshal(t *testing.T) {
	b, err := json.Marshal(Credits{Credits: 1, UserKey: "k"})
	if err != nil {
		t.Fatal(err)
	}
	if string(b) != `{"credits":1,"totalUsed":0,"totalRecharged":0,"todayUsed":0,"todayRank":0,"userKey":"k"}` {
		t.Errorf("unexpected: %s", b)
	}
}
