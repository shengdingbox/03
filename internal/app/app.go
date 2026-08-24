// Package app 实现命令分发与交互式 CLI 流程。
package app

import (
	"bufio"
	"context"
	"os"
	"os/signal"
	"strings"
	"syscall"
)

// Session 保存会话内状态（内存态，不落盘）。
type Session struct {
	SelectedNodeURL string
	SessionKey      string
	reader          *bufio.Reader
}

// Run 是 CLI 主入口，返回进程退出码。
func Run(args []string) int {
	s := &Session{reader: bufio.NewReader(os.Stdin)}
	if len(args) < 1 {
		return s.interactive()
	}

	switch args[0] {
	case "-h", "--help", "help":
		printHelp()
		return 0
	}

	cmd := args[0]
	cmdArgs := args[1:]
	entry, ok := commands[cmd]
	if !ok {
		printf("未知命令: %s\n", cmd)
		printf("可用命令: %s\n", strings.Join(commandNames(), ", "))
		return 1
	}

	// 单命令路径：SIGINT → 已取消 → 130（对应 Python KeyboardInterrupt）
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	code := entry.fn(s, cmdArgs, ctx)
	if ctx.Err() != nil {
		println("\n已取消")
		return 130
	}
	return code
}

// 命令注册表（对应 Python COMMANDS dict）。
var commands = map[string]struct {
	desc string
	fn   func(*Session, []string, context.Context) int
}{
	"info":             {"展示当前全部信息", cmdInfo},
	"credits":          {"查询积分", cmdCredits},
	"config":           {"展示配置 JSON", cmdConfig},
	"config-workbuddy": {"配置 WorkBuddy models.json", cmdConfigWorkbuddy},
	"config-codebuddy": {"配置 CodeBuddy models.json", cmdConfigCodebuddy},
	"restore-config":   {"还原配置 <workbuddy|codebuddy>", cmdRestoreConfig},
}

func commandNames() []string {
	// 保持 Python COMMANDS 的展示顺序
	order := []string{"info", "credits", "config", "config-workbuddy", "config-codebuddy", "restore-config"}
	return order
}

func printHelp() {
	println("BuddyToolNew CLI - 命令行操作")
	println()
	println("用法: buddy <command> [args]")
	println()
	println("命令:")
	for _, name := range commandNames() {
		printf("  %-18s %s\n", name, commands[name].desc)
	}
	println()
	println("示例:")
	println("  buddy info")
	println("  buddy credits")
	println("  buddy config-workbuddy")
}
