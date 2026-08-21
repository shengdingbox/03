"""模型配置纯逻辑 — 从 GUI 页面 (api_proxy / dashboard) 搬出的无 Qt 依赖部分

提供:
1. models.json 读写/增量合并（原 api_proxy._read_existing_models 等）
2. 可配置模型常量与条目构建（原 ApiProxyPage.SUPPORTED_CONFIG_MODELS 等）
3. WorkBuddy / CodeBuddy 配置生成与备份/还原（原 dashboard._build_config_json / _apply_config）

本模块不得 import 任何 PySide6 符号。
"""

import json
import os
from datetime import datetime
from pathlib import Path
from shutil import copy2


# ─── models.json 读写与增量合并（原 api_proxy 模块级函数） ───

def _read_existing_models(target_path: str) -> list:
    """读取 models.json 中已有的模型列表。

    兼容两种格式：
    - WorkBuddy：裸数组 ``[ {...}, {...} ]``
    - CodeBuddy：包裹对象 ``{"models": [ {...} ]}``

    文件不存在或解析失败时返回空列表（不抛异常）。
    """
    if not os.path.exists(target_path):
        return []
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError, ValueError):
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("models"), list):
        return data["models"]
    return []


def _incremental_merge_models(existing: list, new_entries: list):
    """增量合并模型列表。

    匹配规则：当且仅当 ``id`` 与 ``name`` 都相同视为同一模型：
    - 已存在：替换该条目，并做“保留字段合并”——以旧条目为底，新条目字段覆盖之，
      旧条目中独有的字段（新条目未提供）予以保留。
    - 不存在：追加到列表末尾。

    Returns:
        (merged_list, replaced_count, added_count)
    """
    merged = list(existing)
    # 建立 (id, name) -> 索引 的查找表（仅记录首次出现位置，避免重复条目互相覆盖）
    index = {}
    for i, m in enumerate(merged):
        if not isinstance(m, dict):
            continue
        key = (str(m.get("id", "")).strip(), str(m.get("name", "")).strip())
        if key not in index:
            index[key] = i

    replaced = 0
    added = 0
    for entry in new_entries:
        key = (str(entry.get("id", "")).strip(), str(entry.get("name", "")).strip())
        if key in index:
            idx = index[key]
            base = dict(merged[idx]) if isinstance(merged[idx], dict) else {}
            base.update(entry)  # 新字段覆盖旧字段，旧字段中独有的保留
            merged[idx] = base
            replaced += 1
        else:
            merged.append(entry)
            index[key] = len(merged) - 1
            added += 1
    return merged, replaced, added


def _write_models_json(target_path: str, merged: list, wrapper: str) -> None:
    """将合并后的模型列表写回 models.json。

    Args:
        wrapper: ``"array"`` => WorkBuddy 裸数组；``"object"`` => CodeBuddy ``{"models": [...]}``
    """
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        if wrapper == "object":
            json.dump({"models": merged}, f, ensure_ascii=False, indent=2)
        else:
            json.dump(merged, f, ensure_ascii=False, indent=2)


# ─── 可配置模型常量与条目构建（原 ApiProxyPage 类属性/方法） ───

class ModelConfig:
    """模型配置数据与条目构建（原 ApiProxyPage 中与 Qt 无关的部分）"""

    SUPPORTED_CONFIG_MODELS = [
        "hy3", "hy3-preview", "hunyuan-chat", "hunyuan-2.0-thinking",
        "deepseek-v4-pro", "deepseek-v4-flash",
        "deepseek-v3-2-volc", "deepseek-v3-1", "deepseek-v3-0324", "deepseek-r1",
        "glm-5.2", "glm-5.1", "glm-5.0", "glm-5.0-turbo", "glm-5v-turbo", "glm-4.7", "glm-4.6",
        "kimi-k2.6", "kimi-k2.5", "kimi-k2.7",
        "minimax-m3", "minimax-m2.7", "minimax-m2.5",
        "auto",
    ]

    # 模型显示名（按截图大小写处理；未列出的模型显示名等于 id）
    # 注意：图片文件名使用小写 id，与此处显示名解耦
    MODEL_DISPLAY_NAMES = {
        "hy3": "Hy3",
        "kimi-k2.7": "Kimi-K2.7-Code",
    }

    # 模型能力定义 (tool_call, images, reasoning)
    # 全部模型均支持图片输入（vision: true），避免 WorkBuddy 误判禁图
    MODEL_CAPABILITIES = {
        "hy3":                      (True,  True,  True),
        "hy3-preview":              (True,  True,  True),
        "hunyuan-chat":             (True,  True,  True),
        "hunyuan-2.0-thinking":     (True,  True,  True),
        "deepseek-v4-pro":          (True,  True,  True),
        "deepseek-v4-flash":        (True,  True,  True),
        "deepseek-v3-2-volc":       (True,  True,  True),
        "deepseek-v3-1":            (True,  True,  True),
        "deepseek-v3-0324":         (True,  True,  True),
        "deepseek-r1":              (True,  True,  True),
        "glm-5.2":                  (True,  True,  True),
        "glm-5.1":                  (True,  True,  True),
        "glm-5.0":                  (True,  True,  True),
        "glm-5.0-turbo":            (True,  True,  True),
        "glm-5v-turbo":             (True,  True,  True),
        "glm-4.7":                  (True,  True,  True),
        "glm-4.6":                  (True,  True,  True),
        "kimi-k2.6":                (True,  True,  True),
        "kimi-k2.5":                (True,  True,  True),
        "kimi-k2.7":                (True,  True,  True),
        "minimax-m3":               (True,  True,  True),
        "minimax-m2.7":             (True,  True,  True),
        "minimax-m2.5":             (True,  True,  True),
        "auto":                     (True,  True,  True),
    }

    def build_model_entries(self, selected_ids: list, base_url: str,
                            api_key: str, include_custom_protocol: bool = True) -> list:
        """根据选中的模型 id 列表构建 models.json 条目。

        Args:
            selected_ids: 选中的模型 id 列表
            base_url: 接口地址
            api_key: 写入条目的 apiKey
            include_custom_protocol: 是否写入 useCustomProtocol 字段（WorkBuddy 需要，CodeBuddy 不需要）
        """
        entries = []
        for model_id in selected_ids:
            tool_call, images, reasoning = self.MODEL_CAPABILITIES.get(model_id, (True, True, True))
            display_name = self.MODEL_DISPLAY_NAMES.get(model_id, model_id)
            entry = {
                "id": model_id,
                "name": display_name,
                "vendor": "Custom",
                "url": base_url,
                "apiKey": api_key,
                "supportsToolCall": tool_call,
                "supportsImages": images,
                "supportsReasoning": reasoning,
            }
            if include_custom_protocol:
                entry["useCustomProtocol"] = False
            if reasoning:
                entry["reasoning"] = {"supportedEfforts": ["max"]}
            entries.append(entry)
        return entries


