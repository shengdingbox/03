# BuddyToolNew - 项目记忆

## 项目概述
- **名称**: BuddyToolNew（⚡ BuddyToolNew）
- **定位**: 多平台 IDE 工具管理器 — WorkBuddy / CodeBuddy 批量签到、API Key 代理、积分管理
- **技术栈**: Python 3.11+ / PySide6 (Qt6) / SQLite / PyInstaller 打包（onefile，spec 文件）
- **仓库**: https://github.com/qinchangxv/buddytoolnew
- **当前版本**: v1.1.8（src/VERSION）
- **许可**: MIT

## 命名约定（重要）
软件内部有多类 "buddy" 标识，**改名时必须区分**：
- **软件名（已改为 BuddyToolNew）**：显示名 `BuddyToolNew`、可执行名 `BuddyToolNew.exe`、包名 `buddytoolnew`、数据目录 `~/.buddytoolnew`、DB 名 `buddytoolnew.db`、单实例锁名 `buddytoolnew-single-instance`、开机自启项名 `BuddyToolNew`。
- **第三方平台名（不可改）**：`WorkBuddy`、`CodeBuddy`、`CodeBuddy CN`；其数据文件 `workbuddy.db`。
- **服务端 API 协议（不可改，改了连不上服务端）**：`BuddyKey`/`buddykey`、API Key `buddy_707d23cb0832fb0f0fc4a3d7`、域名 `buddy.shengdingit.com`、管理密钥 `xiaobaobuddy`/`xiaofeibuddy`。注：旧加密接口（server_api.py 的 redeem/get_credits/get_buddykey）保留但当前暂不使用。
- **机器码**：现已改为激活时服务端返回的 buddyKey 原值（如 `sk-xxx`），持久化在 `proxy_db.key` 的 `settings.machine_code`。不再基于硬件计算。`machine.py` 的 `_get_disk_serial/_get_cpu_id/_get_hostname` 仍保留，仅供 `proxy_db.key` 的 AES 密钥派生使用。
- **本地数据格式标记（不可改，改了旧用户数据失效）**：`proxy_db.key` 中的 magic `b"BTG1"`（注释为 "BuddyToolNew GCM v1"）。
- **激活接口**：明文 POST `http://47.108.236.176:5000/api/activate`，body `{"cardKey":"BC_xxx"}`，返回 `{buddyKey, cardKey, faceValue, success}`。buddyKey 同时作为机器码和上游 api_key，faceValue 作为当前积分。
- **查分接口**：明文 GET `http://47.108.236.176:5000/api/user/credits?userKey=<buddyKey>`，返回 `{credits, todayRank, todayUsed, totalRecharged, totalUsed, userKey}`。封装在 `server_api.get_credits()`。
- **明文服务基址**：`_PLAIN_BASE = "http://47.108.236.176:5000"`，`_plain_session`（不加密、`trust_env=False`）。激活 `activate_card()` + 查分 `get_credits()` 都走此 session。
- **启动服务流程**：点"启动服务"直接启动代理（`_toggle_proxy_service` → `_on_service_started` → `_proxy_page._toggle_service()`），不再获取 BuddyKey。buddyKey 复用激活卡密时存入上游 Key 池的那条。运行时额度耗尽(429/14018)直接标记 key 为 exhausted，提示用户激活新卡密，不再自动获取新 BuddyKey。

