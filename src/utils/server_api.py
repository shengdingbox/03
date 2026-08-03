"""服务端 API 客户端 — 积分查询、卡密兑换等

服务端地址动态获取：从 https://file-1303165843.cos.ap-guangzhou.myqcloud.com/server.txt
下载每行一个地址，随机取一个作为服务端 API 基址。

支持 AES-256-GCM 加密传输 + HMAC-SHA256 签名。
"""

import json
import base64
import os
import time
import hmac
import hashlib
import logging
import random
import threading

import requests as _requests_module
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ._obfuscate import get as _obf_get, get_bytes as _obf_bytes
from .ssl_pinning import install_pinning as _install_pinning

logger = logging.getLogger(__name__)

# 服务端地址列表的远程获取地址
_SERVER_LIST_URL = "https://file-1303165843.cos.ap-guangzhou.myqcloud.com/server.txt"

# 动态获取的服务端地址（首次请求时从远程加载，缓存 10 分钟）
_active_base: str = ""
_server_list_cache: list = []
_server_list_expire: float = 0.0
_server_list_lock = threading.Lock()
_SERVER_LIST_TTL = 600  # 10 分钟缓存

# 本地开发模式：True 时使用 http://127.0.0.1:5000 作为服务端地址，不从远程获取
_LOCAL_MODE = False

# AES-256-GCM 密钥（与服务端一致，hex → 32 字节）
_AES_KEY = bytes.fromhex(_obf_get("AES_KEY_HEX"))

# HMAC-SHA256 签名
_API_KEY = _obf_get("API_KEY")
_HMAC_KEY = _obf_bytes("HMAC_KEY")

# 全局 Session，启用证书固定
_session = _requests_module.Session()
_session.trust_env = False  # 忽略系统代理环境变量
_install_pinning(_session)

# ─── 明文接口（新激活/查分服务，暂不加密） ───
# 服务端地址动态获取，与加密接口共用 _fetch_server_list()
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


_LOCAL_SERVER = "http://127.0.0.1:5000"


def _fetch_server_list(force_refresh: bool = False) -> list:
    """获取服务端地址列表

    本地模式: 直接返回 ["http://127.0.0.1:5000"]
    远程模式: 从远程地址列表下载，每行一个，返回去重后的列表

    Args:
        force_refresh: True 时强制刷新缓存（启动时使用，仅远程模式有效）
    """
    global _server_list_cache, _server_list_expire

    # 本地模式：直接返回本地地址
    if _LOCAL_MODE:
        return [_LOCAL_SERVER]

    now = time.time()
    # 缓存未过期且非强制刷新，直接返回
    if not force_refresh and _server_list_cache and now < _server_list_expire:
        return _server_list_cache

    with _server_list_lock:
        # 双重检查：其他线程可能已经更新了缓存
        if not force_refresh and _server_list_cache and now < _server_list_expire:
            return _server_list_cache

        try:
            resp = _requests_module.get(_SERVER_LIST_URL, timeout=10)
            resp.raise_for_status()
            lines = [
                line.strip().rstrip("/")
                for line in resp.text.splitlines()
                if line.strip() and not line.strip().startswith("#")
            ]
            # 去重并保留顺序
            seen = set()
            unique = []
            for line in lines:
                if line not in seen:
                    seen.add(line)
                    unique.append(line)
            if unique:
                _server_list_cache = unique
                _server_list_expire = now + _SERVER_LIST_TTL
                logger.info(f"[ServerList] 从远程加载 {len(unique)} 个服务端地址")
                return unique
        except Exception as e:
            logger.warning(f"[ServerList] 从远程加载服务端地址失败: {e}")

        # 远程加载失败且有缓存，继续用旧缓存
        if _server_list_cache:
            return _server_list_cache

        # 完全没有地址，返回空列表
        return []


def _build_signed_headers() -> dict:
    """构建带 HMAC-SHA256 签名的请求头"""
    timestamp = str(int(time.time()))
    msg = f"api_key={_API_KEY}&timestamp={timestamp}"
    sign = hmac.new(_HMAC_KEY, msg.encode("utf-8"), hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "X-API-Key": _API_KEY,
        "X-Timestamp": timestamp,
        "X-API-Sign": sign,
        "X-Sign-Method": "hmac-sha256",
    }


# 触发域名切换的异常类型（网络层错误，非 HTTP 状态码错误）
import urllib3
_FAILABLE_EXC = (
    _requests_module.ConnectionError,
    _requests_module.Timeout,
    urllib3.exceptions.SSLError,
    ConnectionError,
)


