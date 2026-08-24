"""服务端 API 客户端 — 积分查询、模型列表、节点发现

服务端地址动态获取：从 https://buddy.shengdingit.com/api/server_endpoints
获取节点列表（含 name/url/sortOrder），按 sortOrder 排序后取 url 作为服务端 API 基址。

全部接口均为明文 GET/POST（JSON），无加密传输。
"""

import logging
import random
import threading
import time

import requests as _requests_module

logger = logging.getLogger(__name__)

# 服务端地址列表的远程获取地址（GET，返回 {"data": [{name, url, sortOrder, ...}], "success": true}）
_SERVER_LIST_URL = "https://buddy.shengdingit.com/api/server_endpoints"

# 动态获取的服务端地址（首次请求时从远程加载，缓存 10 分钟）
_server_list_cache: list = []
_server_list_expire: float = 0.0
_server_list_lock = threading.Lock()
_SERVER_LIST_TTL = 600  # 10 分钟缓存

# 本地开发模式：True 时使用 http://127.0.0.1:5000 作为服务端地址，不从远程获取
_LOCAL_MODE = False
_LOCAL_SERVER = "http://127.0.0.1:5000"

# 全局 Session（明文接口，忽略系统代理环境变量）
_plain_session = _requests_module.Session()
_plain_session.trust_env = False  # 忽略系统代理环境变量


def set_local_mode(enabled: bool):
    """设置本地开发模式

    Args:
        enabled: True 时使用 http://127.0.0.1:5000 作为服务端地址，忽略远程地址列表
    """
    global _LOCAL_MODE
    _LOCAL_MODE = bool(enabled)
    if _LOCAL_MODE:
        # 清空远程缓存，强制走本地地址
        global _server_list_cache, _server_list_expire
        _server_list_cache = []
        _server_list_expire = 0.0


def is_local_mode() -> bool:
    """查询当前是否为本地开发模式"""
    return _LOCAL_MODE


# 触发域名切换的异常类型（网络层错误，非 HTTP 状态码错误）
import urllib3
_FAILABLE_EXC = (
    _requests_module.ConnectionError,
    _requests_module.Timeout,
    urllib3.exceptions.SSLError,
    ConnectionError,
)


def _fetch_server_list(force_refresh: bool = False) -> list:
    """获取服务端地址列表（url 字符串列表）

    本地模式: 直接返回 ["http://127.0.0.1:5000"]
    远程模式: 从 https://buddy.shengdingit.com/api/server_endpoints 获取节点，
             按 sortOrder 排序后返回 url 列表，缓存 10 分钟。

    Args:
        force_refresh: True 时强制刷新缓存（启动时使用，仅远程模式有效）
    """
    global _server_list_cache, _server_list_expire

    # 本地模式：直接返回本地地址
    if _LOCAL_MODE:
        return [_LOCAL_SERVER]

    nodes = _fetch_server_nodes(force_refresh=force_refresh)
    return [n["url"] for n in nodes]