## 项目结构
```
buddytoolnew/
├── app.py                 # 打包入口，importlib 动态加载 src.main
├── src/                   # 核心源码包
│   ├── main.py            # 应用入口（日志、单实例、信号处理、QApplication）
│   ├── main_window.py     # 主窗口（侧边栏 + QStackedWidget、托盘、自动更新）
│   ├── cli.py             # 命令行入口（info/credits/redeem/start/config）
│   ├── i18n/              # 国际化（zh-CN/en-US 翻译字典）
│   ├── models/__init__.py # 数据模型（Account, Platform, QuotaInfo 等）
│   ├── modules/           # 核心业务模块
│   │   ├── api_client.py    # CodeBuddy/WorkBuddy API 客户端（积分、签到）
│   │   ├── oauth.py         # WorkBuddy OAuth 登录流程
│   │   ├── checkin.py       # 签到管理器
│   │   ├── proxy_server.py  # 本地 API 中转代理（最大文件，~176KB）
│   │   └── updater.py       # 自动更新检查器
│   ├── ui/
│   │   ├── components/sidebar.py  # 侧边栏导航
│   │   ├── pages/                # 5 个页面
│   │   │   ├── dashboard.py   # 仪表盘（含一键配置、备份）
│   │   │   ├── accounts.py    # 账号管理（~104KB，最大页面）
│   │   │   ├── checkin.py     # 每日签到
│   │   │   ├── api_proxy.py   # API 代理配置（~120KB）
│   │   │   ├── settings.py    # 设置（含开机自启）
│   │   │   └── quota.py       # 配额监控
│   │   └── styles/theme.py    # 主题样式
│   └── utils/
│       ├── store.py          # SQLite 持久化（~/.buddytoolnew/buddytoolnew.db）
│       ├── machine.py        # 机器码生成（前缀 buddy_，服务端协议）
│       ├── usage_reporter.py # 用量上报（缓存 ~/.buddytoolnew/usage_pending/）
│       ├── server_api.py     # 服务端 API 客户端（含 failover）
│       └── ssl_pinning.py    # buddy.shengdingit.com 的 SPKI 固定
├── tests/                # 测试（test_model_config.py）
├── assets/icons/         # 应用图标
├── key/                  # Go 脚本（create_apikey.go，创建 codebuddy.cn API Key）
├── build.bat             # PyInstaller 一键打包（输出 dist\BuddyToolNew.exe）
├── BuddyToolNew.spec     # PyInstaller spec 文件（PySide6 DLL 白名单 + src hiddenimports）
├── publish.bat           # 更新包打包+上传（scp 到 /var/www/html/buddytoolnew/）
├── pyproject.toml        # uv 项目配置（name = "buddytoolnew"）
├── requirements.txt      # pip 依赖
├── API.md                # 服务端 API 文档
└── dist_final/           # 打包输出目录
```

## 核心功能模块
1. **账号管理**: 多平台账号统一管理，支持 API Key (ck_xxx) 导入、JSON/文本批量导入、卡密导入
2. **批量签到**: 每日自动签到 + 连续签到追踪
3. **积分监控**: 实时查询积分/配额，多资源包展示
4. **API 代理服务**: 本地 HTTP 代理，转发请求到上游 copilot.tencent.com，支持多 Key 轮询/粘性会话/负载感知/故障转移
5. **自动更新**: 定期检查服务端 version.json，支持增量更新（src/ 目录替换）
6. **一键配置**: 一键配置 WorkBuddy/CodeBuddy 客户端走本地代理

## 关键技术细节
- **数据存储**: SQLite (`~/.buddytoolnew/buddytoolnew.db`)，WAL 模式；代理密钥库 `~/.buddytoolnew/proxy_db.key`（AES-256-GCM + 机器绑定，magic BTG1）
- **API 认证**: 两种模式 — JWT (Keycloak) 和 API Key (ck_xxx)，推荐 API Key 模式
- **API 基址**: 积分/签到 API 在 `https://copilot.tencent.com`，公开 API 在 `https://codebuddy.cn`，自建服务端 `http://47.83.145.136:8787`（卡密/兑换/BuddyKey/用量上报）
- **代理上游**: `https://47.108.236.176/v1`（明文，透传请求和响应）。上游路径 `/chat/completions`、`/models`。用 buddyKey 作上游鉴权。
- **单实例**: QLocalSocket/QLocalServer 实现，锁名 `buddytoolnew-single-instance`，支持唤醒已运行窗口
- **打包**: PyInstaller onefile 模式（`BuddyToolNew.spec`），app.py 用 importlib 动态加载 src.main；spec 中需将 src 所有子模块加入 hiddenimports，pathex 设为项目根目录
- **日志**: 控制台输出（GUI 模式动态 AttachConsole）

## 依赖
- PySide6==6.8.3 (Qt6 GUI 框架)
- requests==2.34.2 (HTTP 客户端)
- cryptography==48.0.0
- nuitka==2.7.12（已弃用）
- pyinstaller==6.20.0（当前打包工具）
- pysocks>=1.7.1

## 运行方式
- 开发: `python src/main.py` 或 `python -m src.main`
- CLI: `python -m src.cli <command>`（info/credits/redeem/start/config）
- 打包: `build.bat`（Nuitka → dist\BuddyToolNew.exe）
- 发布: `publish.bat`（打包 src/ 为 update.zip + 计算 SHA256 + 生成 version.json + 可选上传）

## Git 状态备注
- Git 仓库: github.com/qinchangxv/buddytoolnew，分支 main
- `dist_final/` 是上次打包产物，重新 build 会覆盖
