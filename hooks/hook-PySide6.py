# Override PySide6 hook: do NOT call collect_extra_binaries()
# Binaries are manually curated in BuddyToolNew.spec via _collect_pyside6_binaries()
from PyInstaller.utils.hooks import check_requirement
from PyInstaller.utils.hooks.qt import ensure_single_qt_bindings_package

ensure_single_qt_bindings_package("PySide6")

hiddenimports = ['shiboken6', 'inspect']

if check_requirement("PySide6 >= 6.4.0"):
    hiddenimports += ['PySide6.support.deprecated']

# No binaries collection here - handled by spec file
binaries = []
