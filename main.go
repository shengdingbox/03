// BuddyToolNew CLI 入口。
package main

import (
	"os"

	"buddy.tool/cli/internal/app"
)

func main() {
	os.Exit(app.Run(os.Args[1:]))
}
