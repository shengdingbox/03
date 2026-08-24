// Package httpclient 提供明文 HTTP 客户端与节点列表缓存。
//
// 对应原 Python server_api 的 _plain_session（trust_env=False）与节点缓存。
package httpclient

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"time"
)

// NewClient 返回忽略系统代理的 HTTP 客户端。
//
// Python 用 requests.Session + trust_env=False；Go 通过 Transport.Proxy=nil 实现。
func NewClient() *http.Client {
	return &http.Client{
		Transport: &http.Transport{
			Proxy: nil, // 忽略系统代理（Clash/V2Ray 等）
			DialContext: (&net.Dialer{
				Timeout:   10 * time.Second,
				KeepAlive: 30 * time.Second,
			}).DialContext,
		},
	}
}

// GetJSON 发起 GET 请求并在超时时间内返回，将响应 JSON 反序列化到 v。
func GetJSON(ctx context.Context, client *http.Client, url string, v any) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return err
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	if err := json.NewDecoder(resp.Body).Decode(v); err != nil {
		return fmt.Errorf("解析响应失败: %w", err)
	}
	return nil
}
