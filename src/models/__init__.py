"""数据模型 - 账号、平台、配置等核心数据结构"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Platform(Enum):
    """支持的平台 - CodeBuddy 与 WorkBuddy 账号通用，仅登录方式不同"""
    CODEBUDDY = "codebuddy"
    WORKBUDDY = "workbuddy"


class AccountStatus(Enum):
    """账号状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    QUOTA_EXHAUSTED = "quota_exhausted"
    ERROR = "error"


class PlanType(Enum):
    """套餐类型"""
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"


@dataclass
class CheckinInfo:
    """签到信息（仅作为 Account 字段保留，用于数据库序列化；签到功能已删除）"""
    last_checkin_time: Optional[datetime] = None
    streak_days: int = 0
    rewards: list = field(default_factory=list)
    daily_credit: int = 0          # 今日获得积分
    total_credits: int = 0         # 累计签到获得积分


@dataclass
class ResourcePackage:
    """资源包（积分包）信息 - 对应 /v2/billing/meter/get-user-resource 的 Account 条目"""
    package_name: str = ""          # 资源包名称（如 "CodeBuddy个人体验版"）
    package_type: str = ""         # 资源包类型（1=免费, 2=付费, 4=体验）
    product_name: str = ""         # 产品名称（如 "腾讯云代码助手"）
    sub_product_name: str = ""     # 子产品名称（如 "腾讯云代码助手 (IDE)"）
    capacity_unit: str = "credits" # 单位
    capacity_size: float = 0.0     # 总量
    capacity_remain: float = 0.0   # 剩余
    capacity_used: float = 0.0     # 已用
    cycle_size: float = 0.0        # 当前周期总量
    cycle_remain: float = 0.0      # 当前周期剩余
    cycle_start: str = ""          # 周期开始时间
    cycle_end: str = ""            # 周期结束时间
    status: int = 0                # 状态（0=正常）
    resource_id: str = ""          # 资源 ID


@dataclass
class QuotaInfo:
    """配额信息（旧版，保留兼容）"""
    hourly_suggestions: int = 0
    hourly_suggestions_limit: int = 0
    weekly_chat: int = 0
    weekly_chat_limit: int = 0
    credits_remaining: float = 0.0
    credits_total: float = 0.0
    reset_time: Optional[datetime] = None
    last_updated: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_at: Optional[datetime] = None
    # 新增：多资源包
    packages: list = field(default_factory=list)  # List[ResourcePackage]
    payment_type: str = ""            # 付费类型


@dataclass
class Account:
    """通用账号模型"""
    uid: str = ""
    nickname: str = ""
    platform: Platform = Platform.CODEBUDDY
    status: AccountStatus = AccountStatus.ACTIVE
    status_reason: str = ""
    plan_type: PlanType = PlanType.FREE
    domain: str = ""
    enterprise_id: str = ""
    enterprise_name: str = ""
    auth_token: str = ""
    auth_raw: str = ""
    ck: str = ""                    # Cookie / 登录URL
    api_key: str = ""               # API Key (从服务器获取)
    profile_raw: str = ""
    usage_raw: str = ""
    checkin: CheckinInfo = field(default_factory=CheckinInfo)
    quota: QuotaInfo = field(default_factory=QuotaInfo)
    created_at: Optional[datetime] = None
    last_used: Optional[datetime] = None
