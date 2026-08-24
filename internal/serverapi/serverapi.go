// Package serverapi 调用服务端 API（积分查询、模型列表、节点发现）。
//
// 对应原 Python src/utils/server_api.py 的明文接口部分。
package serverapi

import (
	"context"
	"errors"
	"fmt"
	"math/rand"
	"time"

	"buddy.tool/cli/internal/httpclient"
)

// ProxyModelsURL 模型列表固定地址（与节点列表地址源不同；测试可覆盖）。
var ProxyModelsURL = "https://buddy.shengdingit.com/api/proxy/models"

var client = httpclient.NewClient()

// Credits 积分查询结果。
type Credits struct {
	Credits        float64 `json:"credits"`
	TotalUsed      float64 `json:"totalUsed"`
	TotalRecharged float64 `json:"totalRecharged"`
	TodayUsed      float64 `json:"todayUsed"`
	TodayRank      int     `json:"todayRank"`
	UserKey        string  `json:"userKey"`
}

// GetCredits 查询用户积分额度。
//
// 随机打乱节点列表逐个尝试，网络层异常切换下一个节点；
// 成功判据是响应含 credits 字段（非 HTTP 状态码）。返回原始 dict 字段。
func GetCredits(ctx context.Context, userKey string) (map[string]any, error) {
	if userKey == "" {
		return nil, errors.New("API Key 为空，请先输入 API Key")
	}

	servers, err := httpclient.GetServerList(ctx)
	if err != nil {
		return nil, err
	}
	rand.Shuffle(len(servers), func(i, j int) { servers[i], servers[j] = servers[j], servers[i] })

	var lastErr error
	for _, base := range servers {
		url := base + "/api/user/credits"
		var data map[string]any
		cctx, cancel := context.WithTimeout(ctx, 15*time.Second)
		err := httpclient.GetJSON(cctx, client, url+"?userKey="+userKey, &data)
		cancel()

		if err != nil {
			lastErr = err
			continue // 网络异常，切下一个节点
		}
		if _, ok := data["credits"]; ok {
			return data, nil
		}
		// 响应无 credits 键：直接返回错误，不 failover
		msg, _ := data["error"].(string)
		if msg == "" {
			msg, _ = data["message"].(string)
		}
		if msg == "" {
			msg = "未知错误"
		}
		return nil, errors.New(msg)
	}
	if lastErr != nil {
		return nil, fmt.Errorf("无可用服务端地址: %w", lastErr)
	}
	return nil, errors.New("无可用服务端地址")
}

// GetProxyModels 获取模型列表。
//
// 固定从 ProxyModelsURL 获取。响应 dict.data 为列表则返回之，裸列表直接返回，
// 其他/失败返回空列表（不报错，无 failover）。
func GetProxyModels(ctx context.Context) []map[string]any {
	var raw any
	cctx, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	if err := httpclient.GetJSON(cctx, client, ProxyModelsURL, &raw); err != nil {
		return nil
	}

	// dict 含 data 列表（OpenAI 兼容格式）
	if m, ok := raw.(map[string]any); ok {
		if list, ok := m["data"].([]any); ok {
			return anyMaps(list)
		}
	}
	// 裸列表
	if list, ok := raw.([]any); ok {
		return anyMaps(list)
	}
	return nil
}

// anyMaps 把 []any 转为 []map[string]any，跳过非对象元素。
func anyMaps(list []any) []map[string]any {
	out := make([]map[string]any, 0, len(list))
	for _, item := range list {
		if m, ok := item.(map[string]any); ok {
			out = append(out, m)
		}
	}
	return out
}
