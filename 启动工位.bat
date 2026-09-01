@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Cursor 工位
cd /d "%~dp0"

py -3 "%~dp0启动工位.py" 2>nul
if not errorlevel 1 exit /b 0
python "%~dp0启动工位.py"
if errorlevel 1 (
  echo 启动失败。请确认已安装 Python 3.10+（python.org 安装包自带 Tk 界面）。
  pause
)
