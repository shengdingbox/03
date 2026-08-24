package app

import (
	"context"
	"fmt"
	"math/rand"
	"strings"

	"buddy.tool/cli/internal/httpclient"
	"buddy.tool/cli/internal/modelconfig"
	"buddy.tool/cli/internal/serverapi"
	"buddy.tool/cli/internal/settings"
	"buddy.tool/cli/internal/version"
)

// cmdInfo 展示当前全部信息。
func cmdInfo(s *Session, _ []string, _ context.Context) int {
	printHeader("当前信息")
	println("\n📋 基本信息:")
	printKV("版本号", version.Current(), 0)
	printKV("API Key", orElse(s.SessionKey, "（未设置）"), 1)

	println("\n📄 配置 JSON 预览:")
	println("  （使用 'config' 命令查看完整配置）")
	println()
	return 0
}

func orElse(s, def string) string {
	if s == "" {
		return def
	}
	return s
}

// cmdCredits 查询积分。
func cmdCredits(s *Session, _ []string, ctx context.Context) int {
	printHeader("积分查询")
	userKey := s.SessionKey
	printf("API Key: %s\n", userKey)
	println("正在查询...")

	result, err := serverapi.GetCredits(ctx, userKey)
	if err != nil {
		printf("❌ 查询失败: %s\n", err)
		return 1
	}

	println("\n✅ 查询成功:")
	printKV("剩余积分", result["credits"], 0)
	printKV("累计充值", result["totalRecharged"], 0)
	printKV("累计使用", result["totalUsed"], 0)
	printKV("今日使用", result["todayUsed"], 0)
	printKV("今日排名", result["todayRank"], 0)
	return 0
}

// cmdConfig 展示配置 JSON。
func cmdConfig(s *Session, _ []string, ctx context.Context) int {
	printHeader("客户端配置")
	apiKey := s.SessionKey
	upstreamBase := resolveUpstreamBase(s, ctx)
	if upstreamBase == "" {
		println("⚠️  无可用服务端地址")
		return 1
	}

	serverModels := serverapi.GetProxyModels(ctx)
	models := modelconfig.BuildConfigModels(apiKey, serverModels, upstreamBase, "")

	if len(models) == 0 {
		println("⚠️  从服务端获取模型列表失败")
	}
	printJSON(map[string]any{"models": models})
	return 0
}

// cmdConfigClient 配置 WorkBuddy / CodeBuddy 的 models.json。
func cmdConfigClient(s *Session, args []string, targetClient string, ctx context.Context) int {
	opts, _ := argParse(args, "prefix")
	name := "WorkBuddy"
	if targetClient != "workbuddy" {
		name = "CodeBuddy"
	}
	printHeader(fmt.Sprintf("配置 %s", name))

	apiKey := s.SessionKey
	if apiKey == "" {
		println("❌ 未设置 API Key")
		return 1
	}

	prefix := opts["prefix"]
	if prefix == "" {
		prefix = settings.LoadModelPrefix()
	}

	upstreamBase := resolveUpstreamBase(s, ctx)
	serverModels := serverapi.GetProxyModels(ctx)
	if len(serverModels) == 0 {
		println("⚠️  从服务端获取模型列表失败，跳过配置")
		return 1
	}

	models := modelconfig.BuildConfigModels(apiKey, serverModels, upstreamBase, prefix)
	if len(models) == 0 {
		println("⚠️  模型列表为空，跳过配置")
		return 1
	}

	targetPath := modelconfig.TargetPath(targetClient)
	existing, _ := modelconfig.ReadExisting(targetPath)
	merged, replaced, added := modelconfig.IncrementalMerge(existing, models)

	if _, err := modelconfig.WriteClientConfig(targetClient, merged); err != nil {
		printf("❌ 写入配置失败: %s\n", err)
		return 1
	}

	printf("\n✅ %s 配置已更新!\n", name)
	printKV("新增模型", added, 0)
	printKV("更新模型", replaced, 0)
	printKV("当前模型数", len(merged), 0)
	printKV("接口地址", fmt.Sprintf("%s/v1/chat/completions", upstreamBase), 0)
	printKV("配置位置", targetPath, 0)
	if prefix != "" {
		printKV("模型前缀", prefix, 0)
	}
	println("\n（原配置已自动备份，可用 restore-config 还原）")
	return 0
}

func cmdConfigWorkbuddy(s *Session, args []string, ctx context.Context) int {
	return cmdConfigClient(s, args, "workbuddy", ctx)
}

func cmdConfigCodebuddy(s *Session, args []string, ctx context.Context) int {
	return cmdConfigClient(s, args, "codebuddy", ctx)
}

// cmdRestoreConfig 从备份目录还原配置。
func cmdRestoreConfig(s *Session, args []string, ctx context.Context) int {
	_ = s
	_ = ctx
	if len(args) < 1 || (args[0] != "workbuddy" && args[0] != "codebuddy") {
		println("用法: buddy restore-config <workbuddy|codebuddy>")
		return 1
	}
	client := args[0]
	name := "WorkBuddy"
	if client != "workbuddy" {
		name = "CodeBuddy"
	}
	printHeader(fmt.Sprintf("还原 %s 配置", name))

	targetPath, err := modelconfig.RestoreConfig(client)
	if err != nil {
		printf("❌ %s\n", err)
		return 1
	}
	printf("\n✅ %s 配置已还原: %s\n", name, targetPath)
	return 0
}

// resolveUpstreamBase 获取上游基址（对应 Python _resolve_upstream_base）。
func resolveUpstreamBase(s *Session, ctx context.Context) string {
	if s.SelectedNodeURL != "" {
		return s.SelectedNodeURL
	}
	servers, err := httpclient.GetServerList(ctx)
	if err == nil && len(servers) > 0 {
		return strings.TrimRight(servers[rand.Intn(len(servers))], "/")
	}
	return "https://buddy.shengdingit.com"
}

// argParse 极简参数解析（对应 Python _arg_parse）。
//
// 只支持 --prefix V / --prefix=V / --flag。
func argParse(argv []string, options ...string) (map[string]string, []string) {
	opts := map[string]string{}
	var positional []string
	for i := 0; i < len(argv); i++ {
		a := argv[i]
		if strings.HasPrefix(a, "--") {
			body := a[2:]
			if eq := strings.Index(body, "="); eq >= 0 {
				opts[body[:eq]] = body[eq+1:]
			} else if i+1 < len(argv) && !strings.HasPrefix(argv[i+1], "--") && contains(options, body) {
				opts[body] = argv[i+1]
				i++
			} else {
				opts[body] = "true"
			}
		} else {
			positional = append(positional, a)
		}
	}
	return opts, positional
}

func contains(list []string, s string) bool {
	for _, item := range list {
		if item == s {
			return true
		}
	}
	return false
}