# ─── WorkBuddy / CodeBuddy 配置生成与备份（原 dashboard 逻辑） ───

WORKBUDDY_MODELS = str(Path.home() / ".workbuddy" / "models.json")
CODEBUDDY_MODELS = str(Path.home() / ".codebuddy" / "models.json")
CONFIG_BACKUP_DIR = str(Path.home() / ".buddytoolnew" / "config_backups")


def build_config_models(api_key: str, server_models: list, upstream_base: str, prefix: str = "") -> list:
    """根据服务端模型列表 + 机器码 + 上游地址生成 models 配置列表。

    Args:
        api_key: 机器码（buddyKey）
        server_models: get_proxy_models() 返回的模型 dict 列表
        upstream_base: 上游服务端地址（如 http://xxx）
        prefix: 模型前缀（追加到 id/name，可选）

    Returns:
        models 列表；server_models 为空时返回 []
    """
    url = f"{upstream_base.rstrip('/')}/v1/chat/completions"
    models = []
    for m in server_models:
        if not isinstance(m, dict) or not m.get("id"):
            continue
        model_id = m.get("id", "")
        name = m.get("name") or model_id
        if prefix:
            model_id = f"{prefix}{model_id}"
            name = f"{prefix}{name}"
        models.append({
            "id": model_id,
            "name": name,
            "vendor": m.get("vendor", "Buddy"),
            "apiKey": api_key,
            "url": url,
            "maxInputTokens": m.get("maxInputTokens", 128000),
            "maxOutputTokens": m.get("maxOutputTokens", 8192),
            "supportsToolCall": m.get("supportsToolCall", True),
            "supportsImages": m.get("supportsImages", True),
            "supportsReasoning": m.get("supportsReasoning", True),
        })
    return models


def backup_config(client: str) -> str:
    """备份目标客户端的 models.json 到备份目录。

    Args:
        client: "workbuddy" 或 "codebuddy"

    Returns:
        备份文件路径；无原文件或备份失败返回 ""
    """
    target_path = WORKBUDDY_MODELS if client == "workbuddy" else CODEBUDDY_MODELS
    src = Path(target_path)
    if not src.exists():
        return ""

    backup_root = Path(CONFIG_BACKUP_DIR)
    backup_root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backup_root / f"{client}_{ts}.json"
    try:
        copy2(str(src), str(dst))
        return str(dst)
    except Exception:
        return ""


def write_client_config(client: str, merged: list) -> str:
    """写入客户端 models.json（自动备份原文件）。

    Args:
        client: "workbuddy" 或 "codebuddy"
        merged: 合并后的模型列表

    Returns:
        写入的目标路径
    """
    backup_config(client)
    target_path = WORKBUDDY_MODELS if client == "workbuddy" else CODEBUDDY_MODELS
    wrapper = "array" if client == "workbuddy" else "object"
    _write_models_json(target_path, merged, wrapper=wrapper)
    return target_path


def restore_config(client: str) -> str:
    """从备份目录还原指定客户端最近一次备份。

    Args:
        client: "workbuddy" 或 "codebuddy"

    Returns:
        还原目标路径；无备份时抛 FileNotFoundError
    """
    backup_root = Path(CONFIG_BACKUP_DIR)
    if not backup_root.exists():
        raise FileNotFoundError(f"备份目录不存在: {backup_root}")

    prefix = client.lower() + "_"
    backups = sorted(
        [f for f in backup_root.iterdir() if f.name.startswith(prefix) and f.suffix == ".json"],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not backups:
        raise FileNotFoundError(f"未找到 {client} 的备份文件")

    latest = backups[0]
    target_path = WORKBUDDY_MODELS if client == "workbuddy" else CODEBUDDY_MODELS
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    copy2(str(latest), str(target))
    return target_path
