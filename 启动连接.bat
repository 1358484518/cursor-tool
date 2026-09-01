@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Cursor Windows 工位连接
cd /d "%~dp0"

echo.
echo ========================================
echo   启动 Cursor worker 连接
echo ========================================
echo 作用：运行官方 agent worker start，保持与 Cloud Agent 的连接。
echo 本机工作区里改代码、编译烧录；串口和拍照走 MCP。
echo 请保持本窗口开启。关闭后云端将无法使用这台工位。
echo.

call :find_python
if errorlevel 1 (
  echo 找不到 Python 3.10+。请先双击 一键配置.bat
  echo.
  pause
  exit /b 1
)

%PYTHON% -m workstation.start
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo 连接结束，退出码 %EXITCODE%。
)
pause
exit /b %EXITCODE%

:find_python
set PYTHON=
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=py -3.12"
  exit /b 0
)
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=py -3"
  exit /b 0
)
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=python"
  exit /b 0
)
python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
  set "PYTHON=python3"
  exit /b 0
)
exit /b 1
