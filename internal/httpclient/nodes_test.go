package httpclient

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGetNodesSortAndTrim(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"success":true,"data":[
			{"id":"1","name":"节点A","url":"http://x.example/","sortOrder":2,"region":"华南"},
			{"id":"2","name":"节点B","url":"http://y.example","sortOrder":0,"region":"华北"},
			{"id":"3","name":"","url":"http://z.example","sortOrder":1,"region":""}
		]}`)
	}))
	t.Cleanup(srv.Close)
	ServerListURL = srv.URL
	ResetNodeCacheForTest()

	nodes, err := GetNodes(context.Background(), true)
	if err != nil {
		t.Fatal(err)
	}
	if len(nodes) != 3 {
		t.Fatalf("want 3 nodes, got %d", len(nodes))
	}
	// sortOrder 升序
	if nodes[0].SortOrder != 0 || nodes[1].SortOrder != 1 || nodes[2].SortOrder != 2 {
		t.Errorf("not sorted: %+v", nodes)
	}
	// url 剥尾部 /
	if nodes[2].URL != "http://x.example" {
		t.Errorf("url not trimmed: %q", nodes[2].URL)
	}
	// 无 name 用 region，再退 url
	if nodes[0].Name != "节点B" {
		t.Errorf("name wrong: %q", nodes[0].Name)
	}
	if nodes[1].Name != "http://z.example" {
		t.Errorf("name should fallback to url: %q", nodes[1].Name)
	}
}

func TestGetNodesCached(t *testing.T) {
	hit := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hit++
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"success":true,"data":[{"id":"1","name":"A","url":"http://x","sortOrder":0}]}`)
	}))
	t.Cleanup(srv.Close)
	ServerListURL = srv.URL
	ResetNodeCacheForTest()

	if _, err := GetNodes(context.Background(), true); err != nil {
		t.Fatal(err)
	}
	if _, err := GetNodes(context.Background(), false); err != nil {
		t.Fatal(err)
	}
	if _, err := GetNodes(context.Background(), false); err != nil {
		t.Fatal(err)
	}
	if hit != 1 {
		t.Fatalf("expected 1 fetch (cached), got %d", hit)
	}
}

func TestGetServerListURLs(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"success":true,"data":[
			{"id":"1","name":"A","url":"http://a.example/","sortOrder":0},
			{"id":"2","name":"B","url":"http://b.example","sortOrder":1}
		]}`)
	}))
	t.Cleanup(srv.Close)
	ServerListURL = srv.URL
	ResetNodeCacheForTest()

	urls, err := GetServerList(context.Background())
	if err != nil {
		t.Fatal(err)
	}
	if len(urls) != 2 || urls[0] != "http://a.example" || urls[1] != "http://b.example" {
		t.Fatalf("got %v", urls)
	}
}