def _fetch_server_nodes(force_refresh: bool = False) -> list:
    """获取服务端节点列表（含 name/url/sortOrder），按 sortOrder 升序排序

    Returns:
        [{"id": ..., "name": ..., "url": ..., "sortOrder": ..., "region": ...}, ...]
        失败或空时返回 []
    """
    global _server_list_cache, _server_list_expire

    # 本地模式：直接返回本地地址
    if _LOCAL_MODE:
        return [{"id": "", "name": "本地", "url": _LOCAL_SERVER, "sortOrder": 0, "region": ""}]

    now = time.time()
    # 缓存未过期且非强制刷新，直接返回
    if not force_refresh and _server_list_cache and now < _server_list_expire:
        return _server_list_cache

    with _server_list_lock:
        # 双重检查：其他线程可能已经更新了缓存
        if not force_refresh and _server_list_cache and now < _server_list_expire:
            return _server_list_cache

        try:
            resp = _plain_session.get(_SERVER_LIST_URL, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data") if isinstance(data, dict) else None
            if not isinstance(items, list):
                raise ValueError(f"响应格式异常: {data}")
            nodes = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                url = str(it.get("url", "")).strip().rstrip("/")
                if not url:
                    continue
                nodes.append({
                    "id": str(it.get("id", "")).strip(),
                    "name": str(it.get("name") or it.get("region") or url).strip(),
                    "url": url,
                    "sortOrder": int(it.get("sortOrder", 0) or 0),
                    "region": str(it.get("region", "")).strip(),
                })
            nodes.sort(key=lambda n: n["sortOrder"])
            if nodes:
                _server_list_cache = nodes
                _server_list_expire = now + _SERVER_LIST_TTL
                logger.info(f"[ServerList] 从远程加载 {len(nodes)} 个节点")
                return nodes
        except Exception as e:
            logger.warning(f"[ServerList] 从远程加载服务端地址失败: {e}")

        # 远程加载失败且有缓存，继续用旧缓存
        if _server_list_cache:
            return _server_list_cache

        # 完全没有地址，返回空列表
        return []


def activate_card(card_key: str) -> dict:
    """激活卡密（POST 明文接口）

    从动态服务端地址列表中随机选取地址调用 /api/activate，明文 JSON 请求。

    Args:
        card_key: 卡密（BC_ 前缀）

    Returns:
        成功: {"success": true, "buddyKey": "sk-xxx", "cardKey": "BC_xxx", "faceValue": 60.0}
        失败: {"success": false, "error": "..."} 或 {"error": "..."}
    """
    payload = {"cardKey": card_key}
    logger.info(f"[activate_card] POST /api/activate | payload={payload}")

    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    last_error = None
    for base in servers:
        url = f"{base}/api/activate"
        try:
            resp = _plain_session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            logger.info(f"[activate_card] {base} 响应 HTTP {resp.status_code} | body={resp.text[:500]}")
            try:
                data = resp.json()
            except Exception as e:
                logger.error(f"[activate_card] 响应 JSON 解析失败: {e}")
                return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            logger.info(f"[activate_card] 解析结果: {data}")
            return data if isinstance(data, dict) else {"success": False, "error": "响应格式异常"}
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[activate_card] {base} 请求失败: {e}，尝试下一个地址")
            continue
        except Exception as e:
            logger.error(f"[activate_card] {base} 异常: {e}")
            return {"success": False, "error": str(e)}

    return {"success": False, "error": str(last_error) if last_error else "无可用服务端地址"}


def get_credits(user_key: str) -> dict:
    """查询用户积分额度（GET 明文接口）

    从动态服务端地址列表中随机选取地址调用 /api/user/credits?userKey=<buddyKey>

    Args:
        user_key: 机器码（即激活返回的 buddyKey）

    Returns:
        {
            "credits": float,
            "totalUsed": float,
            "totalRecharged": float,
            "todayUsed": float,
            "todayRank": int,
            "userKey": str,
        }
        失败时返回 {"error": "..."}
    """
    if not user_key:
        logger.warning("[get_credits] API Key 为空，跳过查询")
        return {"error": "API Key 为空，请先输入 API Key"}

    logger.info(f"[get_credits] GET /api/user/credits | userKey={user_key[:12]}...（长度 {len(user_key)}）")

    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    last_error = None
    for base in servers:
        url = f"{base}/api/user/credits"
        try:
            resp = _plain_session.get(url, params={"userKey": user_key}, timeout=15)
            logger.info(f"[get_credits] {base} 响应 HTTP {resp.status_code} | body={resp.text[:500]}")
            try:
                data = resp.json()
            except Exception as e:
                logger.error(f"[get_credits] 响应 JSON 解析失败: {e}")
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            if isinstance(data, dict) and "credits" in data:
                logger.info(f"[get_credits] 查询成功: credits={data.get('credits')}, totalUsed={data.get('totalUsed')}")
                return data
            logger.warning(f"[get_credits] 响应无 credits 字段: {data}")
            return {"error": data.get("error") or data.get("message") or "未知错误"}
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[get_credits] {base} 请求失败: {e}，尝试下一个地址")
            continue
        except Exception as e:
            logger.error(f"[get_credits] {base} 异常: {e}")
            return {"error": str(e)}

    return {"error": str(last_error) if last_error else "无可用服务端地址"}


def check_version(current_version: str = "", platform: str = "win") -> dict:
    """检查新版本（GET 明文接口）

    GET /api/version/check?platform={platform}&version={version}

    Args:
        current_version: 当前版本号，为空时从 src/VERSION 读取
        platform: 平台 (win/mac/linux/all)

    Returns:
        {
            "success": bool,
            "hasUpdate": bool,
            "version": str,
            "latestVersion": str,
            "platform": str,
            "downloadUrl": str,
            "changelog": str,
            "minVersion": str,
            "isForceUpdate": bool,
            "createdAt": str,
        }
        失败时返回 {"error": "..."}
    """
    import sys as _sys

    if not current_version:
        from ..modules.updater import get_current_version
        current_version = get_current_version()

    if platform == "win":
        platform = "win" if _sys.platform == "win32" else ("mac" if _sys.platform == "darwin" else "linux")

    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    last_error = None
    for base in servers:
        url = f"{base}/api/version/check"
        try:
            resp = _plain_session.get(
                url,
                params={"platform": platform, "version": current_version},
                timeout=15,
            )
            logger.info(f"[check_version] {base} 响应 HTTP {resp.status_code} | body={resp.text[:500]}")
            try:
                data = resp.json()
            except Exception as e:
                logger.error(f"[check_version] 响应 JSON 解析失败: {e}")
                return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}
            if isinstance(data, dict):
                return data
            return {"error": "响应格式异常"}
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[check_version] {base} 请求失败: {e}，尝试下一个地址")
            continue
        except Exception as e:
            logger.error(f"[check_version] {base} 异常: {e}")
            return {"error": str(e)}

    return {"error": str(last_error) if last_error else "无可用服务端地址"}


def get_proxy_models() -> list:
    """获取模型列表（GET 明文接口，OpenAI 兼容）

    固定从 https://buddy.shengdingit.com/api/proxy/models 获取。

    Returns:
        成功: [{"id": ..., "name": ..., "vendor": ..., "maxInputTokens": ...,
                "maxOutputTokens": ..., "supportsToolCall": ..., ...}, ...]
        失败: []
    """
    url = "https://buddy.shengdingit.com/api/proxy/models"
    try:
        resp = _plain_session.get(url, timeout=15)
        logger.info(f"[get_proxy_models] {url} 响应 HTTP {resp.status_code} | body={resp.text[:500]}")
        data = resp.json()
        # OpenAI 兼容格式: {"object": "list", "data": [...]}
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            logger.info(f"[get_proxy_models] 获取到 {len(data['data'])} 个模型")
            return data["data"]
        # 兼容直接返回 list 的情况
        if isinstance(data, list):
            logger.info(f"[get_proxy_models] 获取到 {len(data)} 个模型")
            return data
        logger.warning(f"[get_proxy_models] 响应格式异常: {data}")
    except Exception as e:
        logger.error(f"[get_proxy_models] {url} 请求失败: {e}")
    return []
