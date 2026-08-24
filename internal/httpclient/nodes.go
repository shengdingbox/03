package httpclient

import (
	"context"
	"sort"
	"strings"
	"sync"
	"time"
)

// ServerListURL 服务端节点列表地址（测试可覆盖）。
var ServerListURL = "https://buddy.shengdingit.com/api/server_endpoints"

// ServerListTTL 节点列表缓存有效期（10 分钟）。
const ServerListTTL = 600 * time.Second

// Node 服务端节点。
type Node struct {
	ID        string
	Name      string
	URL       string
	Region    string
	SortOrder int
}

var (
	nodeCache    []Node
	nodeExpire   time.Time
	nodeCacheMu  sync.Mutex
	nodeClient   = NewClient()
)

// GetNodes 获取服务端节点列表，按 sortOrder 升序排序，缓存 TTL 内复用。
//
// forceRefresh 为 true 时强制刷新缓存。远程失败时有旧缓存则用旧缓存，否则返回错误。
func GetNodes(ctx context.Context, forceRefresh bool) ([]Node, error) {
	nodeCacheMu.Lock()
	defer nodeCacheMu.Unlock()

	now := time.Now()
	if !forceRefresh && nodeCache != nil && now.Before(nodeExpire) {
		return nodeCache, nil
	}

	nodes, err := fetchNodes(ctx)
	if err == nil && len(nodes) > 0 {
		nodeCache = nodes
		nodeExpire = now.Add(ServerListTTL)
		return nodes, nil
	}

	// 远程失败且有旧缓存，继续用旧缓存
	if nodeCache != nil {
		return nodeCache, nil
	}
	if err != nil {
		return nil, err
	}
	return nil, nil
}

// GetServerList 返回节点 url 字符串列表。
func GetServerList(ctx context.Context) ([]string, error) {
	nodes, err := GetNodes(ctx, false)
	if err != nil {
		return nil, err
	}
	urls := make([]string, 0, len(nodes))
	for _, n := range nodes {
		urls = append(urls, n.URL)
	}
	return urls, nil
}

// ResetNodeCacheForTest 清空节点缓存（测试用）。
func ResetNodeCacheForTest() {
	nodeCacheMu.Lock()
	defer nodeCacheMu.Unlock()
	nodeCache = nil
	nodeExpire = time.Time{}
}

func fetchNodes(ctx context.Context) ([]Node, error) {
	var resp struct {
		Data []struct {
			ID        string `json:"id"`
			Name      string `json:"name"`
			URL       string `json:"url"`
			SortOrder int    `json:"sortOrder"`
			Region    string `json:"region"`
		} `json:"data"`
	}
	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	if err := GetJSON(ctx, nodeClient, ServerListURL, &resp); err != nil {
		return nil, err
	}

	var nodes []Node
	for _, it := range resp.Data {
		url := strings.TrimSpace(it.URL)
		url = strings.TrimRight(url, "/")
		if url == "" {
			continue
		}
		name := it.Name
		if name == "" {
			name = it.Region
		}
		if name == "" {
			name = url
		}
		nodes = append(nodes, Node{
			ID:        it.ID,
			Name:      strings.TrimSpace(name),
			URL:       url,
			Region:    strings.TrimSpace(it.Region),
			SortOrder: it.SortOrder,
		})
	}
	sort.Slice(nodes, func(i, j int) bool { return nodes[i].SortOrder < nodes[j].SortOrder })
	return nodes, nil
}
