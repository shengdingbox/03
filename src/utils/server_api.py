"""服务端 API 客户端 — 积分查询、卡密兑换等

主域名: https://buddy.shengdingit.com/api
备用域名: https://api.shengdingit.com/api（主域名网络异常时自动切换）

支持 AES-256-GCM 加密传输 + HMAC-SHA256 签名。
"""

import json
import base64
import os
import time
import hmac
import hashlib
import logging

import requests as _requests_module
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ._obfuscate import get as _obf_get, get_bytes as _obf_bytes
from .ssl_pinning import install_pinning as _install_pinning

logger = logging.getLogger(__name__)

SERVER_BASE = _obf_get("SERVER_BASE")
SERVER_BASE_FALLBACK = _obf_get("SERVER_BASE_FALLBACK")

# 当前生效的 API 基址（主域名故障后自动切换到备用域名）
_active_base = SERVER_BASE

# AES-256-GCM 密钥（与服务端一致，hex → 32 字节）
_AES_KEY = bytes.fromhex(_obf_get("AES_KEY_HEX"))

# HMAC-SHA256 签名
_API_KEY = _obf_get("API_KEY")
_HMAC_KEY = _obf_bytes("HMAC_KEY")

# 全局 Session，启用证书固定
_session = _requests_module.Session()
_session.trust_env = False  # 忽略系统代理环境变量
_install_pinning(_session)


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

    先用当前活跃域名请求，若发生网络层异常（连接超时/DNS 解析失败/SSL 错误），
    自动切换到备用域名重试一次。

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

    bases_to_try = [_active_base]
    if _active_base == SERVER_BASE:
        bases_to_try.append(SERVER_BASE_FALLBACK)
    else:
        bases_to_try.append(SERVER_BASE)

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
            if base != _active_base:
                logger.info(f"[Failover] 切换到备用域名: {base}")
                _active_base = base
            return _decrypt_body(resp.text)
        except _FAILABLE_EXC as e:
            last_error = e
            logger.warning(f"[Failover] {base} 请求失败: {e}，尝试下一个域名")
            continue
        except Exception as e:
            # 非网络层异常（如解密失败），不切换域名
            logger.error(f"[Failover] {base} 非网络异常: {e}")
            return {"error": str(e)}

    logger.error(f"[Failover] 所有域名均不可用，最后错误: {last_error}")
    return {"error": str(last_error)}


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


def get_credits(user_key: str = None) -> dict:
    """查询用户积分额度（POST 加密接口）

    Args:
        user_key: 用户密钥（机器码），为空时使用本机动态机器码

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
    return _post_with_failover("/user/credits", {"userKey": key}, timeout=15)


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


def get_buddykey(user_key: str = None) -> dict:
    """获取激活码 BuddyKey（POST 加密接口）

    Args:
        user_key: 机器码，为空时使用本机动态机器码

    Returns:
        成功: {"success": true, "userKey": "...", "buddyKey": "ck_...", "expiresAt": "...", "balance": ..., "buddyKeyId": int}
        失败: {"success": false, "error": "..."}
    """
    from .machine import get_machine_code

    key = user_key or get_machine_code()
    return _post_with_failover("/buddykey/get", {"userKey": key}, timeout=30)


def check_version(current_version: str = "", platform: str = "win") -> dict:
    """检查新版本（POST 加密接口）

    Args:
        current_version: 当前版本号，为空时从 src/VERSION 读取
        platform: 平台 (win/mac/linux/all)

    Returns:
        {
            "has_update": bool,
            "version": str,
            "latest_version": str,
            "platform": str,
            "download_url": str,
            "changelog": str,
            "min_version": str,
            "is_force_update": bool,
            "created_at": str,
        }
        失败时返回 {"error": "..."}
    """
    import sys as _sys

    if not current_version:
        from ..modules.updater import get_current_version
        current_version = get_current_version()

    if platform == "win":
        platform = "win" if _sys.platform == "win32" else ("mac" if _sys.platform == "darwin" else "linux")

    payload = {
        "platform": platform,
        "current_version": current_version,
    }
    return _post_with_failover("/version/check", payload, timeout=15)


def get_models_list() -> dict:
    """获取可用模型列表（POST 加密接口）

    Returns:
        {"models": [{"id": ..., "name": ..., "maxInputTokens": ..., ...}]}
        失败时返回 {"error": "..."}
    """
    return _post_with_failover("/models/list", {}, timeout=15)


def report_usage(
    device_fingerprint: str,
    credits_used: float,
    model: str = "",
    request_tokens: int = 0,
    response_tokens: int = 0,
    upstream_id: str = "",
    record_id: str = "",
) -> dict:
    """使用量上报（POST 加密接口）

    Args:
        device_fingerprint: 设备码（机器码）
        credits_used: 消耗积分
        model: 模型名称
        request_tokens: 请求 token 数
        response_tokens: 响应 token 数
        upstream_id: 上游 ID
        record_id: 记录 ID

    Returns:
        {"success": true, "device_fingerprint": "...", "credits_used": ..., "balance_before": ..., "balance_after": ..., "report_id": int}
    """
    payload = {
        "device_fingerprint": device_fingerprint,
        "credits_used": credits_used,
        "model": model,
        "request_tokens": request_tokens,
        "response_tokens": response_tokens,
        "upstream_id": upstream_id,
    }
    if record_id:
        payload["record_id"] = record_id

    return _post_with_failover("/usage/report", payload, timeout=15)
