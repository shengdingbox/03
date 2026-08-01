"""仪表盘页面 — 支持响应式缩放，窗口缩小时文字和UI同步缩小"""

import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QPushButton, QButtonGroup, QApplication, QScrollArea, QSpinBox, QComboBox,
    QMessageBox, QCheckBox, QProgressBar, QDialog, QLineEdit
)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QPalette

from ...i18n import t
from ...utils.store import load_accounts, load_setting, save_setting
from ...models import AccountStatus
from ...modules.proxy_server import ProxyDatabase
from ..styles.theme import LIGHT_THEME, DARK_THEME

logger = logging.getLogger(__name__)


def _current_theme_colors() -> dict:
    """获取当前主题颜色字典"""
    theme = load_setting("theme", "system")
    if theme == "system":
        app = QApplication.instance()
        is_dark = bool(app and app.styleHints().colorScheme() == Qt.ColorScheme.Dark)
        theme = "dark" if is_dark else "light"
    return DARK_THEME if theme == "dark" else LIGHT_THEME


class StatCard(QFrame):
    """统计卡片 — 支持响应式缩放"""

    _BASE_ICON = 20
    _BASE_TITLE = 12
    _BASE_VALUE = 24
    _BASE_MH = 16
    _BASE_MV = 12
    _BASE_SPACING = 8

    def __init__(self, title: str, value: str, icon: str = "", color_key: str = "accent"):
        """
        Args:
            color_key: 主题色板键名，如 accent / success / warning / error
        """
        super().__init__()
        self.setObjectName("card")
        self._color_key = color_key
        self._colors = _current_theme_colors()
        self._scale = 1.0
        self._icon_label = None

        layout = QVBoxLayout(self)
        layout.setSpacing(self._BASE_SPACING)
        layout.setContentsMargins(self._BASE_MH, self._BASE_MV, self._BASE_MH, self._BASE_MV)

        header = QHBoxLayout()
        if icon:
            self._icon_label = QLabel(icon)
            self._icon_label.setStyleSheet(f"font-size: {self._BASE_ICON}px;")
            header.addWidget(self._icon_label)
        title_label = QLabel(title)
        title_label.setObjectName("card_label")
        title_label.setStyleSheet(f"font-size: {self._BASE_TITLE}px; color: {self._colors['text_tertiary']};")
        header.addWidget(title_label)
        header.addStretch()
        layout.addLayout(header)

        self._value_label = QLabel(value)
        self._value_label.setObjectName("card_value")
        self._apply_value_style()
        layout.addWidget(self._value_label)

    def _apply_value_style(self):
        """根据当前主题色和缩放比例更新数值标签样式"""
        color = self._colors.get(self._color_key, self._colors["accent"])
        size = int(self._BASE_VALUE * self._scale)
        self._value_label.setStyleSheet(f"color: {color}; font-size: {size}px; font-weight: 700;")

    def set_value(self, text: str):
        self._value_label.setText(text)

    def apply_scale(self, scale: float):
        """响应式缩放：调整字体大小、边距、间距"""
        self._scale = scale
        layout = self.layout()
        mh = int(self._BASE_MH * scale)
        mv = int(self._BASE_MV * scale)
        layout.setContentsMargins(mh, mv, mh, mv)
        layout.setSpacing(int(self._BASE_SPACING * scale))
        if self._icon_label:
            self._icon_label.setStyleSheet(f"font-size: {int(self._BASE_ICON * scale)}px;")
        title_label = self.findChild(QLabel, "card_label")
        if title_label:
            title_label.setStyleSheet(
                f"font-size: {int(self._BASE_TITLE * scale)}px; color: {self._colors['text_tertiary']};"
            )
        self._apply_value_style()

    def apply_theme(self, colors: dict):
        """主题切换时刷新颜色（保持当前缩放比例）"""
        self._colors = colors
        title_label = self.findChild(QLabel, "card_label")
        if title_label:
            title_label.setStyleSheet(
                f"font-size: {int(self._BASE_TITLE * self._scale)}px; color: {colors['text_tertiary']};"
            )
        self._apply_value_style()