def _post_with_failover(path: str, payload: dict, timeout: int = 15) -> dict:
    """带域名故障转移的 POST 请求

    从远程地址列表中随机选取服务端地址进行请求，若发生网络层异常，
    自动尝试列表中的下一个地址。

    Args:
        path: API 路径（如 /user/credits）
        payload: 请求体 dict（会自动加密）
        timeout: 超时秒数

    Returns:
        解密后的响应 dict，或 {"error": "..."}
    """
    global _active_base

    encrypted_body = _encrypt_body(payload)
    headers = _build_signed_headers()

    # 获取服务端地址列表（随机打乱顺序用于故障转移）
    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    bases_to_try = servers if servers else []

    last_error = None
    for base in bases_to_try:
        url = f"{base}{path}"
        try:
            resp = _session.post(
                url,
                data=encrypted_body,
                headers=headers,
                timeout=timeout,
            )
            # 请求成功（网络层），更新活跃域名
            _active_base = base
            return _decrypt_body(resp.text)
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[Failover] {base} 请求失败: {e}，尝试下一个地址")
            continue
        except Exception as e:
            # 非网络层异常（如解密失败），不切换地址
            logger.error(f"[Failover] {base} 非网络异常: {e}")
            return {"error": str(e)}

    logger.error(f"[Failover] 所有服务端地址均不可用，最后错误: {last_error}")
    return {"error": str(last_error) if last_error else "无可用服务端地址"}


def _encrypt_body(data: dict) -> str:
    """AES-256-GCM 加密请求体

    流程:
        1. JSON 紧凑序列化
        2. 随机 12 字节 nonce
        3. AES-256-GCM 加密 → ciphertext+tag
        4. 拼接 nonce + ciphertext_and_tag → base64
        5. 包装为 {"data": "<base64>"}

    Returns:
        加密后的 JSON 字符串
    """
    plaintext = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(12)
    aesgcm = AESGCM(_AES_KEY)
    # cryptography 库的 encrypt 返回 ciphertext+tag（tag 在末尾）
    ct_and_tag = aesgcm.encrypt(nonce, plaintext, associated_data=None)

    # 服务端格式: nonce(12) + tag(16) + ciphertext
    # cryptography 库输出: ciphertext + tag(16)
    # 需要拆分重组: ciphertext = ct_and_tag[:-16], tag = ct_and_tag[-16:]
    ciphertext = ct_and_tag[:-16]
    tag = ct_and_tag[-16:]
    raw = nonce + tag + ciphertext
    data_b64 = base64.b64encode(raw).decode("ascii")
    return json.dumps({"data": data_b64})


def _decrypt_body(body_text: str) -> dict:
    """AES-256-GCM 解密响应体

    Args:
        body_text: 响应体原始文本

    Returns:
        解密后的 dict，如果非加密格式则直接 JSON 解析
    """
    try:
        body_json = json.loads(body_text)
    except Exception:
        return {"error": "响应非有效 JSON", "raw": body_text[:500]}

    # 非加密响应（GET 接口等），直接返回
    if "data" not in body_json:
        return body_json

    data_b64 = body_json["data"]
    raw = base64.b64decode(data_b64)

    # 服务端格式: nonce(12) + tag(16) + ciphertext
    nonce = raw[:12]
    tag = raw[12:28]
    ciphertext = raw[28:]

    # cryptography 库需要 ciphertext+tag 拼接
    ct_and_tag = ciphertext + tag
    aesgcm = AESGCM(_AES_KEY)
    try:
        plaintext = aesgcm.decrypt(nonce, ct_and_tag, associated_data=None)
        return json.loads(plaintext.decode("utf-8"))
    except Exception as e:
        logger.error(f"解密响应失败: {e}")
        return {"error": f"解密失败: {e}"}


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


