"""i18n 国际化模块"""

# 当前语言
_current_lang = "zh-CN"

# 默认中文翻译（仅保留实际被引用的 key）
_zh_cn = {
    # 导航 / 页面标题
    "nav.dashboard": "仪表盘",

    # 通用
    "common.cancel": "取消",
    "common.confirm": "确认",
    "common.warning": "警告",

    # 账号管理
    "accounts.title": "额度管理",
    "accounts.add_account": "激活卡密",

    # API 代理
    "api_proxy.title": "API 代理服务",
}


def set_language(lang: str):
    """设置当前语言"""
    global _current_lang
    _current_lang = lang


def get_language() -> str:
    """获取当前语言"""
    return _current_lang


def t(key: str, **kwargs) -> str:
    """翻译 key 到当前语言的文本"""
    text = _zh_cn.get(key, key)
    if kwargs:
        text = text.format(**kwargs)
    return text
