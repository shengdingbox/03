"""主窗口 - BuddyToolNew 桌面应用"""

import logging
import os
import sys
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSystemTrayIcon,
    QMenu, QMessageBox, QApplication,
)
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import Qt, QSize, Slot, QTimer

from .ui.pages import (
    DashboardPage, AccountsPage, ApiProxyPage,
)
from .ui import get_stylesheet

from .utils.store import init_db, load_setting
from .modules.updater import UpdateChecker, get_current_version

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self._update_version_suffix()
        self.setWindowTitle("⚡ BuddyToolNew")
        self.setMinimumSize(QSize(520, 520))
        self.resize(750, 600)

        # 初始化数据库
        init_db()

        # 加载设置
        self._current_theme = load_setting("theme", "system")

        # 构建UI
        self._setup_ui()
        self._setup_tray()
        self.apply_theme(self._current_theme)

        # 自动更新
        self._setup_updater()

    def _update_version_suffix(self):
        """更新窗口标题中的版本号"""
        ver = get_current_version()
        self.setWindowTitle(f"⚡ BuddyToolNew v{ver}")

    def _setup_updater(self):
        """初始化自动更新检查器"""
        self._updater = UpdateChecker(self)
        self._updater.update_available.connect(self._on_update_available)
        self._updater.no_update.connect(self._on_no_update)

        # 启动定期检查：首次5秒后检查，之后每1小时检查
        self._updater.start_periodic_check(3600_000)

    def _on_update_available(self, version: str, changelog: str, download_url: str, sha256: str):
        """发现新版本 — 弹窗提示"""
        current = get_current_version()

        msg = QMessageBox(self)
        msg.setWindowTitle("发现新版本")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setText(f"发现新版本 v{version}！（当前 v{current}）")
        msg.setInformativeText(
            f"更新内容：\n{changelog}\n\n"
            f"是否立即更新？"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Yes)

        # 以后不再提醒选项
        skip_btn = msg.addButton("跳过此版本", QMessageBox.ButtonRole.RejectRole)

        result = msg.exec()

        if msg.clickedButton() == skip_btn:
            # 记录跳过的版本
            from .utils.store import save_setting
            save_setting("skip_version", version)
            return

        if result == QMessageBox.StandardButton.Yes:
            # 打开浏览器跳转到下载地址
            if download_url:
                import webbrowser
                webbrowser.open(download_url)
            else:
                QMessageBox.warning(self, "提示", "未获取到下载地址，请手动前往官网下载。")

    def _setup_ui(self):
        """构建主界面 — 单页面布局（合并仪表盘 + 额度管理，无侧边栏）"""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 单页面：DashboardPage（已内嵌 AccountsPage 的额度管理内容）
        self._dashboard_page = DashboardPage()
        layout.addWidget(self._dashboard_page, 1)

        # ApiProxyPage 不作为独立页面显示，但保留实例供仪表盘调用服务逻辑
        self._proxy_page = ApiProxyPage()

        # 仪表盘需要引用代理页面来控制服务
        self._dashboard_page.set_proxy_page(self._proxy_page)

        # 代理页面需要引用仪表盘来同步控件值
        self._proxy_page.set_dashboard_page(self._dashboard_page)

        # 跨页面信号：积分更新互相同步
        # 嵌入在 Dashboard 中的 AccountsPage 积分更新时刷新代理池
        accounts_page = self._dashboard_page._accounts_page
        if accounts_page:
            accounts_page.quota_updated.connect(self._on_accounts_quota_updated)
        self._proxy_page.quota_updated.connect(self._on_proxy_quota_updated)

    def _setup_tray(self):
        """设置系统托盘"""
        self._tray = QSystemTrayIcon(self)
        self._tray.setToolTip("BuddyToolNew")

        # 加载应用图标（优先 .ico 文件，降级为程序化生成）
        app_icon = self._load_app_icon()
        self._tray.setIcon(app_icon)
        self.setWindowIcon(app_icon)

        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示主窗口")
        show_action.triggered.connect(self._show_window)

        # 手动检查更新
        check_update_action = tray_menu.addAction("🔄 检查更新")
        check_update_action.triggered.connect(self._manual_check_update)

        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self._quit_app)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)

        # 如果关闭行为设为最小化到托盘，则初始化时就显示托盘图标
        close_behavior = load_setting("close_behavior", "minimize")
        if close_behavior == "minimize":
            self._tray.show()

    def _manual_check_update(self):
        """手动检查更新"""
        if not hasattr(self, '_updater') or self._updater is None:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.information(self, "检查更新", "自动更新功能已关闭")
            return
        self._updater._manual_check = True
        self._updater.check_update()

    def _load_app_icon(self) -> QIcon:
        """加载应用图标 — macOS 用程序化生成高清图标，其他平台优先 .ico"""
        # macOS 上 .ico 显示模糊，改用程序化生成高清图标
        if sys.platform == "darwin":
            icon = self._generate_high_res_icon()
            self._set_dock_icon(icon)
            return icon

        # Windows / Linux: 优先加载 .ico
        icon_paths = []
        if getattr(sys, 'frozen', False):
            # PyInstaller / Nuitka 打包模式
            base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
            icon_paths.append(os.path.join(base, 'assets', 'icons', 'app.ico'))
        # 开发模式
        src_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(src_dir)
        icon_paths.append(os.path.join(project_root, 'assets', 'icons', 'app.ico'))

        for icon_path in icon_paths:
            if os.path.isfile(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    logger.info(f"加载应用图标: {icon_path}")
                    return icon

        # 降级：程序化生成闪电图标
        return self._generate_high_res_icon()

    def _generate_high_res_icon(self) -> QIcon:
        """程序化生成高分辨率闪电图标（256x256）"""
        logger.info("使用程序化生成图标")
        from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QPen, QLinearGradient, QBrush
        from PySide6.QtCore import QRect, QLineF

        size = 256
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        # 圆角矩形背景渐变
        gradient = QLinearGradient(0, 0, 0, size)
        gradient.setColorAt(0, QColor("#7C3AED"))
        gradient.setColorAt(0.5, QColor("#6C5CE7"))
        gradient.setColorAt(1, QColor("#5B4FE9"))
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(8, 8, size - 16, size - 16, 56, 56)

        # 内圆角边框
        painter.setBrush(QColor(255, 255, 255, 15))
        painter.drawRoundedRect(14, 14, size - 28, size - 28, 50, 50)

        # 闪电图形
        painter.setBrush(QColor("#FFFFFF"))
        painter.setPen(Qt.PenStyle.NoPen)
        flash = [
            (size * 0.58, size * 0.18),
            (size * 0.30, size * 0.55),
            (size * 0.46, size * 0.55),
            (size * 0.38, size * 0.82),
            (size * 0.70, size * 0.42),
            (size * 0.52, size * 0.42),
        ]
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        poly = QPolygonF([QPointF(x, y) for x, y in flash])
        painter.drawPolygon(poly)

        # 闪电阴影效果
        painter.setBrush(QColor(255, 255, 255, 40))
        shadow = [
            (size * 0.58, size * 0.18),
            (size * 0.55, size * 0.22),
            (size * 0.50, size * 0.45),
            (size * 0.52, size * 0.42),
        ]
        shadow_poly = QPolygonF([QPointF(x, y) for x, y in shadow])
        painter.drawPolygon(shadow_poly)

        painter.end()
        return QIcon(pixmap)

    def _set_dock_icon(self, icon: QIcon):
        """macOS: 设置 Dock 图标"""
        if sys.platform != "darwin":
            return
        try:
            from AppKit import NSImage, NSApp
            pixmap = icon.pixmap(256, 256)
            if pixmap.isNull():
                return
            # QPixmap → NSImage
            image = pixmap.toImage()
            buf = image.bits().asstring(image.sizeInBytes())
            ns_image = NSImage.alloc().initWithData_(
                bytes(buf)
            )
            ns_image.setSize_((256, 256))
            NSApp.setApplicationIconImage_(ns_image)
        except Exception as e:
            logger.debug(f"设置 Dock 图标失败: {e}")

    def _on_accounts_quota_updated(self):
        """账号页积分更新 → 刷新代理池子 Key 列表"""
        proxy_page = self._proxy_page
        if proxy_page:
            try:
                proxy_page._refresh_sub_keys()
            except Exception:
                pass

    def _on_proxy_quota_updated(self):
        """代理池页积分更新 → 刷新额度管理（嵌入在 Dashboard 中）"""
        accounts_page = self._dashboard_page._accounts_page if self._dashboard_page else None
        if accounts_page:
            try:
                accounts_page._refresh_table()
            except Exception:
                pass

    @Slot(bool)
    def _on_no_update(self, is_manual: bool):
        """无更新"""
        if is_manual:
            # 手动检查才弹提示，自动检查不打扰
            QMessageBox.information(self, "检查更新", "✅ 当前已是最新版本！")

    def apply_theme(self, theme: str):
        """应用主题"""
        self._current_theme = theme
        stylesheet = get_stylesheet(theme)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(stylesheet)
        self.setStyleSheet(stylesheet)
        # 通知 Dashboard 页面刷新动态颜色（含内嵌的额度管理）
        if self._dashboard_page and hasattr(self._dashboard_page, "apply_theme"):
            try:
                self._dashboard_page.apply_theme()
            except Exception:
                pass

    def _show_window(self):
        """显示窗口"""
        self.showNormal()
        self.activateWindow()
        self.raise_()
        self.setFocus()

    def _on_tray_activated(self, reason):
        """托盘图标激活"""
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _quit_app(self):
        """退出应用 — 清理所有子进程和资源，确保进程真正退出"""
        # 1. 停止 API 代理服务器（刷盘 + 关闭 socket + 关闭连接池）
        if self._proxy_page:
            try:
                self._proxy_page._cleanup()
            except Exception:
                pass

        # 2. 注意：不关闭 WorkBuddy 进程！
        #    WorkBuddy 是独立应用，只有用户在登录流程中主动确认时才会关闭（oauth.py）
        #    关闭本软件不应影响用户正在使用的 WorkBuddy

        # 3. 关闭所有 QThread（签到、查询等后台任务）
        # Dashboard 内嵌的 AccountsPage 可能有后台 worker
        candidates = []
        if self._dashboard_page:
            candidates.append(self._dashboard_page)
            if self._dashboard_page._accounts_page:
                candidates.append(self._dashboard_page._accounts_page)
        if self._proxy_page:
            candidates.append(self._proxy_page)
        for page in candidates:
            try:
                if hasattr(page, '_worker') and page._worker:
                    page._worker.stop()
                if hasattr(page, '_status_worker') and page._status_worker:
                    page._status_worker.stop()
                if hasattr(page, '_batch_worker') and page._batch_worker:
                    page._batch_worker.stop()
            except Exception:
                pass

        # 5. 隐藏托盘图标
        try:
            self._tray.hide()
        except Exception:
            pass

        # 6. 先尝试优雅退出 Qt 事件循环
        try:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        except Exception:
            pass

        # 7. 兜底：如果 Qt 退出后线程还没结束，强制杀掉进程
        # 这是必要的，因为 HTTPServer 的 serve_forever() 线程可能阻塞
        # 即使调了 shutdown()，如果 socket 正在 accept() 等待，也可能卡住
        import threading
        # 给 1 秒让优雅退出生效
        for t in threading.enumerate():
            if t is not threading.main_thread() and t.is_alive():
                try:
                    t.join(timeout=1.0)
                except Exception:
                    pass
        # 如果还有非 daemon 线程活着，强制退出
        still_alive = [t for t in threading.enumerate() if t is not threading.main_thread() and t.is_alive()]
        if still_alive:
            logger.warning(f"还有 {len(still_alive)} 个线程未退出，强制终止进程")
            os._exit(0)

    def _kill_workbuddy_process(self):
        """已弃用 — 不再在软件关闭时杀 WorkBuddy
        
        WorkBuddy 是独立应用，只有用户在登录流程（oauth.py）中主动确认后才会关闭。
        保留此方法仅为向后兼容，实际不再执行任何操作。
        """
        logger.debug("_kill_workbuddy_process 被调用但已弃用，不再杀 WorkBuddy 进程")

    def closeEvent(self, event):
        """关闭事件 - 退出或最小化到托盘"""
        close_behavior = load_setting("close_behavior", "minimize")
        if close_behavior == "minimize":
            event.ignore()
            self.hide()
            self._tray.show()
            self._tray.showMessage(
                "BuddyToolNew",
                "已最小化到系统托盘，双击图标恢复",
            )
        else:
            event.accept()
            self._quit_app()
