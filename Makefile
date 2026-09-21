# BuddyToolNew Go 构建脚本
#
#   make build            本机构建
#   make test             运行测试
#   make vet              go vet
#   make cross            交叉编译 4 平台产物到 out/
#   make pkg              交叉编译并打包（带版本号文件名，与 CI 一致）
#   make clean            清理 out/
#
# 版本号默认读 VERSION 文件，可覆盖：make pkg VERSION=26.09.21

BINARY   ?= BuddyTool
VERSION  ?= $(shell tr -d '\r\n' < VERSION)
LDFLAGS  := -s -w -X buddy.tool/cli/internal/version.injectedVersion=$(VERSION)
OUT      := out

.PHONY: build test vet cross pkg clean

build:
	go build -trimpath -ldflags "$(LDFLAGS)" -o $(OUT)/$(BINARY)$(shell go env GOEXE) .

test:
	go test ./...

vet:
	go vet ./...

# 交叉编译：windows amd64 / darwin amd64+arm64 / linux amd64
cross:
	@mkdir -p $(OUT)
	@echo "=== windows/amd64 ==="
	CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "$(LDFLAGS)" -o $(OUT)/BuddyTool.exe .
	@echo "=== darwin/amd64 ==="
	CGO_ENABLED=0 GOOS=darwin GOARCH=amd64 go build -trimpath -ldflags "$(LDFLAGS)" -o $(OUT)/BuddyTool-darwin-amd64 .
	@echo "=== darwin/arm64 ==="
	CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 go build -trimpath -ldflags "$(LDFLAGS)" -o $(OUT)/BuddyTool-darwin-arm64 .
	@echo "=== linux/amd64 ==="
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "$(LDFLAGS)" -o $(OUT)/buddy-tool .
	@echo "=== 产物 ==="
	@ls -lh $(OUT)

# 打包为发布产物（文件名不带版本号，与 .github/workflows/build.yml 一致）
pkg: cross
	@echo "=== 打包 ==="
	@cd $(OUT) && \
		zip -q -r BuddyTool-windows-amd64.zip BuddyTool.exe && \
		zip -q -r BuddyTool-darwin-amd64.zip BuddyTool-darwin-amd64 && \
		zip -q -r BuddyTool-darwin-arm64.zip BuddyTool-darwin-arm64 && \
		tar -czf buddy-tool-linux-amd64.tar.gz buddy-tool
	@ls -lh $(OUT)

clean:
	rm -rf $(OUT)
