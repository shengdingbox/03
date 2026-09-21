// Package httpclient 提供明文 HTTP 客户端与节点列表缓存。
//
// 对应原 Python server_api 的 _plain_session（trust_env=False）与节点缓存。
package httpclient

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"time"
)

// UserAgent API 请求标识（与客户端保持一致）。
const UserAgent = "cc-switch/1.0"

// GetJSONStatus 与 GetJSON 相同，但额外返回 HTTP 状态码。
//
// ctx 超时在响应头返回后即失效，正文读取前用限时 context 兜底，避免响应体挂起。
func GetJSONStatus(ctx context.Context, client *http.Client, url, bearer string, v any) (int, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return 0, err
	}
	if bearer != "" {
		req.Header.Set("Authorization", "Bearer "+bearer)
	}
	req.Header.Set("User-Agent", UserAgent)

	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBodyBytes))
	if err != nil {
		return resp.StatusCode, err
	}
	if len(body) == 0 {
		return resp.StatusCode, nil
	}
	if err := json.Unmarshal(body, v); err != nil {
		return resp.StatusCode, fmt.Errorf("解析响应失败: %w", err)
	}
	return resp.StatusCode, nil
}

// maxBodyBytes 限制响应体读取上限，避免异常响应耗尽内存。
const maxBodyBytes = 4 << 20

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
