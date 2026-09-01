#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "========================================"
echo "  启动 Cursor worker 连接"
echo "========================================"
echo "作用：运行官方 agent worker start。"
echo "文件和编译走 worker；串口/拍照走现成 MCP（mcp-serial / framegrab）。"
echo "请保持本终端不要关闭。"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "找不到 python3。请先运行: bash 一键配置.sh"
  exit 1
fi

exec python3 -m workstation.start
