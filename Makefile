# BuddyToolNew Go 构建脚本
#
#   make build   本机构建
#   make test    运行测试
#   make vet     go vet
#   make cross   交叉编译 4 平台产物到 out/
#   make clean   清理 out/

BINARY   := BuddyTool
VERSION  := $(shell tr -d '\r\n' < VERSION)
LDFLAGS  := -s -w -X buddy.tool/cli/internal/version.injectedVersion=$(VERSION)
OUT      := out

.PHONY: build test vet cross clean

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

clean:
	rm -rf $(OUT)
