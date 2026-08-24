package app

import (
	"context"
	"fmt"
	"io"
	"strconv"
	"strings"

	"buddy.tool/cli/internal/httpclient"
)

// interactive 交互式流程：选择节点 → 输入 API Key → 主菜单（对应 Python _interactive）。
func (s *Session) interactive() int {
	for {
		if !s.selectNode() {
			return 0
		}
		if !s.startPage() {
			return 0
		}
		if s.mainMenu() {
			return 0
		}
	}
}

// readLine 读取一行输入（对应 Python _prompt）。
func (s *Session) readLine(desc string) string {
	if desc != "" {
		print(desc)
	}
	line, err := s.reader.ReadString('\n')
	if err != nil {
		if err != io.EOF {
			println("\n已取消")
		}
		return ""
	}
	return strings.TrimSpace(line)
}

// saveExistingKey 保存 API Key 到会话内存（不落盘）。
func (s *Session) saveExistingKey(buddyKey string) bool {
	buddyKey = strings.TrimSpace(buddyKey)
	if buddyKey == "" {
		println("❌ API Key 不能为空")
		return false
	}
	s.SessionKey = buddyKey
	println("✅ API Key 已设置")
	return true
}

// selectNode 选择服务端节点（对应 Python _select_node）。
func (s *Session) selectNode() bool {
	ctx := context.Background()
	printHeader("选择服务节点")
	nodes, err := httpclient.GetNodes(ctx, true)
	if err != nil || len(nodes) == 0 {
		println("⚠️  未获取到可用节点，使用默认地址。")
		return true
	}

	printf("共 %d 个节点，回车默认选择第一个：\n", len(nodes))
	for i, n := range nodes {
		name := n.Name
		if name == "" {
			name = n.URL
		}
		suffix := ""
		if n.Region != "" {
			suffix = fmt.Sprintf("（%s）", n.Region)
		}
		printf("  [%d] %s%s\n", i+1, name, suffix)
	}

	choice := s.readLine(fmt.Sprintf("请选择节点 (1-%d) [默认 1]: ", len(nodes)))
	idx := 1
	if choice != "" {
		n, err := strconv.Atoi(choice)
		if err != nil {
			println("❌ 无效选择，使用默认第一个。")
			idx = 1
		} else {
			idx = n
		}
	}
	if idx < 1 || idx > len(nodes) {
		println("❌ 超出范围，使用默认第一个。")
		idx = 1
	}

	node := nodes[idx-1]
	s.SelectedNodeURL = node.URL
	name := node.Name
	if name == "" {
		name = node.URL
	}
	printf("✅ 已选择节点: %s (%s)\n", name, node.URL)
	return true
}

// startPage 启动页（对应 Python _start_page）。
func (s *Session) startPage() bool {
	printHeader("BuddyToolNew")
	println("  官网: https://buddy.shengdingit.com （续费9折）")
	println("  查询积分/充值/进入官网/联系客服")
	println()
	return s.loginPage()
}

// loginPage API Key 输入页面（对应 Python _login_page）。
func (s *Session) loginPage() bool {
	printHeader("请输入 API Key")
	key := s.readLine("API Key (BuddyKey): ")
	if key == "" {
		return false
	}
	return s.saveExistingKey(key)
}

// mainMenu 主菜单（对应 Python _main_menu）。返回 true 表示退出。
func (s *Session) mainMenu() bool {
	for {
		printHeader("BuddyToolNew 菜单")
		println("  [1] 配置 WorkBuddy models.json")
		println("  [2] 配置 CodeBuddy models.json")
		println("  [3] 全部配置")
		println("  [4] 还原配置")
		println("  [0] 退出")
		choice := s.readLine("请选择: ")
		switch choice {
		case "1":
			cmdConfigWorkbuddy(s, nil, context.Background())
		case "2":
			cmdConfigCodebuddy(s, nil, context.Background())
		case "3":
			s.configAll()
		case "4":
			s.restoreMenu()
		case "0", "q":
			println("已退出")
			return true
		default:
			println("❌ 无效选择")
		}
		println()
	}
}

// configAll 同时配置 WorkBuddy 与 CodeBuddy（对应 Python _config_all）。
func (s *Session) configAll() {
	println("\n--- 配置 WorkBuddy ---")
	cmdConfigWorkbuddy(s, nil, context.Background())
	println("\n--- 配置 CodeBuddy ---")
	cmdConfigCodebuddy(s, nil, context.Background())
}

// restoreMenu 还原配置子菜单（对应 Python _restore_menu）。
func (s *Session) restoreMenu() {
	printHeader("还原配置")
	println("  还原哪个客户端配置？")
	println()
	println("  [1] WorkBuddy")
	println("  [2] CodeBuddy")
	println("  [0] 返回")
	choice := s.readLine("请选择: ")
	switch choice {
	case "1":
		cmdRestoreConfig(s, []string{"workbuddy"}, context.Background())
	case "2":
		cmdRestoreConfig(s, []string{"codebuddy"}, context.Background())
	case "0":
		return
	default:
		println("❌ 无效选择")
	}
}
