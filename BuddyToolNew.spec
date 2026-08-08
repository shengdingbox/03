# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BuddyToolNew - 精简打包，仅包含必要的 PySide6 模块"""

import os
import PySide6

block_cipher = None

_pyside6_dir = os.path.dirname(PySide6.__file__)

# 需要排除的 Qt DLL（按文件名关键词匹配）
# 这些是项目不需要的重型模块 DLL
EXCLUDE_DLL_PATTERNS = [
    'WebEngine', 'WebChannel', 'WebSockets',
    'Quick3D', 'QuickControls2', 'QuickTemplates2', 'QuickTest',
    'QuickLayouts', 'QuickEffects', 'QuickParticles', 'QuickShapes',
    'QuickTimeline', 'QuickDialogs2', 'QuickWidgets', 'Quick',
    '3D', 'Charts', 'DataVisualization', 'Graphs',
    'Pdf', 'Location', 'Positioning', 'Sensors',
    'SerialPort', 'SerialBus', 'Bluetooth', 'Nfc',
    'RemoteObjects', 'Scxml', 'NetworkAuth', 'Help',
    'OpenGL', 'Test', 'UiTools', 'Concurrent', 'StateMachine',
    'HttpServer', 'DBus', 'Designer', 'AxContainer',
    'TextToSpeech', 'VirtualKeyboard', 'ExampleIcons',
    'PrintSupport', 'Sql', 'ShaderTools', 'Qml',
    'SpatialAudio',
    # FFmpeg 多媒体编解码库（QtMultimedia 依赖）
    'avcodec', 'avformat', 'avutil', 'swscale', 'swresample',
    # 软件渲染（不需要，系统有 GPU 驱动）
    'opengl32sw',
    # Qt 数据库驱动
    'qsql', 'qsqlite',
]

# 仅保留项目实际需要的 Qt DLL 白名单
KEEP_DLL_NAMES = [
    'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'Qt6Network.dll',
    # 插件
    'plugins\\platforms\\qwindows.dll',
    'plugins\\styles\\qwindowsvistastyle.dll',
    'plugins\\imageformats\\qico.dll',
    'plugins\\tls\\qschannelbackend.dll',
]

