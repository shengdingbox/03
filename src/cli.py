"""BuddyToolNew CLI - 命令行操作入口（纯命令行，无图形界面）

用法：
  python -m src.cli <command> [args]

命令：
  info               展示当前全部信息（版本、机器码、端口、积分缓存、API Key、设置）
  credits            查询积分
  config             展示配置 JSON
  config-workbuddy   配置 WorkBuddy 的 models.json [--prefix P]
  config-codebuddy   配置 CodeBuddy 的 models.json [--prefix P]
  restore-config     从备份还原配置 <workbuddy|codebuddy>
  logs               查看请求日志 [--limit N]
  help               打印本帮助
"""

import sys
import json
import logging

logger = logging.getLogger(__name__)


def _print_header(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print(f"{'='*50}")


def _print_kv(key: str, value, indent: int = 0):
    prefix = "  " * indent
    if isinstance(value, (dict, list)):
        print(f"{prefix}{key}:")
        print(f"{prefix}  {json.dumps(value, ensure_ascii=False, indent=2)}")
    else:
        print(f"{prefix}{key}: {value}")


def _get_machine_code():
    from .utils.machine import get_machine_code
    return get_machine_code()


def _arg_parse(argv, options):
    """极简参数解析：支持 --key value / --flag / --key=value"""
    opts = {}
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith("--"):
            if "=" in a:
                k, v = a[2:].split("=", 1)
                opts[k] = v
            elif i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                k = a[2:]
                if k in options:
                    opts[k] = argv[i + 1]
                    i += 1
                else:
                    opts[k] = True
            else:
                opts[a[2:]] = True
        else:
            positional.append(a)
        i += 1
    return opts, positional


def cmd_credits(args):
    """查询积分"""
    _print_header("积分查询")
    from .utils.server_api import get_credits

    user_key = _get_machine_code()
    print(f"机器码: {user_key}")
    print("正在查询...")

    result = get_credits(user_key=user_key)
    if result.get("error"):
        print(f"❌ 查询失败: {result['error']}")
        return 1

    print(f"\n✅ 查询成功:")
    _print_kv("剩余积分", result.get("credits", 0))
    _print_kv("累计充值", result.get("totalRecharged", 0))
    _print_kv("累计使用", result.get("totalUsed", 0))
    _print_kv("今日使用", result.get("todayUsed", 0))
    _print_kv("今日排名", result.get("todayRank", 0))

    # 同时显示本地缓存
    try:
        from .modules.proxy_server import ProxyDatabase
        db = ProxyDatabase.get_instance()
        cached = db.get_cached_credits()
        if cached:
            print(f"\n（本地缓存）:")
            _print_kv("剩余积分", cached.get("credits", 0))
    except Exception:
        pass
    return 0


def cmd_config(args):
    """展示配置 JSON"""
    _print_header("客户端配置")
    from .utils.machine import get_machine_code
    from .utils.server_api import _fetch_server_list, get_proxy_models
    import random as _random

    api_key = get_machine_code() or ""
    servers = _fetch_server_list()
    upstream_base = _random.choice(servers).rstrip("/") if servers else ""
    if not upstream_base:
        print("⚠️  无可用服务端地址")
        return 1
    url = f"{upstream_base}/v1/chat/completions"

    # 从服务端动态获取模型列表（/api/proxy/models 明文 GET）
    models = []
    server_models = get_proxy_models()
    for m in server_models:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        models.append({
            "id": m.get("id", ""),
            "name": m.get("name") or m.get("id", ""),
            "vendor": m.get("vendor", "Buddy"),
            "apiKey": api_key,
            "url": url,
            "maxInputTokens": m.get("maxInputTokens", 128000),
            "maxOutputTokens": m.get("maxOutputTokens", 8192),
            "supportsToolCall": m.get("supportsToolCall", True),
            "supportsImages": m.get("supportsImages", True),
            "supportsReasoning": m.get("supportsReasoning", True),
        })

    if not models:
        print("⚠️  从服务端获取模型列表失败")

    config = {"models": models}
    print(json.dumps(config, ensure_ascii=False, indent=2))
    return 0


def _resolve_upstream_base():
    """从动态服务端地址列表随机取一个作为上游基址"""
    import random as _random
    from .utils.server_api import _fetch_server_list
    from .modules.proxy_server import DEFAULT_UPSTREAM_URL

    servers = _fetch_server_list()
    if servers:
        return _random.choice(servers).rstrip("/")
    return DEFAULT_UPSTREAM_URL.rstrip("/")


def cmd_config_client(args, target_client: str):
    """配置 WorkBuddy / CodeBuddy 的 models.json"""
    opts, _ = _arg_parse(args, ("prefix",))
    from .utils.store import load_setting
    from .utils.server_api import get_proxy_models
    from .utils.model_config import (
        build_config_models, write_client_config,
        _read_existing_models, _incremental_merge_models,
    )

    name = "WorkBuddy" if target_client == "workbuddy" else "CodeBuddy"
    _print_header(f"配置 {name}")

    global _session_api_key
    api_key = _session_api_key or _get_machine_code()
    if not api_key:
        print("❌ 未设置 API Key")
        return 1

    # 模型前缀（--prefix 覆盖本地设置）
    prefix = opts.get("prefix")
    if prefix is None:
        prefix = load_setting("model_prefix", "")

    # 上游地址 + 动态模型列表
    upstream_base = _resolve_upstream_base()
    server_models = get_proxy_models()
    if not server_models:
        print("⚠️  从服务端获取模型列表失败，跳过配置")
        return 1

    models = build_config_models(api_key, server_models, upstream_base, prefix=prefix)
    if not models:
        print("⚠️  模型列表为空，跳过配置")
        return 1

    # 读取现有配置并增量合并
    from .utils.model_config import (
        WORKBUDDY_MODELS, CODEBUDDY_MODELS,
    )
    target_path = WORKBUDDY_MODELS if target_client == "workbuddy" else CODEBUDDY_MODELS
    existing = _read_existing_models(target_path)
    merged, replaced, added = _incremental_merge_models(existing, models)

    # 写入（自动备份原文件）
    write_client_config(target_client, merged)

    print(f"\n✅ {name} 配置已更新!")
    _print_kv("新增模型", added)
    _print_kv("更新模型", replaced)
    _print_kv("当前模型数", len(merged))
    _print_kv("接口地址", f"{upstream_base}/v1/chat/completions")
    _print_kv("配置位置", target_path)
    if prefix:
        _print_kv("模型前缀", prefix)
    print("\n（原配置已自动备份，可用 restore-config 还原）")
    return 0


def cmd_config_workbuddy(args):
    return cmd_config_client(args, "workbuddy")


def cmd_config_codebuddy(args):
    return cmd_config_client(args, "codebuddy")


def cmd_restore_config(args):
    """从备份目录还原配置"""
    if len(args) < 1 or args[0] not in ("workbuddy", "codebuddy"):
        print("用法: python -m src.cli restore-config <workbuddy|codebuddy>")
        return 1

    client = args[0]
    name = "WorkBuddy" if client == "workbuddy" else "CodeBuddy"
    _print_header(f"还原 {name} 配置")
    from .utils.model_config import restore_config

    try:
        target_path = restore_config(client)
        print(f"\n✅ {name} 配置已还原: {target_path}")
        return 0
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return 1


def cmd_logs(args):
    """查看请求日志"""
    opts, _ = _arg_parse(args, ("limit",))
    try:
        limit = int(opts.get("limit", "200"))
    except ValueError:
        limit = 200

    _print_header("请求日志")
    from .modules.proxy_server import ProxyDatabase
    db = ProxyDatabase.get_instance()
    logs = db.get_request_logs(since=0, limit=limit)
    if not logs:
        print("（无请求日志）")
        return 0
    import time as _time
    for log in reversed(logs[-limit:]):
        ts = _time.strftime("%H:%M:%S", _time.localtime(log.get("timestamp", 0)))
        event = log.get("event", "")
        model = log.get("model", "")
        sub = log.get("sub_key_label") or log.get("sub_key_id") or ""
        err = log.get("error", "")
        duration = log.get("duration_ms", 0)
        print(f"[{ts}] {event:<16} model={model:<28} sub={sub:<20} "
              f"dur={duration}ms pt={log.get('prompt_tokens',0)} ct={log.get('completion_tokens',0)}"
              f"{' err=' + str(err) if err else ''}")
    return 0


def cmd_info(args):
    """展示当前全部信息"""
    _print_header("当前信息")
    from .modules.proxy_server import ProxyDatabase
    from .utils.store import load_setting, init_db
    from .modules.updater import get_current_version

    # 初始化数据库
    init_db()

    # 基本信息
    print("\n📋 基本信息:")
    _print_kv("版本号", get_current_version())
    _print_kv("机器码", _get_machine_code(), indent=1)

    # 端口和地址
    port = int(load_setting("proxy_port", "8002"))
    print(f"\n🔌 代理服务:")
    _print_kv("端口", port, indent=1)
    _print_kv("接口地址", f"http://127.0.0.1:{port}/v1/chat/completions", indent=1)

    # 积分
    print(f"\n💎 积分:")
    # 本地缓存
    try:
        db = ProxyDatabase.get_instance()
        cached = db.get_cached_credits()
        if cached:
            _print_kv("剩余积分（缓存）", cached.get("credits", 0), indent=1)
            _print_kv("累计充值", cached.get("totalRecharged", 0), indent=1)
            _print_kv("累计使用", cached.get("totalUsed", 0), indent=1)
            _print_kv("今日使用", cached.get("todayUsed", 0), indent=1)
        else:
            print("  （无本地缓存，使用 'credits' 命令查询）")
    except Exception as e:
        print(f"  读取缓存失败: {e}")

    # API Key
    print(f"\n🔑 API Key:")
    try:
        db = ProxyDatabase.get_instance()
        sub_keys = db.get_sub_api_keys()
        if sub_keys:
            for sk in sub_keys:
                _print_kv("Key", sk.get("api_key", ""), indent=1)
                _print_kv("状态", "启用" if sk.get("is_active") else "禁用", indent=1)
        else:
            print("  （未配置）")
    except Exception as e:
        print(f"  读取失败: {e}")

    # BuddyKey
    print(f"\n🔗 BuddyKey:")
    try:
        buddy_key = _get_machine_code()
        if buddy_key:
            _print_kv("BuddyKey", buddy_key[:20] + "...", indent=1)
        else:
            print("  （未激活）")
    except Exception as e:
        print(f"  读取失败: {e}")

    # 设置
    print(f"\n⚙️  设置:")
    try:
        settings = db.get_settings()
        if settings:
            for k, v in settings.items():
                _print_kv(k, v, indent=1)
        else:
            print("  （无）")
    except Exception as e:
        print(f"  读取失败: {e}")

    # 配置 JSON 预览
    print(f"\n📄 配置 JSON 预览:")
    print("  （使用 'config' 命令查看完整配置）")

    print()
    return 0


# 会话内 API Key（内存态，不落盘）。每次进入交互界面都需重新输入。
_session_api_key = ""


def _save_existing_key(buddy_key: str) -> bool:
    """保存 API Key (BuddyKey) 到会话内存，不落盘"""
    global _session_api_key

    buddy_key = buddy_key.strip()
    if not buddy_key:
        print("❌ API Key 不能为空")
        return False

    _session_api_key = buddy_key
    print("✅ API Key 已设置")
    return True


def _prompt(desc: str) -> str:
    try:
        return input(desc).strip()
    except (EOFError, KeyboardInterrupt):
        print("\n已取消")
        return ""


def _login_page() -> bool:
    """API Key 输入页面"""
    _print_header("请输入 API Key")
    key = _prompt("API Key (BuddyKey): ")
    if not key:
        return False
    return _save_existing_key(key)


def _restore_menu():
    """还原配置子菜单"""
    _print_header("还原配置")
    print("  还原哪个客户端配置？")
    print()
    print("  [1] WorkBuddy")
    print("  [2] CodeBuddy")
    print("  [0] 返回")
    choice = _prompt("请选择: ")
    if choice == "1":
        cmd_restore_config(["workbuddy"])
    elif choice == "2":
        cmd_restore_config(["codebuddy"])
    elif choice == "0":
        return
    else:
        print("❌ 无效选择")


def _main_menu() -> bool:
    """主菜单：配置 WorkBuddy / CodeBuddy / 还原配置

    Returns:
        True   退出程序
        False  继续循环
    """
    while True:
        _print_header("BuddyToolNew 菜单")
        print("  [1] 配置 WorkBuddy models.json")
        print("  [2] 配置 CodeBuddy models.json")
        print("  [3] 还原配置")
        print("  [0] 退出")
        choice = _prompt("请选择: ")
        if choice == "1":
            cmd_config_workbuddy([])
        elif choice == "2":
            cmd_config_codebuddy([])
        elif choice == "3":
            _restore_menu()
        elif choice in ("0", "q"):
            print("已退出")
            return True
        else:
            print("❌ 无效选择")
        print()


def _open_key_page():
    """打开网页获取 API Key"""
    import webbrowser
    url = "https://buddy.shengdingit.com"
    print(f"正在打开: {url}")
    try:
        webbrowser.open(url)
        print("✅ 已打开获取 API Key 页面，获取后请回来输入。")
    except Exception as e:
        print(f"❌ 打开浏览器失败: {e}")
        print(f"请手动访问: {url}")


def _start_page() -> bool:
    """启动菜单：输入 API Key / 获取 API Key

    Returns:
        True   已设置 API Key，可进入主菜单
        False  退出程序
    """
    while True:
        _print_header("BuddyToolNew")
        print("  1. 输入 API Key")
        print("  2. 获取apikey,充值访问https://buddy.shengdingit.com")
        print("  0. 退出")
        choice = _prompt("请选择: ")
        if choice == "1":
            if _login_page():
                return True
        elif choice == "2":
            _open_key_page()
            print()
        elif choice in ("0", "q"):
            print("已退出")
            return False
        else:
            print("❌ 无效选择")
            print()


def _interactive():
    """交互式流程：启动菜单 → 输入/获取 API Key → 主菜单"""
    while True:
        if not _start_page():
            return 0
        if _main_menu():
            return 0


COMMANDS = {
    "info": ("展示当前全部信息", cmd_info),
    "credits": ("查询积分", cmd_credits),
    "config": ("展示配置 JSON", cmd_config),
    "config-workbuddy": ("配置 WorkBuddy models.json", cmd_config_workbuddy),
    "config-codebuddy": ("配置 CodeBuddy models.json", cmd_config_codebuddy),
    "restore-config": ("还原配置 <workbuddy|codebuddy>", cmd_restore_config),
    "logs": ("查看请求日志", cmd_logs),
}


def main():
    """CLI 入口"""
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    if len(sys.argv) < 2:
        return _interactive()

    if sys.argv[1] in ("-h", "--help", "help"):
        print("BuddyToolNew CLI - 命令行操作")
        print(f"\n用法: python -m src.cli <command> [args]")
        print(f"\n命令:")
        for cmd, (desc, _) in COMMANDS.items():
            print(f"  {cmd:18s} {desc}")
        print(f"\n示例:")
        print(f"  python -m src.cli info")
        print(f"  python -m src.cli credits")
        print(f"  python -m src.cli config-workbuddy")
        return 0

    cmd_name = sys.argv[1]
    cmd_args = sys.argv[2:]

    if cmd_name not in COMMANDS:
        print(f"未知命令: {cmd_name}")
        print(f"可用命令: {', '.join(COMMANDS.keys())}")
        return 1

    desc, func = COMMANDS[cmd_name]
    try:
        return func(cmd_args)
    except KeyboardInterrupt:
        print("\n已取消")
        return 130
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        logger.exception("CLI 命令执行异常")
        return 1


if __name__ == "__main__":
    sys.exit(main())
