@echo off
chcp 65001 >nul 2>nul

echo ========================================
echo   BuddyToolNew Build - PyInstaller
echo ========================================
echo.

cd /d "%~dp0"

REM Check uv
where uv >nul 2>nul
if errorlevel 1 (
    echo [ERROR] uv not found!
    pause
    exit /b 1
)

REM Add UPX to PATH for compression
if exist "%~dp0tools\upx.exe" set PATH=%~dp0tools;%PATH%

REM Sync dependencies
echo Syncing dependencies...
uv sync -q
if errorlevel 1 (
    echo [ERROR] uv sync failed!
    pause
    exit /b 1
)

REM Clean old build artifacts
if exist "dist\BuddyToolNew.exe" del /q "dist\BuddyToolNew.exe"
if exist "dist\BuddyToolNew" rmdir /s /q dist\BuddyToolNew
if exist "build" rmdir /s /q build

echo Building with .spec file, please wait...
echo.

uv run python -m PyInstaller BuddyToolNew.spec --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build OK!
echo   Output: dist\BuddyToolNew.exe
echo ========================================
echo.

for %%A in ("dist\BuddyToolNew.exe") do echo Size: %%~zA bytes

echo.
echo Done. Distribute dist\BuddyToolNew.exe to users.
echo.

pause
