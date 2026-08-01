"""机器码与硬件特征工具

本模块提供两类能力：
1. 硬件特征采集（_get_disk_serial / _get_cpu_id / _get_hostname）— 仅供 proxy_db.key
   的本地数据库加密密钥派生使用（见 proxy_server._get_local_db_key），不得删除。
2. 机器码读写（get_machine_code / set_machine_code / get_short_machine_code）— 机器码
   不再基于硬件计算，而是激活卡密时由服务端返回的 buddyKey 充当，持久化在
   proxy_db.key 的 settings.machine_code 字段。未激活时返回空字符串。
"""

import hashlib
import platform
import os
import logging

logger = logging.getLogger(__name__)

# Windows 下隐藏子进程窗口的标志
_NO_WINDOW = 0x08000000 if platform.system() == "Windows" else 0


def _get_disk_serial() -> str:
    """获取磁盘序列号（Windows 用 wmic，macOS 用 ioreg，Linux 用 /sys）"""
    try:
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["wmic", "diskdrive", "get", "serialnumber"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
            )
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            if lines:
                # 跳过标题行，取第一个序列号
                serials = [l for l in lines if l.lower() != "serialnumber"]
                if serials:
                    return serials[0]
        elif platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformIODevice"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.splitlines():
                if "IOPlatformSerialNumber" in line:
                    parts = line.split('"')
                    if len(parts) >= 4:
                        return parts[-2]
        elif platform.system() == "Linux":
            # 尝试读取 /sys/class/dmi/id/product_serial
            try:
                with open("/sys/class/dmi/id/product_serial", "r") as f:
                    return f.read().strip()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"获取磁盘序列号失败: {e}")
    return ""


def _get_cpu_id() -> str:
    """获取 CPU ID"""
    try:
        if platform.system() == "Windows":
            import subprocess
            result = subprocess.run(
                ["wmic", "cpu", "get", "ProcessorId"],
                capture_output=True, text=True, timeout=5,
                creationflags=_NO_WINDOW,
            )
            lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            if lines:
                ids = [l for l in lines if l.lower() != "processorid"]
                if ids:
                    return ids[0]
        elif platform.system() == "Darwin":
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        elif platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.lower().startswith("model name"):
                            return line.split(":")[-1].strip()
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"获取 CPU ID 失败: {e}")
    return ""


def _get_hostname() -> str:
    """获取主机名"""
    try:
        return platform.node() or os.uname().nodename
    except Exception:
        return ""


# ─── 机器码读写（基于激活的 buddyKey，不再硬件计算） ───

# 内存缓存，避免重复 IO
_cached_machine_code = None


def _load_cached_machine_code() -> str:
    """从 proxy_db.key 读取已保存的机器码（即激活时存入的 buddyKey）"""
    try:
        # 延迟导入，避免循环依赖
        from ..modules.proxy_server import ProxyDatabase
        db = ProxyDatabase.get_instance()
        settings = db.get_settings()
        return settings.get("machine_code", "") or ""
    except Exception as e:
        logger.debug(f"从 proxy_db.key 读取机器码失败: {e}")
        return ""


def _persist_machine_code(code: str) -> None:
    """将机器码保存到 proxy_db.key 的 settings.machine_code 字段"""
    try:
        from ..modules.proxy_server import ProxyDatabase
        db = ProxyDatabase.get_instance()
        db.update_settings({"machine_code": code})
    except Exception as e:
        logger.debug(f"保存机器码到 proxy_db.key 失败: {e}")


def set_machine_code(code: str) -> None:
    """设置机器码（激活卡密成功后调用，code 为服务端返回的 buddyKey）

    同时更新内存缓存和持久化存储。
    """
    global _cached_machine_code
    _cached_machine_code = code or ""
    if code:
        _persist_machine_code(code)


def get_machine_code() -> str:
    """获取当前机器码

    机器码 = 激活卡密时服务端返回的 buddyKey，持久化在 proxy_db.key。
    未激活时返回空字符串。

    Returns:
        机器码字符串（buddyKey），未激活时为 ""
    """
    global _cached_machine_code
    if _cached_machine_code is not None:
        return _cached_machine_code

    # 从 proxy_db.key 读取
    cached = _load_cached_machine_code()
    _cached_machine_code = cached
    return cached