def get_credits(user_key: str = None) -> dict:
    """查询用户积分额度（GET 明文接口）

    从动态服务端地址列表中随机选取地址调用 /api/user/credits?userKey=<buddyKey>

    Args:
        user_key: 机器码（即激活返回的 buddyKey），为空时使用本机已保存的机器码

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
    from .machine import get_machine_code

    key = user_key or get_machine_code()
    if not key:
        logger.warning("[get_credits] 机器码为空，未激活，跳过查询")
        return {"error": "未激活，请先激活卡密获取 BuddyKey"}

    logger.info(f"[get_credits] GET /api/user/credits | userKey={key[:12]}...（长度 {len(key)}）")

    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    last_error = None
    for base in servers:
        url = f"{base}/api/user/credits"
        try:
            resp = _plain_session.get(url, params={"userKey": key}, timeout=15)
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


def get_today_usage(user_key: str = None, page: int = 1, page_size: int = 20) -> tuple:
    """获取今日使用记录（GET 明文接口，支持分页）

    GET /api/user/today-usage?userKey={userKey}&page={page}&pageSize={pageSize}

    Args:
        user_key: 机器码，为空时使用本机已保存的机器码
        page: 页码（从 1 开始）
        page_size: 每页条数

    Returns:
        (records, total): records 为当前页记录列表，total 为总记录数
        失败时返回 ([], 0)
    """
    from .machine import get_machine_code

    key = user_key or get_machine_code()
    if not key:
        logger.warning("[get_today_usage] 机器码为空，未激活，跳过查询")
        return [], 0

    logger.info(f"[get_today_usage] GET /api/user/today-usage | userKey={key[:12]}... page={page} pageSize={page_size}")

    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    last_error = None
    for base in servers:
        url = f"{base}/api/user/today-usage"
        try:
            resp = _plain_session.get(url, params={
                "userKey": key,
                "page": page,
                "pageSize": page_size,
            }, timeout=15)
            logger.info(f"[get_today_usage] {base} 响应 HTTP {resp.status_code} | body={resp.text[:500]}")
            try:
                data = resp.json()
            except Exception as e:
                logger.error(f"[get_today_usage] 响应 JSON 解析失败: {e}")
                last_error = e
                continue

            records = []
            total = 0
            if isinstance(data, dict):
                records = data.get("records") or data.get("data") or []
                total = data.get("total", 0) or data.get("totalCount", 0) or len(records)
            elif isinstance(data, list):
                records = data
                total = len(data)

            logger.info(f"[get_today_usage] 获取到 {len(records)} 条记录，总数 {total}")
            return records, total
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[get_today_usage] {base} 请求失败: {e}，尝试下一个地址")
            continue
        except Exception as e:
            logger.error(f"[get_today_usage] {base} 异常: {e}")
            last_error = e
            continue

    logger.error(f"[get_today_usage] 所有服务端地址均不可用，最后错误: {last_error}")
    return [], 0


def redeem(card_key: str, user_key: str = None, operator: str = "user") -> dict:
    """卡密兑换（POST 加密接口）

    Args:
        card_key: 卡密 (BC_ 前缀)
        user_key: 机器码，为空时使用本机动态机器码
        operator: 操作者标识

    Returns:
        成功: {"success": true, "cardKey": "...", "userKey": "...", "amount": ..., "balanceCredits": ...}
        失败: {"error": "..."} 或 {"success": false, ...}
    """
    from .machine import get_machine_code

    key = user_key or get_machine_code()
    payload = {
        "cardKey": card_key,
        "userKey": key,
        "operator": operator,
    }
    return _post_with_failover("/redeem", payload, timeout=30)


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


def get_models_list() -> dict:
    """获取可用模型列表（POST 加密接口）

    Returns:
        {"models": [{"id": ..., "name": ..., "maxInputTokens": ..., ...}]}
        失败时返回 {"error": "..."}
    """
    return _post_with_failover("/models/list", {}, timeout=15)


def get_proxy_models() -> list:
    """获取模型列表（GET 明文接口，OpenAI 兼容）

    GET /api/proxy/models — 返回服务端支持的模型列表。

    Returns:
        成功: [{"id": ..., "name": ..., "vendor": ..., "maxInputTokens": ...,
                "maxOutputTokens": ..., "supportsToolCall": ..., ...}, ...]
        失败: []
    """
    servers = list(_fetch_server_list())
    if servers:
        random.shuffle(servers)
    last_error = None
    for base in servers:
        url = f"{base}/api/proxy/models"
        try:
            resp = _plain_session.get(url, timeout=15)
            logger.info(f"[get_proxy_models] {base} 响应 HTTP {resp.status_code} | body={resp.text[:500]}")
            try:
                data = resp.json()
            except Exception as e:
                logger.error(f"[get_proxy_models] 响应 JSON 解析失败: {e}")
                last_error = e
                continue
            # OpenAI 兼容格式: {"object": "list", "data": [...]}
            if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
                logger.info(f"[get_proxy_models] 获取到 {len(data['data'])} 个模型")
                return data["data"]
            # 兼容直接返回 list 的情况
            if isinstance(data, list):
                logger.info(f"[get_proxy_models] 获取到 {len(data)} 个模型")
                return data
            logger.warning(f"[get_proxy_models] 响应格式异常: {data}")
            last_error = "响应格式异常"
            continue
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[get_proxy_models] {base} 请求失败: {e}，尝试下一个地址")
            continue
        except Exception as e:
            logger.error(f"[get_proxy_models] {base} 异常: {e}")
            last_error = e
            continue

    logger.error(f"[get_proxy_models] 所有服务端地址均不可用，最后错误: {last_error}")
    return []
