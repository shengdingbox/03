"""自动更新模块 - 版本读取

当前 CLI 无更新检查命令，此模块仅保留本地版本号读取。
"""

import sys
from pathlib import Path

# 本地版本文件
VERSION_FILE = Path(__file__).parent.parent / "VERSION"


def get_current_version() -> str:
    """读取本地版本号

    源码模式: src/VERSION（项目根目录下）
    打包模式: Nuitka onefile 解压后 VERSION 通过 --include-data-file 打包进来
    """
    candidates = [
        VERSION_FILE,                                    # 源码: <root>/src/VERSION
        Path(__file__).parent / "VERSION",               # 同目录
        Path(__file__).parent.parent / "VERSION",        # src/VERSION
        Path(__file__).parent.parent.parent / "VERSION", # 根目录 VERSION
    ]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidates.extend([
            exe_dir / "src" / "VERSION",
            exe_dir / "VERSION",
        ])
    if hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)
        candidates.extend([
            meipass / "src" / "VERSION",
            meipass / "VERSION",
        ])
    for candidate in candidates:
        try:
            if candidate.is_file():
                ver = candidate.read_text(encoding="utf-8").strip()
                if ver:
                    return ver
        except Exception:
            continue
    return "0.0.0"
