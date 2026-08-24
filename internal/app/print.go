package app

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strings"
)

// stdout 是全局输出流；测试可替换。
var stdout io.Writer = os.Stdout

// printHeader 打印标题分隔块（对应 Python _print_header）。
func printHeader(title string) {
	line := strings.Repeat("=", 50)
	fmt.Fprintf(stdout, "\n%s\n  %s\n%s\n", line, title, line)
}

// printKV 打印键值（对应 Python _print_kv）。
func printKV(key string, v any, indent int) {
	prefix := strings.Repeat("  ", indent)
	switch val := v.(type) {
	case map[string]any, []any:
		b, err := json.MarshalIndent(val, "", "  ")
		if err != nil {
			fmt.Fprintf(stdout, "%s%s: %v\n", prefix, key, val)
			return
		}
		fmt.Fprintf(stdout, "%s%s:\n%s  %s\n", prefix, key, prefix, b)
	default:
		fmt.Fprintf(stdout, "%s%s: %v\n", prefix, key, v)
	}
}

// printJSON 打印缩进 JSON（对应 json.dumps(indent=2)）。
func printJSON(v any) {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		fmt.Fprintf(stdout, "%v\n", v)
		return
	}
	fmt.Fprintf(stdout, "%s\n", b)
}

// printf 打印到 stdout。
func printf(format string, a ...any) {
	fmt.Fprintf(stdout, format, a...)
}

// print 打印到 stdout（不换行）。
func print(a ...any) {
	fmt.Fprint(stdout, a...)
}

// println 打印一行到 stdout。
func println(a ...any) {
	fmt.Fprintln(stdout, a...)
}
