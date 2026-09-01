@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Cursor Windows 工位一键配置
cd /d "%~dp0"

echo.
echo ========================================
echo   Cursor Windows 工位一键配置
echo ========================================
echo.

call :find_python
if errorlevel 1 (
  echo 正在尝试用 winget 安装 Python 3 ...
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  call :find_python
)
if errorlevel 1 (
  echo.
  echo 找不到 Python 3.10+。请先安装 Python，并勾选 “Add python.exe to PATH”。
  echo 下载: https://www.python.org/downloads/windows/
  echo.
  pause
  exit /b 1
)

echo 使用 Python: %PYTHON%
echo.
%PYTHON% -m workstation.setup
set EXITCODE=%ERRORLEVEL%
echo.
if not "%EXITCODE%"=="0" (
  echo 配置未完成，退出码 %EXITCODE%。
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
