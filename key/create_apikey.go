// create_apikey.go
//
// 用法:
//   go run create_apikey.go
//
// 运行时会提示输入 Cookie 值（curl 中的 Cookie 头），然后向
// https://www.codebuddy.cn/console/api/client/v1/api-keys 发送 POST 请求创建 API Key。
//
// 说明:
//   - 显式禁用系统/环境代理（绕过代理），直连目标主机。
//   - Cookie 由运行时标准输入读取，避免硬编码。
//   - 可通过命令行参数自定义 name 与 user_enterprise_id，默认值与原 curl 一致。

package main

import (
	"bufio"
	"bytes"
	"crypto/tls"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const (
	defaultName              = "1212131"
	defaultUserEnterpriseID  = "personal-edition-user-id"
	apiKeyEndpoint           = "https://www.codebuddy.cn/console/api/client/v1/api-keys"
	defaultTimeoutSeconds    = 30
)

// buildHTTPClient 构造一个绕过系统代理的 HTTP 客户端。
// 关键点:
//   1. Transport.Proxy 始终返回 nil，忽略 HTTP_PROXY/HTTPS_PROXY 等环境变量。
//   2. Transport.DialContext 使用直连拨号器，避免任何代理介入。
//   3. 跳过 TLS 证书校验失败时的额外拦截（保持默认校验，仅显式指定 TLS 配置）。
func buildHTTPClient(timeout time.Duration) *http.Client {
	dialer := &net.Dialer{
		Timeout:   30 * time.Second,
		KeepAlive: 30 * time.Second,
	}

	transport := &http.Transport{
		// 强制不走代理 —— Proxy 始终返回 nil
		Proxy: func(*http.Request) (*url.URL, error) {
			return nil, nil
		},
		DialContext:           dialer.DialContext,
		ForceAttemptHTTP2:     true,
		MaxIdleConns:          10,
		IdleConnTimeout:       90 * time.Second,
		TLSHandshakeTimeout:   15 * time.Second,
		ExpectContinueTimeout: 1 * time.Second,
		TLSClientConfig: &tls.Config{
			MinVersion: tls.VersionTLS12,
		},
	}

	return &http.Client{
		Transport: transport,
		Timeout:   timeout,
	}
}

// readCookieFromStdin 从标准输入读取 Cookie 值。
// 支持两种输入方式:
//   1. 直接粘贴完整的 "Cookie: xxx" 头部行;
//   2. 仅粘贴 Cookie 值本身。
// 自动去除首尾空白和两端可能存在的引号。
func readCookieFromStdin() (string, error) {
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("请输入 Cookie 值（粘贴整行 Cookie 头或仅值，回车结束）:\n> ")

	line, err := reader.ReadString('\n')
	if err != nil && err != io.EOF {
		return "", fmt.Errorf("读取输入失败: %w", err)
	}

	line = strings.TrimSpace(line)

	// 若用户粘贴了 "Cookie:  xxx" 形式，去掉前缀
	if strings.HasPrefix(strings.ToLower(line), "cookie:") {
		line = strings.TrimSpace(line[len("cookie:"):])
	}

	// 去除两端可能存在的引号
	line = strings.Trim(line, "\"'")

	return line, nil
}

// readNameFromStdin 从标准输入读取 API Key 名称。
func readNameFromStdin() (string, error) {
	reader := bufio.NewReader(os.Stdin)
	fmt.Print("请输入 API Key 名称（回车使用默认值 1212131）:\n> ")

	line, err := reader.ReadString('\n')
	if err != nil && err != io.EOF {
		return "", fmt.Errorf("读取输入失败: %w", err)
	}

	line = strings.TrimSpace(line)
	if line == "" {
		line = defaultName
	}

	// 去除两端可能存在的引号
	line = strings.Trim(line, "\"'")

	return line, nil
}

// apiResponse 表示接口返回的 JSON 结构。
type apiResponse struct {
	Code int    `json:"code"`
	Msg  string `json:"msg"`
	Data struct {
		Key       string `json:"key"`
		KeyID     string `json:"key_id"`
		ExpiresAt string `json:"expires_at"`
	} `json:"data"`
}

// buildRequest 构造 POST 请求，复制原 curl 的全部请求头。
func buildRequest(cookie, name, enterpriseID string) (*http.Request, error) {
	payload := map[string]string{
		"name":                name,
		"user_enterprise_id":  enterpriseID,
	}
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, fmt.Errorf("序列化请求体失败: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, apiKeyEndpoint, bytes.NewReader(bodyBytes))
	if err != nil {
		return nil, fmt.Errorf("构造请求失败: %w", err)
	}

	// 按原 curl 顺序设置请求头
	headers := map[string]string{
		"Accept":             "application/json, text/plain, */*",
		"Accept-Encoding":    "gzip, deflate, br, zstd",
		"Accept-Language":    "zh-CN,zh;q=0.9",
		"Cache-Control":      "no-cache",
		"Connection":         "keep-alive",
		"Content-Type":       "application/json",
		"Cookie":             cookie,
		"Host":               "www.codebuddy.cn",
		"Origin":             "https://www.codebuddy.cn",
		"Pragma":             "no-cache",
		"Sec-Fetch-Dest":     "empty",
		"Sec-Fetch-Mode":     "cors",
		"Sec-Fetch-Site":     "same-origin",
		"User-Agent":         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
		"sec-ch-ua":          `"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"`,
		"sec-ch-ua-mobile":   "?0",
		"sec-ch-ua-platform": `"Windows"`,
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}

	return req, nil
}

func main() {
	// 命令行参数（可选）
	enterpriseID := flag.String("enterprise-id", defaultUserEnterpriseID, "user_enterprise_id")
	timeoutSec := flag.Int("timeout", defaultTimeoutSeconds, "请求超时秒数")
	flag.Parse()

	// 1. 询问 API Key 名称
	name, err := readNameFromStdin()
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误: %v\n", err)
		waitEnterToExit()
		os.Exit(1)
	}

	// 2. 询问 Cookie
	cookie, err := readCookieFromStdin()
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误: %v\n", err)
		waitEnterToExit()
		os.Exit(1)
	}
	if cookie == "" {
		fmt.Fprintln(os.Stderr, "错误: Cookie 不能为空")
		waitEnterToExit()
		os.Exit(1)
	}

	// 3. 构造绕过代理的 HTTP 客户端
	client := buildHTTPClient(time.Duration(*timeoutSec) * time.Second)

	// 4. 构造请求（使用用户输入的 name 与默认 enterprise-id）
	req, err := buildRequest(cookie, name, *enterpriseID)
	if err != nil {
		fmt.Fprintf(os.Stderr, "错误: %v\n", err)
		os.Exit(1)
	}

	// 4. 发送请求
	resp, err := client.Do(req)
	if err != nil {
		fmt.Fprintf(os.Stderr, "请求失败: %v\n", err)
		waitEnterToExit()
		os.Exit(1)
	}
	defer resp.Body.Close()

	// 5. 读取响应并解析出 key
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		fmt.Fprintf(os.Stderr, "读取响应体失败: %v\n", err)
		waitEnterToExit()
		os.Exit(1)
	}

	var apiResp apiResponse
	if err := json.Unmarshal(respBody, &apiResp); err != nil {
		fmt.Fprintf(os.Stderr, "解析响应失败: %v\n原始响应: %s\n", err, string(respBody))
		waitEnterToExit()
		os.Exit(1)
	}

	if apiResp.Code != 0 || apiResp.Data.Key == "" {
		fmt.Fprintf(os.Stderr, "请求失败: code=%d msg=%s\n原始响应: %s\n", apiResp.Code, apiResp.Msg, string(respBody))
		waitEnterToExit()
		os.Exit(1)
	}

	// 只输出 key
	fmt.Println(apiResp.Data.Key)
	waitEnterToExit()
}

// waitEnterToExit 等待用户按下回车后退出，便于双击运行时查看输出。
func waitEnterToExit() {
	fmt.Print("\n按回车键退出...")
	bufio.NewReader(os.Stdin).ReadString('\n')
}