def _collect_pyside6_binaries():
    """手动收集 PySide6 二进制文件，仅保留必要的"""
    binaries = []
    # PySide6 的 .pyd 绑定文件 - 仅保留必要的
    keep_pyds = ['QtCore.pyd', 'QtGui.pyd', 'QtWidgets.pyd', 'QtNetwork.pyd']
    for pyd in keep_pyds:
        pyd_path = os.path.join(_pyside6_dir, pyd)
        if os.path.exists(pyd_path):
            binaries.append((pyd_path, 'PySide6'))
    # Qt DLL - 仅保留白名单中的
    for root, dirs, files in os.walk(_pyside6_dir):
        for f in files:
            if not f.endswith('.dll'):
                continue
            full = os.path.join(root, f)
            rel = os.path.relpath(full, _pyside6_dir)
            # 检查是否在白名单中
            if f in ('Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'Qt6Network.dll'):
                binaries.append((full, 'PySide6'))
            elif 'plugins' in rel:
                # 仅保留白名单插件
                rel_norm = rel.replace('/', '\\')
                for keep in KEEP_DLL_NAMES:
                    if rel_norm.endswith(keep) or rel_norm == keep:
                        binaries.append((full, os.path.join('PySide6', os.path.dirname(rel))))
                        break
    return binaries

# 项目只需要 QtCore, QtGui, QtWidgets, QtNetwork, QtSvg
# 排除所有其他 PySide6 模块
PYSIDE6_EXCLUDES = [
    # 3D
    'PySide6.Qt3DCore', 'PySide6.Qt3DRender', 'PySide6.Qt3DInput',
    'PySide6.Qt3DLogic', 'PySide6.Qt3DAnimation', 'PySide6.Qt3DExtras',
    # WebEngine
    'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebEngineQuick', 'PySide6.QtWebChannel',
    'PySide6.QtWebChannelQuick', 'PySide6.QtWebSockets',
    # Quick/QML
    'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQml',
    'PySide6.QtQuick3D', 'PySide6.QtQuick3DUtils', 'PySide6.QtQuick3DAsset',
    'PySide6.QtQuick3DParticles', 'PySide6.QtQuick3DAssetImport',
    'PySide6.QtQuickControls2', 'PySide6.QtQuickTemplates2',
    'PySide6.QtQuickTest', 'PySide6.QtQuickLayouts',
    'PySide6.QtQuickEffects', 'PySide6.QtQuickParticles',
    'PySide6.QtQuickShapes', 'PySide6.QtQuickTimeline',
    'PySide6.QtShaderTools', 'PySide6.QtQmlWorkerScript',
    # Multimedia
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
    'PySide6.QtSpatialAudio',
    # Charts/Graphs/DataViz
    'PySide6.QtCharts', 'PySide6.QtChartsQml',
    'PySide6.QtDataVisualization', 'PySide6.QtDataVisualizationQml',
    'PySide6.QtDataVisualization2D',
    'PySide6.QtGraphs', 'PySide6.QtGraphsWidgets',
    # PDF
    'PySide6.QtPdf', 'PySide6.QtPdfWidgets', 'PySide6.QtPdfQuick',
    # Location/Positioning/Sensors
    'PySide6.QtLocation', 'PySide6.QtPositioning', 'PySide6.QtSensors',
    # Serial/Bluetooth/NFC
    'PySide6.QtSerialPort', 'PySide6.QtSerialBus',
    'PySide6.QtBluetooth', 'PySide6.QtNfc',
    # Other unused
    'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
    'PySide6.QtNetworkAuth', 'PySide6.QtHelp',
    'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets',
    'PySide6.QtTest', 'PySide6.QtUiTools',
    'PySide6.QtConcurrent', 'PySide6.QtStateMachine',
    'PySide6.QtHttpServer', 'PySide6.QtDBus',
    'PySide6.QtDesigner', 'PySide6.QtAxContainer',
    'PySide6.QtTextToSpeech', 'PySide6.QtVirtualKeyboard',
    'PySide6.QtExampleIcons', 'PySide6.QtAsyncio',
    'PySide6.QtPrintSupport',  # 如需打印再加回
    'PySide6.QtSql',
    # QtSvg - 如果样式需要可加回
    'PySide6.QtSvg', 'PySide6.QtSvgWidgets',
]

# Python 标准库和第三方排除
PYTHON_EXCLUDES = [
    'tkinter', 'unittest', 'pydoc', 'doctest',
    'test', 'tests', 'pytest',
    'matplotlib', 'numpy', 'pandas', 'PIL', 'cv2',
    'torch', 'tensorflow', 'IPython', 'notebook',
    'jupyter', 'PySide6.QtUiTools',
    # 不需要的运行时包
    'setuptools', 'pip', 'wheel', 'pkg_resources',
    'lib2to3',
]

a = Analysis(
    ['app.py'],
    pathex=[os.path.dirname(os.path.abspath('app.py'))],
    hookspath=[os.path.join(os.path.dirname(os.path.abspath(SPEC)), 'hooks')],
    binaries=_collect_pyside6_binaries(),
    datas=[
        ('assets', 'assets'),
        ('src/VERSION', 'src'),
    ],
    hiddenimports=[
        'charset_normalizer',
        'urllib3',
        'certifi',
        'idna',
        'socks',
        'charset_normalizer.md',
        # src 包动态导入（app.py 用 importlib.import_module）
        'src',
        'src.main',
        'src.cli',
        'src.main_window',
        'src.__init__',
        'src.i18n',
        'src.i18n.translations',
        'src.models',
        'src.models.__init__',
        'src.modules',
        'src.modules.api_client',
        'src.modules.oauth',
        'src.modules.checkin',
        'src.modules.proxy_server',
        'src.modules.updater',
        'src.ui',
        'src.ui.components',
        'src.ui.components.sidebar',
        'src.ui.pages.dashboard',
        'src.ui.pages.accounts',
        'src.ui.pages.checkin',
        'src.ui.pages.api_proxy',
        'src.ui.pages.settings',
        'src.ui.pages.quota',
        'src.ui.styles',
        'src.ui.styles.theme',
        'src.utils',
        'src.utils.store',
        'src.utils.machine',
        'src.utils.usage_reporter',
        'src.utils.server_api',
        'src.utils.ssl_pinning',
    ],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PYSIDE6_EXCLUDES + PYTHON_EXCLUDES,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='BuddyToolNew',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[
        # 不压缩这些 DLL（压缩可能导致问题）
        'vcruntime140.dll', 'VCRUNTIME140_1.dll',
        'python3.dll', 'python311.dll',
        # PySide6/Qt DLL 压缩可能导致崩溃，排除
        'Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'Qt6Network.dll',
        'QtCore.pyd', 'QtGui.pyd', 'QtWidgets.pyd', 'QtNetwork.pyd',
    ],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codepage=0,
    icon='assets/icons/icon.ico' if os.path.exists('assets/icons/icon.ico') else None,
)
