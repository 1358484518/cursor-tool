# Cursor-tool：Windows 工位一键配置

仓库：https://github.com/1358484518/cursor-tool

在 Windows 电脑上双击 **`一键配置.bat`**，把这台机器登记为 Cursor Cloud Agent 的 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines) worker。之后云端任务在你指定的文件夹里改代码、跑终端，并可以调用本机串口和摄像头。

## 这个套件有什么用

需求其实很普通：**让云端 Agent 用你桌上那台已经装好 Keil / J-Link / 串口的 Windows 电脑**。这类能力官方和开源里都有现成做法，本仓库按它们来接，而不是再造一套文件协议。

| 你要的能力 | 用现成的什么 |
| --- | --- |
| 双击连上云端 Agent，在指定文件夹干活 | Cursor 官方 My Machines：`agent worker start --worker-dir …`（文件编辑、终端、浏览器都是 worker 自带的） |
| 编译器 / 烧录器 | worker 的终端 + 系统 PATH（Keil、IAR、`arm-none-eabi-gcc`、STM32CubeProgrammer、J-Link） |
| 串口调试、复位抓 boot log | 对齐 [mcp-serial](https://github.com/HumbertoBernal/mcp-serial) 的 `list_ports` / `query` / `reset_device` |
| 拍板子核对 LED / 屏幕 | 对齐 [videocapture-mcp](https://github.com/13rac1/videocapture-mcp) 的 `quick_capture`（开摄像头 → 一帧 → 关闭） |
| MCP 协议本身 | 官方 [Python MCP SDK / FastMCP](https://github.com/modelcontextprotocol/python-sdk)，不再手写 JSON-RPC |

没有它时，Cloud Agent 跑在云端虚拟机里，碰不到你桌上的工具链、COM 口和摄像头。有了它之后，人坐在板子旁边，Agent 在云端改代码、编译、烧录、看串口、拍照核对现象。

## 你要的能力

| 能力 | 怎么实现 |
| --- | --- |
| 双击就能连上 Cursor worker | `一键配置.bat` 安装官方 CLI、登录；`启动连接.bat` 执行 `agent worker start` |
| 工作区限定一个文件夹 | 官方 `--worker-dir`（不是自研文件 MCP） |
| 编译器 / 烧录器可用 | worker 终端保留系统 PATH |
| 串口 / 拍照 | 本机 stdio MCP（FastMCP），仅补充 worker 没有的硬件 |

## 使用步骤

1. 把本仓库放到 Windows 电脑上（克隆或下载均可）。
2. 双击 **`一键配置.bat`**。
3. 按提示指定 worker 工作文件夹（对应 `--worker-dir`；没有会询问是否创建）。
4. 浏览器里登录 Cursor（和 cursor.com 同一个账号）。
5. 配置结束会询问是否立刻启动连接；以后日常只需双击 **`启动连接.bat`**，并保持窗口不要关。
6. 打开 [https://cursor.com/agents](https://cursor.com/agents)，在环境列表里选择这台工位，再发任务。

## 环境要求

- Windows 10/11
- Python 3.10 或更高（没有的话，脚本会尝试用 `winget` 安装）
- 能访问外网，以便安装 Cursor CLI：`irm 'https://cursor.com/install?win32=true' | iex`
- 本机已安装你需要的工具链（Keil、IAR、`arm-none-eabi-gcc`、STM32CubeProgrammer、J-Link 等），并已加入 PATH

## MCP 工具有什么用

**文件和命令不要走这套 MCP。** 列目录、改源码、`gcc` / `STM32_Programmer_CLI` / `JLink.exe` 都用 worker 自带能力。

本仓库只额外拉起一个 stdio MCP（`windows-workstation`），给云端 Agent 用串口和摄像头：

| 工具 | 做什么 | 有什么用 | 参考 |
| --- | --- | --- | --- |
| `list_ports` | 列出 COM 口和 USB VID/PID | 确认板子插在哪个口，按芯片厂家识别适配器 | mcp-serial `list_ports` |
| `query` | 发送并读取；可 `expect` 等到子串，或等到线路安静 | MCU 日志、AT、bootloader；`encoding=hex` 发二进制帧。不传 `data` 则只读 | mcp-serial `query` |
| `serial_write` | 只发不等待 | 发复位命令或 hex 帧 | mcp-serial `write` |
| `reset_device` | 脉冲 DTR 并读启动输出 | 抓 boot log、看 HardFault；Arduino / ESP32 自动复位电路 | mcp-serial `reset_device` |
| `take_photo` | 开摄像头拍一帧后关闭，保存到工作区并把图像返回给 Agent | 核对 LED / 屏幕 / 接线 | videocapture-mcp `quick_capture` |

典型一次任务：

1. worker 看工程、改代码、编译并烧录  
2. `list_ports` → `reset_device` 或 `query` 看启动日志  
3. `take_photo` 核对板上现象  

配置会写入：

- `%USERPROFILE%\.cursor\mcp.json`
- `<工作文件夹>\.cursor\mcp.json`

工作区路径、工位名保存在套件目录的 `config.local.json`（已 gitignore）以及 `%USERPROFILE%\.cursor-workstation\config.json`。

若 Cloud Agent 没有拉起本机 MCP，把同一条 stdio 命令加到 [Cloud Agents 集成](https://cursor.com/dashboard/integrations)：命令为 Python，参数 `-m workstation.mcp_server`，工作目录/环境变量里带上 `PYTHONPATH`（本仓库根）和 `WORKSTATION_ROOT`。stdio 会在你的工位上跑，才能碰到 COM 口和摄像头。

可选：`MCP_SERIAL_ALLOWED_PORTS=COM3,COM4`（逗号分隔 glob）限制 Agent 能碰的串口，与 mcp-serial 的 allowlist 相同。

## 路径与安全

- **工程文件**：由 Cursor worker 的 `--worker-dir` 限定工作区。终端里的子进程仍可能自行打开别的路径（官方 filesystem MCP 同样不拦截子进程），请把工程和产物放在该文件夹。
- **照片**：`take_photo` 的保存路径仍做 realpath 检查，不能写到工作区外（对齐 [官方 filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) 的 allowed-directory 思路）。
- **串口 / 摄像头**：本机硬件，不走文件沙箱。

## 目录结构

```
cursor-tool/
  一键配置.bat          首次安装、选文件夹、登录、可选立即连接
  启动连接.bat          以后每次连 worker（官方 agent worker start）
  requirements.txt      mcp（官方 SDK）、pyserial、opencv-python
  workstation/          Python 套件
    mcp_server.py       FastMCP：list_ports / query / reset_device / take_photo
    serial_io.py        串口（mcp-serial 子集，loop:// 可单测）
    camera.py           拍照（quick_capture）
    sandbox.py          仅约束拍照保存路径
    setup.py / start.py 向导与启动
  tests/                沙箱、loop:// 串口、MCP 协议
```

## 命令行等价操作

```bat
python -m workstation setup
python -m workstation start
python -m workstation mcp
```

手动启动 worker（配置完成后），与[官方文档](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)相同：

```bat
agent worker start --name 你的工位名 --worker-dir 你的工作文件夹
```

## 排查

- **列表里看不到机器**：确认 `启动连接.bat` 窗口还在；用同一个 Cursor 账号；可运行 `agent worker start --debug`。
- **MCP 没有串口/拍照**：看 `%USERPROFILE%\.cursor\mcp.json` 是否有 `windows-workstation`，然后执行 `agent mcp enable windows-workstation`；Cloud Agent 也可在 dashboard 里加同一条 stdio 命令。
- **拍照失败**：安装摄像头驱动，或 `pip install opencv-python`；也可安装 ffmpeg。
- **串口打不开**：设备管理器里确认 COM 口号，关闭占用该口的串口助手。
- **编译器找不到**：在「系统环境变量 → Path」里加入工具链的 `bin` 目录，然后重新开 `启动连接.bat`。

## 网络

Worker 只需要出站 HTTPS，不必开入站端口。需能访问：

- `api2.cursor.sh` / `api2direct.cursor.sh`
- 产物上传：`cloud-agent-artifacts.s3.us-east-1.amazonaws.com`

详细说明见 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)。