class CacheHitRateChart(QWidget):
    """缓存命中率环形图 — 用 QPainter 手绘 donut chart，支持响应式缩放"""

    _BASE_SIZE = 140
    _BASE_PEN = 12
    _BASE_FONT = 18

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rate = 0.0  # 缓存命中率 (0~1)
        self._colors = _current_theme_colors()
        self._scale = 1.0
        self.setFixedSize(self._BASE_SIZE, self._BASE_SIZE)

    def set_rate(self, rate: float):
        """设置命中率（0~1），触发重绘"""
        self._rate = max(0.0, min(1.0, float(rate)))
        self.update()

    def apply_scale(self, scale: float):
        """响应式缩放：调整图表尺寸"""
        self._scale = scale
        size = int(self._BASE_SIZE * scale)
        self.setFixedSize(size, size)

    def apply_theme(self, colors: dict):
        """主题切换时刷新颜色"""
        self._colors = colors
        self.update()

    def paintEvent(self, event):
        """绘制环形图（画笔宽度和字号随缩放比例调整）"""
        colors = self._colors
        color_hit = QColor(colors["success"])
        color_miss = QColor(colors["border"])
        color_text = QColor(colors["text_primary"])

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        pen_width = max(6, int(self._BASE_PEN * self._scale))
        rect = QRectF(
            pen_width / 2, pen_width / 2,
            w - pen_width, h - pen_width
        )

        # 背景圆环（未命中部分）
        bg_pen = QPen(color_miss, pen_width)
        bg_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(bg_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # 命中部分（从12点钟方向顺时针绘制）
        if self._rate > 0:
            hit_pen = QPen(color_hit, pen_width)
            hit_pen.setCapStyle(Qt.RoundCap)
            painter.setPen(hit_pen)
            start_angle = 90 * 16
            span_angle = int(-self._rate * 360 * 16)
            painter.drawArc(rect, start_angle, span_angle)

        # 中心文字（百分比）
        painter.setPen(color_text)
        font = QFont()
        font.setPixelSize(max(10, int(self._BASE_FONT * self._scale)))
        font.setBold(True)
        painter.setFont(font)
        text = f"{self._rate * 100:.1f}%"
        painter.drawText(rect, Qt.AlignCenter, text)

        painter.end()


class CheckableBox(QCheckBox):
    """自定义复选框 — 用 QPainter 绘制清晰的对勾"""

    def __init__(self, text: str, accent_color: str, border_color: str, text_color: str, parent=None):
        super().__init__(text, parent)
        self._accent = accent_color
        self._border = border_color
        self._text_color = text_color
        self.setStyleSheet(f"""
            QCheckBox {{
                color: {text_color};
                font-size: 13px;
                spacing: 8px;
                padding: 4px 0;
            }}
        """)

    def paintEvent(self, event):
        """自绘：文字正常绘制，indicator 手动绘制对勾"""
        from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
        from PySide6.QtCore import QRect, Qt, QPoint, QLineF

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 绘制 indicator 方框
        box_size = 18
        box_y = (self.height() - box_size) // 2
        box_rect = QRect(0, box_y, box_size, box_size)

        if self.isChecked():
            # 蓝色背景
            painter.setBrush(QBrush(QColor(self._accent)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(box_rect, 4, 4)

            # 白色对勾
            pen = QPen(QColor("#FFFFFF"), 2.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            # 对勾路径: (4,9) → (8,13) → (14,5)
            painter.drawLine(QLineF(4, box_y + 9, 8, box_y + 13))
            painter.drawLine(QLineF(8, box_y + 13, 14, box_y + 5))
        else:
            # 透明背景 + 灰色边框
            painter.setBrush(Qt.BrushStyle.NoBrush)
            pen = QPen(QColor(self._border), 2)
            painter.setPen(pen)
            painter.drawRoundedRect(box_rect, 4, 4)

        # 绘制文字
        text_rect = QRect(box_size + 8, 0, self.width() - box_size - 8, self.height())
        painter.setPen(QColor(self._text_color))
        font = QFont()
        font.setPixelSize(13)
        painter.setFont(font)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())

        painter.end()


class DashboardPage(QWidget):
    """仪表盘页面 — 服务控制 + 额度管理合并页面

    顶部：积分余额、API 代理服务控制、客户端配置
    底部：嵌入 AccountsPage 的消耗明细 + 缓存命中率图表
    """

    _REF_WIDTH = 536    # 参考宽度（100%缩放时的可用内容宽度，约 600-64 边距）
    _REF_HEIGHT = 560   # 参考高度（100%缩放时的可用内容高度）
    _MIN_SCALE = 0.5    # 最小缩放比例

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("content_area")
        self._colors = _current_theme_colors()
        self._scale = 1.0
        self._all_cards = []
        self._proxy_page = None  # ApiProxyPage 引用，由 MainWindow 注入
        self._credits_loaded = False  # 是否已从后端加载过积分
        self._accounts_page = None  # 嵌入的 AccountsPage 引用，由 MainWindow 注入
        self._setup_ui()
        self._load_cached_credits()  # 启动时从本地缓存加载积分

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 标题
        title = QLabel(t("nav.dashboard"))
        title.setObjectName("page_title")
        layout.addWidget(title)

        subtitle = QLabel("API 代理 · 额度管理 · 消耗明细")
        subtitle.setObjectName("page_subtitle")
        layout.addWidget(subtitle)

        # 内容区域（不显示滚动条，内容自动缩放到窗口大小）
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 内容区域
        self._content = QWidget()
        self._content.setObjectName("dashboard_scroll_content")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(32, 0, 32, 32)
        content_layout.setSpacing(20)

        # === 积分卡片网格 (2x2) ===
        quota_grid = QGridLayout()
        quota_grid.setSpacing(10)

        def _make_quota_card(icon: str, title: str, value_label: QLabel, color_key: str):
            """构建单个积分卡片"""
            card = QFrame()
            card.setObjectName("proxy_control_card")
            lay = QVBoxLayout(card)
            lay.setContentsMargins(14, 10, 14, 10)
            lay.setSpacing(4)

            head = QHBoxLayout()
            head.setSpacing(6)
            ic = QLabel(icon)
            ic.setStyleSheet("font-size: 16px;")
            head.addWidget(ic)
            t = QLabel(title)
            t.setStyleSheet(
                f"font-size: 12px; color: {self._colors['text_tertiary']};"
            )
            head.addWidget(t)
            head.addStretch()
            lay.addLayout(head)

            value_label.setStyleSheet(
                f"font-size: 20px; font-weight: 700; color: {self._colors[color_key]};"
            )
            lay.addWidget(value_label)
            return card

        self._quota_value_label = QLabel("--")        # 积分包余额
        self._quota_recharged_label = QLabel("--")    # 累计充值
        self._quota_used_label = QLabel("--")         # 已用
        self._quota_today_label = QLabel("--")        # 今日已用

        c_balance = _make_quota_card("💎", "积分包余额", self._quota_value_label, "text_primary")
        c_recharged = _make_quota_card("💰", "累计充值", self._quota_recharged_label, "accent")
        c_used = _make_quota_card("📉", "已用", self._quota_used_label, "warning")
        c_today = _make_quota_card("📅", "今日已用", self._quota_today_label, "error")

        quota_grid.addWidget(c_balance, 0, 0)
        quota_grid.addWidget(c_recharged, 0, 1)
        quota_grid.addWidget(c_used, 1, 0)
        quota_grid.addWidget(c_today, 1, 1)
        content_layout.addLayout(quota_grid)

        # 积分进度条已删除，保留隐藏占位引用避免外部代码报错
        self._quota_progress = QProgressBar()
        self._quota_progress.setVisible(False)

        # 隐藏徽章和旧套餐描述（保留引用避免报错）
        self._quota_badge_label = QLabel("--")
        self._quota_badge_label.setVisible(False)
        self._quota_packages_label = QLabel("")
        self._quota_packages_label.setVisible(False)

        # 按钮行：激活卡密 + 刷新积分
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # 激活卡密按钮
        self._btn_activate = QPushButton(f"🔑 {t('accounts.add_account')}")
        self._btn_activate.setObjectName("primary_btn")
        self._btn_activate.setCursor(Qt.PointingHandCursor)
        self._btn_activate.setMinimumHeight(36)
        self._btn_activate.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._colors['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_hover']};
            }}
        """)
        self._btn_activate.clicked.connect(self._activate_card)
        btn_row.addWidget(self._btn_activate)

        # 刷新积分按钮
        self._btn_refresh_credits = QPushButton("🔄 刷新积分")
        self._btn_refresh_credits.setCursor(Qt.PointingHandCursor)
        self._btn_refresh_credits.setMinimumHeight(36)
        self._btn_refresh_credits.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {self._colors['accent']};
                border: 1px solid {self._colors['accent']};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_light']};
            }}
        """)
        self._btn_refresh_credits.clicked.connect(self._refresh_credits)
        btn_row.addWidget(self._btn_refresh_credits)

        btn_row.addStretch()
        content_layout.addLayout(btn_row)

        # === 客户端配置区（写入 WorkBuddy / CodeBuddy 的 models.json）===
        self._proxy_control_card = QFrame()
        self._proxy_control_card.setObjectName("proxy_control_card")
        proxy_ctrl_layout = QVBoxLayout(self._proxy_control_card)
        proxy_ctrl_layout.setSpacing(10)

        import getpass
        _username = getpass.getuser()

        # === 模型前缀输入框 ===
        prefix_row = QHBoxLayout()
        prefix_label = QLabel("模型前缀:")
        prefix_label.setStyleSheet("font-size: 12px; font-weight: 600;")
        prefix_row.addWidget(prefix_label)
        self._model_prefix_input = QLineEdit()
        self._model_prefix_input.setPlaceholderText("不知道这是啥 不要动")
        self._model_prefix_input.setText(load_setting("model_prefix", ""))
        self._model_prefix_input.setFixedWidth(160)
        self._model_prefix_input.setStyleSheet(f"""
            QLineEdit {{
                border: 2px solid #E53E3E;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
                color: {self._colors['text_primary']};
                background-color: {self._colors['bg_secondary']};
            }}
            QLineEdit::placeholder {{
                color: #E53E3E;
            }}
        """)
        prefix_row.addWidget(self._model_prefix_input)
        prefix_row.addStretch()
        proxy_ctrl_layout.addLayout(prefix_row)

        # === 客户端配置按钮：配置 WorkBuddy / 配置 CodeBuddy / 还原配置 / 打开备份目录 ===
        _btn_style = f"""
            QPushButton {{
                background-color: {self._colors['accent']};
                color: #FFFFFF;
                border: none;
                border-radius: 8px;
                padding: 8px 18px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background-color: {self._colors['accent_hover']};
            }}
        """
        client_btn_row = QHBoxLayout()
        client_btn_row.setSpacing(10)

        self._btn_config_workbuddy = QPushButton("配置 WorkBuddy")
        self._btn_config_workbuddy.setCursor(Qt.PointingHandCursor)
        self._btn_config_workbuddy.setMinimumHeight(40)
        self._btn_config_workbuddy.setStyleSheet(_btn_style)
        self._btn_config_workbuddy.clicked.connect(lambda: self._apply_config("workbuddy"))
        client_btn_row.addWidget(self._btn_config_workbuddy)

        self._btn_config_codebuddy = QPushButton("配置 CodeBuddy")
        self._btn_config_codebuddy.setCursor(Qt.PointingHandCursor)
        self._btn_config_codebuddy.setMinimumHeight(40)
        self._btn_config_codebuddy.setStyleSheet(_btn_style)
        self._btn_config_codebuddy.clicked.connect(lambda: self._apply_config("codebuddy"))
        client_btn_row.addWidget(self._btn_config_codebuddy)

        self._btn_restore_config = QPushButton("还原配置")
        self._btn_restore_config.setCursor(Qt.PointingHandCursor)
        self._btn_restore_config.setMinimumHeight(40)
        self._btn_restore_config.setStyleSheet(_btn_style)
        self._btn_restore_config.clicked.connect(self._restore_config)
        client_btn_row.addWidget(self._btn_restore_config)

        self._btn_open_backup = QPushButton("打开备份目录")
        self._btn_open_backup.setCursor(Qt.PointingHandCursor)
        self._btn_open_backup.setMinimumHeight(40)
        self._btn_open_backup.setStyleSheet(_btn_style)
        self._btn_open_backup.clicked.connect(self._open_backup_dir)
        client_btn_row.addWidget(self._btn_open_backup)

        client_btn_row.addStretch()
        proxy_ctrl_layout.addLayout(client_btn_row)

        # 客户端路径提示
        path_hint = QLabel(
            f"WorkBuddy: C:\\Users\\{_username}\\.workbuddy\\models.json    "
            f"CodeBuddy: C:\\Users\\{_username}\\.codebuddy\\models.json"
        )
        path_hint.setStyleSheet(f"font-size: 11px; color: {self._colors['text_tertiary']};")
        proxy_ctrl_layout.addWidget(path_hint)

        # 自动备份复选框已删除 — 默认每次配置都自动备份
        self._chk_auto_backup = CheckableBox(
            "auto_backup", self._colors['accent'], self._colors['border'], self._colors['text_primary']
        )
        self._chk_auto_backup.setChecked(True)
        self._chk_auto_backup.setVisible(False)

        content_layout.addWidget(self._proxy_control_card)

        # === 额度管理（嵌入 AccountsPage 内容：消耗明细 + 缓存命中率图表）===
        from .accounts import AccountsPage
        self._accounts_page = AccountsPage(self, embedded=True)
        content_layout.addWidget(self._accounts_page)

        content_layout.addStretch()

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        # 显式设置背景色（必须在 setWidget 之后，QScrollArea viewport 默认用系统 palette 不跟主题）
        self._apply_scroll_background()

        # 收集所有静态卡片用于缩放（使用情况图表已移至额度管理页面）
        self._all_cards = []

    # === 响应式缩放 ===

    def resizeEvent(self, event):
        """窗口大小变化时重新计算缩放比例"""
        super().resizeEvent(event)
        self._apply_responsive_scale()

    def _apply_responsive_scale(self):
        """根据当前可用宽度和高度计算缩放比例并应用到所有UI元素

        取宽度和高度方向缩放比例的较小值，确保内容不超出可视区域、不出现滚动条。
        """
        # 安全检查：UI 未完全初始化时跳过（resizeEvent 可能在 _setup_ui 期间被触发）
        if not getattr(self, '_all_cards', None):
            return
        w = self.width() if self.width() > 0 else self._REF_WIDTH
        h = self.height() if self.height() > 0 else self._REF_HEIGHT
        available_w = w - 64  # 减去内容区域左右边距 (32*2)
        available_h = h - 20   # 减去顶部间距
        scale_w = available_w / self._REF_WIDTH
        scale_h = available_h / self._REF_HEIGHT
        self._scale = max(self._MIN_SCALE, min(1.0, scale_w, scale_h))
        s = self._scale

        # 缩放所有静态卡片
        for card in self._all_cards:
            card.apply_scale(s)

    # === 主题相关 ===

    def _apply_scroll_background(self):
        """设置 QScrollArea 及其 viewport、内容 widget 的背景色跟随主题

        三管齐下确保深色模式下不出现灰白背景：
        1. QScrollArea 本身 — scoped QSS
        2. viewport — QPalette + autoFillBackground（最可靠）+ QSS 兜底
        3. 内容 widget — scoped QSS（用 objectName 避免级联到子控件）+ QPalette
        """
        bg = self._colors['bg_primary']
        bg_color = QColor(bg)

        # 1. QScrollArea 本身
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background-color: {bg}; border: none; }}"
        )

        # 2. viewport — QAbstractScrollArea 的 viewport 是内部特殊 widget，
        #    QSS 不可靠，必须用 QPalette + autoFillBackground 才能稳定生效
        viewport = self._scroll.viewport()
        viewport.setAutoFillBackground(True)
        pal = viewport.palette()
        pal.setColor(QPalette.ColorRole.Window, bg_color)
        viewport.setPalette(pal)
        # QSS 作为额外兜底
        viewport.setStyleSheet(f"background-color: {bg};")

        # 3. 内容 widget — 用 objectName 限定 QSS 范围，避免级联到子控件
        if hasattr(self, '_content'):
            self._content.setAutoFillBackground(True)
            pal2 = self._content.palette()
            pal2.setColor(QPalette.ColorRole.Window, bg_color)
            self._content.setPalette(pal2)
            self._content.setStyleSheet(
                f"#dashboard_scroll_content {{ background-color: {bg}; }}"
            )

    def _apply_cache_frame_style(self):
        """缓存命中率图表区域样式（已移至额度管理页面，保留空方法避免外部调用报错）"""
        pass

    def _range_btn_style_active(self) -> str:
        """选中状态按钮样式（已移至额度管理页面）"""
        c = self._colors
        s = self._scale
        pad_v = int(6 * s)
        pad_h = int(16 * s)
        font_size = int(13 * s)
        return (
            f"QPushButton {{ background-color: {c['accent']}; color: #FFFFFF; "
            f"border: none; padding: {pad_v}px {pad_h}px; border-radius: 6px; font-size: {font_size}px; }}"
        )

    def _range_btn_style_normal(self) -> str:
        """未选中状态按钮样式（已移至额度管理页面）"""
        c = self._colors
        s = self._scale
        pad_v = int(6 * s)
        pad_h = int(16 * s)
        font_size = int(13 * s)
        return (
            f"QPushButton {{ background-color: {c['bg_tertiary']}; color: {c['text_secondary']}; "
            f"border: none; padding: {pad_v}px {pad_h}px; border-radius: 6px; font-size: {font_size}px; }}"
            f"QPushButton:hover {{ background-color: {c['bg_hover']}; }}"
        )

    def apply_theme(self):
        """主题切换时刷新所有颜色"""
        self._colors = _current_theme_colors()

        # QScrollArea 背景跟随主题（viewport 默认灰白不跟主题）
        self._apply_scroll_background()

        # 统计卡片
        for card in self._all_cards:
            card.apply_theme(self._colors)

        # 重新应用响应式缩放（会刷新所有带缩放的样式）
        self._apply_responsive_scale()

        # 嵌入的 AccountsPage 也刷新主题
        if self._accounts_page:
            try:
                self._accounts_page._colors = self._colors
                if hasattr(self._accounts_page, '_apply_cache_frame_style'):
                    self._accounts_page._apply_cache_frame_style()
            except Exception:
                pass

    # === 数字格式化（保留静态方法供其他页面调用） ===

    @staticmethod
    def _format_token_count(value: int) -> str:
        """将 Token/数字按大小格式化为中文单位，保留 2 位小数"""
        v = float(value)
        if v < 10_000:
            return f"{int(v):,}"
        if v < 1_000_000:
            return f"{v / 10_000:.2f}万"
        if v < 100_000_000:
            return f"{v / 1_000_000:.2f}百万"
        return f"{v / 100_000_000:.2f}亿"

    # === 图例渲染（已移至额度管理页面，保留空方法避免外部调用报错） ===

    def _render_legend(self, key: str):
        pass

    def _update_legend(self, key: str, value: str):
        pass

    def _refresh_legend_colors(self):
        pass

    # === 事件回调 ===

    def _on_range_changed(self, btn):
        """时间范围切换回调（已移至额度管理页面）"""
        pass

    def _refresh_usage(self):
        """刷新使用情况数据（已移至额度管理页面）"""
        pass

    def _refresh_data(self):
        """刷新仪表盘数据"""
        self._refresh_credits()

    def _load_cached_credits(self):
        """从本地缓存加载积分余额（不请求后端）"""
        try:
            db = ProxyDatabase.get_instance()
            cached = db.get_cached_credits()
            if cached:
                self._render_credits(cached)
            else:
                self._quota_value_label.setText("--")
                self._quota_recharged_label.setText("--")
                self._quota_used_label.setText("--")
                self._quota_today_label.setText("--")
                self._quota_badge_label.setText("--")
                self._quota_progress.setValue(0)
        except Exception:
            pass

    def _render_credits(self, data: dict):
        """渲染积分余额到 UI（4 个卡片）"""
        if not data or "credits" not in data:
            return
        credits = float(data.get("credits", 0))
        total_recharged = float(data.get("totalRecharged", 0))
        total_used = float(data.get("totalUsed", 0))
        today_used = float(data.get("todayUsed", 0))

        self._quota_value_label.setText(f"{credits:.2f}")
        self._quota_recharged_label.setText(f"{total_recharged:.0f}")
        self._quota_used_label.setText(f"{total_used:.0f}")
        self._quota_today_label.setText(f"{today_used:.0f}")

        # 兼容旧字段（隐藏占位）
        self._quota_packages_label.setText(
            f"累计充值 {total_recharged:.0f} · 已用 {total_used:.0f} · 今日 {today_used:.0f}"
        )

        if credits <= 0:
            self._quota_badge_label.setText("已耗尽")
        else:
            self._quota_badge_label.setText(f"剩余 {credits:.0f}")

        if total_recharged > 0:
            percent = int(min(100, max(0, (credits / total_recharged) * 100)))
            self._quota_progress.setValue(percent)
        else:
            self._quota_progress.setValue(0)

    def _refresh_credits(self):
        """从后端查询积分余额并更新本地缓存"""
        # 防止重复创建线程
        if hasattr(self, '_credits_thread') and self._credits_thread and self._credits_thread.isRunning():
            return

        self._btn_refresh_credits.setEnabled(False)
        self._quota_value_label.setText("⏳")
        self._quota_recharged_label.setText("--")
        self._quota_used_label.setText("--")
        self._quota_today_label.setText("--")
        self._quota_badge_label.setText("--")
        self._quota_progress.setValue(0)

        from PySide6.QtCore import QThread, Signal as QSignal

        class CreditsThread(QThread):
            done = QSignal(object)

            def run(self):
                from ...utils.server_api import get_credits
                result = get_credits()
                self.done.emit(result)

        self._credits_thread = CreditsThread()
        self._credits_thread.done.connect(self._on_credits_done)
        self._credits_thread.finished.connect(lambda: setattr(self, '_credits_thread', None))
        self._credits_thread.start()

    def _on_credits_done(self, result: dict):
        """积分查询完成"""
        self._btn_refresh_credits.setEnabled(True)
        self._credits_loaded = True

        if result and "credits" in result:
            # 保存到本地缓存
            try:
                db = ProxyDatabase.get_instance()
                db.save_cached_credits(result)
            except Exception:
                pass
            self._render_credits(result)
        else:
            err = result.get("error", "无响应") if result else "无响应"
            self._quota_value_label.setText("--")
            self._quota_recharged_label.setText("--")
            self._quota_used_label.setText("--")
            self._quota_today_label.setText("--")
            self._quota_packages_label.setText(f"查询失败: {err[:40]}")
            self._quota_badge_label.setText("错误")
            self._quota_progress.setValue(0)

    def _activate_card(self):
        """打开激活卡密对话框"""
        from .accounts import AddAccountDialog
        dialog = AddAccountDialog(self)
        def _on_account_added(_):
            self._refresh_credits()
        dialog.account_added.connect(_on_account_added)
        dialog.exec()

    def set_proxy_page(self, proxy_page):
        """注入 ApiProxyPage 引用（保留接口兼容，不再用于服务控制）"""
        self._proxy_page = proxy_page

    def _open_backup_dir(self):
        """打开备份目录"""
        import os
        from pathlib import Path
        backup_dir = Path.home() / ".buddytoolnew" / "config_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(str(backup_dir)) if hasattr(os, 'startfile') else None

    def _save_client_config(self):
        """保存客户端配置选项"""
        model_prefix = self._model_prefix_input.text().strip()
        save_setting("model_prefix", model_prefix)
        # 同步写入 ProxyDatabase，代理服务请求上游时用这个去掉前缀
        try:
            db = ProxyDatabase.get_instance()
            db.update_settings({"model_prefix": model_prefix})
        except Exception:
            pass

    def _build_config_json(self) -> str:
        """根据当前端口、子 API Key 和服务端模型列表生成配置 JSON

        取消本地代理：直接使用上游 API 地址 + 上游 Key 池中第一个可用 Key 作为 apiKey，
        客户端（WorkBuddy / CodeBuddy）直接请求上游，不再经过本工具的代理服务。
        """
        import json
        import secrets as _sec
        from datetime import datetime
        from ...modules.proxy_server import SUPPORTED_MODELS, MODEL_CONTEXT_LENGTHS, MODEL_MAX_OUTPUT_TOKENS, ProxyDatabase

        # 从上游 Key 池中获取第一个可用 Key 作为 apiKey
        api_key = ""
        try:
            db = ProxyDatabase.get_instance()
            upstream_keys = db.get_upstream_keys()
            for k in upstream_keys:
                if k.get("status", "active") == "active" and k.get("api_key"):
                    api_key = k["api_key"]
                    break
        except Exception:
            pass

        if not api_key:
            # Key 池为空时退化为机器码占位（提示未配置）
            from ...utils.machine import get_machine_code
            api_key = get_machine_code() or "未配置上游Key"
            logger.warning("[_build_config_json] 上游 Key 池为空，apiKey 使用机器码占位")

        # 从动态服务端地址列表中随机取一个作为上游 URL
        from ...utils.server_api import _fetch_server_list
        import random as _random
        servers = _fetch_server_list()
        if servers:
            upstream_base = _random.choice(servers)
        else:
            # 列表为空时回退到默认地址
            from ...modules.proxy_server import DEFAULT_UPSTREAM_URL
            upstream_base = DEFAULT_UPSTREAM_URL
        # 拼接 chat completions 路径
        upstream_base = upstream_base.rstrip("/")
        url = f"{upstream_base}/v1/chat/completions"

        # 固定模型列表
        _FIXED_MODELS = [
            {"id": "auto",              "name": "Auto",            "maxInputTokens": 128000,  "maxOutputTokens": 8192},
            {"id": "Hy3",               "name": "Hy3",             "maxInputTokens": 192000,  "maxOutputTokens": 8192},
            {"id": "GLM-5.2",           "name": "GLM-5.2",         "maxInputTokens": 1000000, "maxOutputTokens": 8192},
            {"id": "GLM-5.1",           "name": "GLM-5.1",         "maxInputTokens": 200000,  "maxOutputTokens": 8192},
            {"id": "GLM-5V-Turbo",      "name": "GLM-5V-Turbo",   "maxInputTokens": 200000,  "maxOutputTokens": 8192},
            {"id": "MiniMax-M3",        "name": "MiniMax-M3",     "maxInputTokens": 512000,  "maxOutputTokens": 8192},
            {"id": "Kimi-K2.7-Code",    "name": "Kimi-K2.7-Code", "maxInputTokens": 256000,  "maxOutputTokens": 8192},
            {"id": "Kimi-K2.6",         "name": "Kimi-K2.6",      "maxInputTokens": 256000,  "maxOutputTokens": 8192},
            {"id": "DeepSeek-V4-Flash", "name": "DeepSeek-V4-Flash", "maxInputTokens": 1000000, "maxOutputTokens": 8192},
            {"id": "DeepSeek-V4-Pro",   "name": "DeepSeek-V4-Pro","maxInputTokens": 1000000, "maxOutputTokens": 8192},
        ]

        models = []
        for m in _FIXED_MODELS:
            models.append({
                "id": m["id"],
                "name": m["name"],
                "vendor": "Buddy",
                "apiKey": api_key,
                "url": url,
                "maxInputTokens": m["maxInputTokens"],
                "maxOutputTokens": m["maxOutputTokens"],
                "supportsToolCall": True,
                "supportsImages": True,
                "supportsReasoning": True,
            })

        return json.dumps({"models": models}, ensure_ascii=False, indent=2)

    def _apply_config(self, target_client: str = "workbuddy"):
        """配置单个客户端 — 生成 JSON 并写入 models.json

        Args:
            target_client: "workbuddy" 或 "codebuddy"
        """
        self._save_client_config()

        from pathlib import Path
        import os
        from datetime import datetime
        from shutil import copy2

        config_json = self._build_config_json()

        if target_client == "workbuddy":
            name = "WorkBuddy"
            target_dir = Path.home() / ".workbuddy"
        else:
            name = "CodeBuddy"
            target_dir = Path.home() / ".codebuddy"

        # 确认弹窗
        reply = QMessageBox.question(
            self, "确认配置",
            f"是否立即配置并重启 {name}？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 默认总是备份原文件
        backup_root = Path.home() / ".buddytoolnew" / "config_backups"
        backup_root.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        src = target_dir / "models.json"
        if src.exists():
            dst = backup_root / f"{name.lower()}_{ts}.json"
            try:
                copy2(str(src), str(dst))
            except Exception as e:
                logger.warning(f"备份 {name} 配置失败: {e}")

        # 写入配置
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / "models.json"
            target_path.write_text(config_json, encoding="utf-8")
        except Exception as e:
            logger.error(f"配置 {name} 失败: {e}")
            QMessageBox.critical(self, "配置失败", f"写入 {name} 配置失败：\n{e}")
            return

        # 配置已写入，提示用户重启客户端生效
        QMessageBox.information(self, "提示", f"{name} 配置已更新，请重启客户端生效")

    def _restore_config(self):
        """还原配置 — 从备份目录恢复最近一次备份到对应客户端

        弹窗让用户选择 WorkBuddy 或 CodeBuddy，然后从
        ~/.buddytoolnew/config_backups/ 中找到最新的对应备份恢复。
        """
        from pathlib import Path
        from shutil import copy2

        backup_root = Path.home() / ".buddytoolnew" / "config_backups"

        # 让用户选择客户端
        items = ["WorkBuddy", "CodeBuddy"]
        from PySide6.QtWidgets import QInputDialog
        choice, ok = QInputDialog.getItem(
            self, "还原配置", "选择要还原的客户端：", items, 0, False
        )
        if not ok:
            return

        target_dir_name = ".workbuddy" if choice == "WorkBuddy" else ".codebuddy"
        target_dir = Path.home() / target_dir_name
        target_path = target_dir / "models.json"

        if not backup_root.exists():
            QMessageBox.warning(self, "无备份", "备份目录不存在，无法还原。\n\n路径：" + str(backup_root))
            return

        # 查找最新的备份文件
        prefix = choice.lower() + "_"
        backups = sorted(
            [f for f in backup_root.iterdir() if f.name.startswith(prefix) and f.suffix == ".json"],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        if not backups:
            QMessageBox.warning(self, "无备份", f"未找到 {choice} 的备份文件。")
            return

        latest = backups[0]
        reply = QMessageBox.question(
            self, "确认还原",
            f"将还原 {choice} 的最近一次备份：\n\n{latest.name}\n\n到：\n{target_path}\n\n会覆盖当前配置，是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            copy2(str(latest), str(target_path))
            QMessageBox.information(self, "还原成功", f"{choice} 配置已从备份还原：\n\n{latest.name}")
        except Exception as e:
            QMessageBox.critical(self, "还原失败", f"还原 {choice} 配置失败：\n{e}")

    def showEvent(self, event):
        """页面显示时刷新数据并应用缩放"""
        super().showEvent(event)
        # 安全网：确保 QScrollArea viewport 背景跟随主题（Qt 内部可能重置 viewport palette）
        self._apply_scroll_background()
        self._apply_responsive_scale()
        # 刷新嵌入的额度管理页面（消耗明细 + 缓存命中率图表）
        if self._accounts_page:
            try:
                self._accounts_page._refresh_table()
            except Exception:
                pass
        # 积分：首次打开从后端查询，后续切页面用本地缓存
        if not self._credits_loaded:
            self._refresh_credits()
        else:
            self._load_cached_credits()
