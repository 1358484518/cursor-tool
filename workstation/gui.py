"""跨平台工位启动界面（标准库 tkinter / ttk）。

Win / Linux 同一套窗口：选文件夹、登录、启动/停止官方 `agent worker`。
不实现 MCP 协议，只调用现成 CLI。界面风格参考常见 ttk 启动器（IDLE 同类：原生控件 + 日志框）。
"""

from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path
from queue import Empty, Queue

from workstation.agent_cli import agent_cmd, find_agent, install_agent
from workstation.config import load_config
from workstation.launcher import WorkerProcess, default_worker_name, prepare_session
from workstation.network import probe_session, worker_child_env

AGENTS_URL = "https://cursor.com/agents"


def _require_tk():
    try:
        import tkinter  # noqa: F401
        from tkinter import ttk  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "未找到 tkinter。\n"
            "Ubuntu/Debian:  sudo apt install python3-tk\n"
            "Fedora:         sudo dnf install python3-tkinter\n"
            "Windows:        用 python.org 安装包（自带 Tk）"
        ) from exc


class LauncherApp:
    def __init__(self, root) -> None:
        import tkinter as tk
        from tkinter import filedialog, messagebox, scrolledtext, ttk

        self.tk = tk
        self.filedialog = filedialog
        self.messagebox = messagebox
        self.root = root
        self.queue: Queue[str] = Queue()
        self.worker = WorkerProcess()
        self._busy = False

        cfg = load_config()
        root.title("Cursor 工位")
        root.minsize(560, 480)
        root.geometry("680x540")

        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(root, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="启动官方 Cloud Agent worker。文件和编译走 worker；串口/拍照走现成 MCP。",
            wraplength=600,
        ).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        ttk.Label(frm, text="工作文件夹").grid(row=1, column=0, sticky="e", **pad)
        self.workspace = tk.StringVar(value=str(cfg.get("workspace") or str(Path.home() / "CursorWork")))
        ttk.Entry(frm, textvariable=self.workspace).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="浏览…", command=self._browse).grid(row=1, column=2, **pad)

        ttk.Label(frm, text="工位名称").grid(row=2, column=0, sticky="e", **pad)
        self.worker_name = tk.StringVar(value=str(cfg.get("worker_name") or default_worker_name()))
        ttk.Entry(frm, textvariable=self.worker_name).grid(row=2, column=1, columnspan=2, sticky="ew", **pad)

        ttk.Label(frm, text="API Key").grid(row=3, column=0, sticky="e", **pad)
        self.api_key = tk.StringVar(value=str(cfg.get("api_key") or ""))
        ttk.Entry(frm, textvariable=self.api_key, show="*").grid(row=3, column=1, columnspan=2, sticky="ew", **pad)
        ttk.Label(frm, text="可留空，改用「浏览器登录」", foreground="#555").grid(
            row=4, column=1, columnspan=2, sticky="w", padx=10
        )

        ttk.Label(frm, text="HTTPS 代理").grid(row=5, column=0, sticky="e", **pad)
        self.https_proxy = tk.StringVar(
            value=str(cfg.get("https_proxy") or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "")
        )
        ttk.Entry(frm, textvariable=self.https_proxy).grid(row=5, column=1, columnspan=2, sticky="ew", **pad)
        ttk.Label(
            frm,
            text="可留空。连不上 api2.cursor.sh 时填写，例如 http://127.0.0.1:7890（Clash）或 10809（v2rayN）",
            foreground="#555",
            wraplength=520,
        ).grid(row=6, column=1, columnspan=2, sticky="w", padx=10)

        btns = ttk.Frame(frm)
        btns.grid(row=7, column=0, columnspan=3, sticky="w", pady=8)
        row1 = ttk.Frame(btns)
        row1.pack(anchor="w")
        row2 = ttk.Frame(btns)
        row2.pack(anchor="w", pady=(4, 0))
        ttk.Button(row1, text="检查并写入配置", command=self._on_prepare).pack(side="left", padx=4)
        ttk.Button(row1, text="浏览器登录", command=self._on_login).pack(side="left", padx=4)
        ttk.Button(row1, text="检查网络", command=self._on_check_network).pack(side="left", padx=4)
        self.btn_start = ttk.Button(row2, text="启动", command=self._on_start)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(row2, text="停止", command=self._on_stop, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        ttk.Button(row2, text="打开 Agents", command=lambda: webbrowser.open(AGENTS_URL)).pack(side="left", padx=4)

        self.status = tk.StringVar(value="未运行")
        ttk.Label(frm, textvariable=self.status).grid(row=8, column=0, columnspan=3, sticky="w", **pad)

        self.log = scrolledtext.ScrolledText(frm, height=14, wrap="word", state="disabled")
        self.log.grid(row=9, column=0, columnspan=3, sticky="nsew", **pad)

        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(9, weight=1)

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._pump()

    def _append(self, msg: str) -> None:
        self.queue.put(msg)

    def _pump(self) -> None:
        try:
            while True:
                line = self.queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", line + "\n")
                self.log.see("end")
                self.log.configure(state="disabled")
        except Empty:
            pass
        self.root.after(120, self._pump)

    def _browse(self) -> None:
        path = self.filedialog.askdirectory(title="选择 worker 工作文件夹")
        if path:
            self.workspace.set(path)

    def _collect(self) -> tuple[str, str, str, str]:
        ws = self.workspace.get().strip()
        if not ws:
            raise ValueError("请先选择工作文件夹")
        folder = Path(ws).expanduser()
        if not folder.exists():
            if self.messagebox.askyesno("创建文件夹", f"文件夹不存在，是否创建？\n{folder}"):
                folder.mkdir(parents=True, exist_ok=True)
            else:
                raise ValueError("未选择有效工作文件夹")
        return (
            str(folder),
            self.worker_name.get().strip(),
            self.api_key.get().strip(),
            self.https_proxy.get().strip(),
        )

    def _run_bg(self, fn) -> None:
        if self._busy:
            return
        self._busy = True

        def wrap() -> None:
            try:
                fn()
            except Exception as exc:  # noqa: BLE001
                self._append(f"错误: {exc}")
            finally:
                self._busy = False

        threading.Thread(target=wrap, daemon=True).start()

    def _on_prepare(self) -> None:
        try:
            args = self._collect()
        except ValueError as exc:
            self.messagebox.showerror("提示", str(exc))
            return

        def work() -> None:
            ws, name, key, proxy = args
            self._append("正在检查 CLI 并写入 MCP 配置…")
            info = prepare_session(ws, name, key, https_proxy=proxy, log=self._append)
            self._append(f"工位: {info['worker_name']}")
            self._append(f"工作区: {info['workspace']}")
            self._append("配置完成。下一步：登录（如需要）然后点「启动」。")

        self._run_bg(work)

    def _on_login(self) -> None:
        def work() -> None:
            self._append("正在打开浏览器登录（agent login）…")
            agent = find_agent() or install_agent()
            completed = agent_cmd(agent, "login", env=worker_child_env(self.https_proxy.get().strip()))
            if completed.stdout:
                self._append(completed.stdout.strip())
            if completed.stderr:
                self._append(completed.stderr.strip())
            self._append("登录命令结束。" if completed.returncode == 0 else f"登录退出码 {completed.returncode}")
            self._append("登录走浏览器，worker 另走 Node HTTPS。若启动时报 EPROTO / SSL，请点「检查网络」或填写代理。")

        self._run_bg(work)

    def _on_check_network(self) -> None:
        proxy = self.https_proxy.get().strip()

        def work() -> None:
            self._append("正在检查 worker 出站网络（api2.cursor.sh）…")
            session = probe_session(proxy)
            for line in session["lines"]:
                self._append(line)
            agent = find_agent()
            if agent is None:
                self._append("未找到 agent CLI，可先点「检查并写入配置」。")
                return
            self._append("运行 agent worker debug …")
            try:
                completed = agent_cmd(
                    agent,
                    "worker",
                    "debug",
                    env=session["env"],
                    capture_output=True,
                    timeout=90,
                )
            except Exception as exc:  # noqa: BLE001
                self._append(f"debug 失败: {exc}")
                return
            if completed.stdout:
                self._append(completed.stdout.strip())
            if completed.stderr:
                self._append(completed.stderr.strip())
            if not completed.stdout and not completed.stderr:
                self._append("(debug 没有输出)")
            self._append(
                "检查结束。" if completed.returncode == 0 else f"debug 退出码 {completed.returncode}"
            )

        self._run_bg(work)

    def _on_start(self) -> None:
        try:
            args = self._collect()
        except ValueError as exc:
            self.messagebox.showerror("提示", str(exc))
            return

        def work() -> None:
            if self.worker.running:
                self._append("已经在运行。")
                return
            ws, name, key, proxy = args
            self._append("准备启动官方 worker…")
            info = prepare_session(ws, name, key, https_proxy=proxy, log=self._append)
            self._append("命令: " + str(info["display"]))
            session = probe_session(proxy)
            for line in session["lines"]:
                self._append(line)
            self.root.after(0, lambda: self.status.set(f"运行中 · {info['worker_name']}"))
            self.root.after(0, lambda: self.btn_start.state(["disabled"]))
            self.root.after(0, lambda: self.btn_stop.state(["!disabled"]))
            self.worker.start(info["command"], self._append, env=session["env"])
            self._busy = False
            self.worker.pump_output(self._append)
            code = self.worker.proc.returncode if self.worker.proc else None
            self.worker.proc = None
            self._append(f"worker 已退出（code={code}）")
            self.root.after(0, lambda: self.status.set("未运行"))
            self.root.after(0, lambda: self.btn_start.state(["!disabled"]))
            self.root.after(0, lambda: self.btn_stop.state(["disabled"]))

        self._run_bg(work)

    def _on_stop(self) -> None:
        def work() -> None:
            self.worker.stop(self._append)

        self._run_bg(work)

    def _on_close(self) -> None:
        if self.worker.running:
            if not self.messagebox.askokcancel("退出", "worker 正在运行，关闭窗口将停止连接。"):
                return
            self.worker.stop(self._append)
        self.root.destroy()


def main() -> None:
    _require_tk()
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista" if os.name == "nt" else "clam")
    except Exception:
        pass
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
