# BuddyToolNew

WorkBuddy / CodeBuddy 模型配置 CLI 工具。Go 单二进制，零依赖，跨平台（Windows / macOS / Linux）。

## 命令

| 命令 | 说明 |
|------|------|
| `info` | 展示当前信息（版本、API Key） |
| `credits` | 查询积分 |
| `config` | 展示配置 JSON |
| `config-workbuddy` | 配置 `~/.workbuddy/models.json`（裸数组） |
| `config-codebuddy` | 配置 `~/.codebuddy/models.json`（`{"models":[...]}`） |
| `restore-config <workbuddy\|codebuddy>` | 从备份还原配置 |
| `help` | 打印帮助 |

无参数运行进入交互模式：选择服务节点 → 输入 API Key → 主菜单。

```
BuddyTool help               # 查看帮助
BuddyTool info               # 展示当前信息
BuddyTool credits            # 查询积分
BuddyTool config-workbuddy   # 配置 WorkBuddy models.json
BuddyTool config-codebuddy --prefix p_   # 带模型前缀
BuddyTool restore-config workbuddy       # 还原 WorkBuddy 配置
```

## 构建

```bash
make build   # 本机构建到 out/
make test    # 运行测试
make cross   # 交叉编译 4 平台产物
```

或直接：

```bash
go build -o BuddyTool.exe .
```

版本号从根目录 `VERSION` 文件读取；发布构建通过 `-ldflags` 注入（见 `.github/workflows/build.yml`）。

## 数据文件

- 模型配置：`~/.workbuddy/models.json`、`~/.codebuddy/models.json`
- 配置备份：`~/.buddytoolnew/config_backups/{client}_{时间戳}.json`
- 设置：`~/.buddytoolnew/settings.json`（当前仅 `model_prefix`）
- API Key 仅存于会话内存，每次启动重新输入，不落盘
