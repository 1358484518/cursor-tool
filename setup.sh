#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo
echo "========================================"
echo "  Cursor Ubuntu/Linux 工位一键配置"
echo "========================================"
echo "只用现成工具，不安装本仓库自研 MCP："
echo "  - Cursor 官方 agent worker（文件/终端/编译烧录）"
echo "  - mcp-serial（串口）"
echo "  - framegrab-mcp-server（摄像头）"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "找不到 python3。请先安装："
  echo "  sudo apt update && sudo apt install -y python3 python3-pip python3-venv curl"
  exit 1
fi

if ! python3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"; then
  echo "需要 Python 3.10 或更高，当前: $(python3 --version)"
  exit 1
fi

echo "使用 Python: $(command -v python3) ($(python3 --version))"
echo
exec python3 -m workstation.setup
