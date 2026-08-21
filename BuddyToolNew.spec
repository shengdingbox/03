# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for BuddyToolNew - 纯 CLI 打包"""

import os

block_cipher = None

# Python 标准库和第三方排除
PYTHON_EXCLUDES = [
    'tkinter', 'pydoc', 'doctest',
    'test', 'tests', 'pytest',
    'matplotlib', 'numpy', 'pandas', 'PIL', 'cv2',
    'torch', 'tensorflow', 'IPython', 'notebook',
    'jupyter',
    # 不需要的运行时包
    'setuptools', 'pip', 'wheel', 'pkg_resources',
    'lib2to3',
]

a = Analysis(
    ['app.py'],
    pathex=[os.path.dirname(os.path.abspath('app.py'))],
    binaries=[],
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
        # src 包
        'src',
        'src.cli',
        'src.__init__',
        'src.models',
        'src.models.__init__',
        'src.modules',
        'src.modules.api_client',
        'src.modules.proxy_server',
        'src.modules.updater',
        'src.utils',
        'src.utils.store',
        'src.utils.machine',
        'src.utils.server_api',
        'src.utils.ssl_pinning',
        'src.utils.env_check',
        'src.utils.proxy',
        'src.utils.model_config',
    ],
    hooksconfig={},
    runtime_hooks=[],
    excludes=PYTHON_EXCLUDES,
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
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codepage=0,
    icon='assets/icons/icon.ico' if os.path.exists('assets/icons/icon.ico') else None,
)
