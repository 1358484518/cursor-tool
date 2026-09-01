"""python -m workstation 入口。"""

from __future__ import annotations

import sys


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] in {"gui", "ui", "launcher"}:
        from workstation.gui import main as gui_main

        gui_main()
        return
    if args[0] in {"setup", "configure", "config"}:
        from workstation.setup import main as setup_main

        setup_main()
        return
    if args[0] in {"start", "connect", "worker"}:
        from workstation.start import main as start_main

        start_main()
        return
    if args[0] in {"mcp", "serve"}:
        from workstation.mcp_server import main as mcp_main

        mcp_main()
        return
    print("用法: python -m workstation [gui|setup|start|mcp]", flush=True)
    raise SystemExit(2)


if __name__ == "__main__":
    main()
