# Cursor-tool：本机工位一键配置（Windows / Ubuntu）

仓库：https://github.com/1358484518/cursor-tool

把你桌上的电脑登记为 Cursor Cloud Agent 的 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines) worker。云端任务在你指定的文件夹里改代码、跑终端，并可调用本机串口和摄像头。

推荐用 GUI 操作：底下仍是官方 `agent worker` 和现成 MCP，窗口只负责选目录、登录、启动。

## 怎么用

在**插着板子、装着编译器的那台电脑**上操作。先拉最新 `main`（不要用旧的中文文件名那一版）。

### 第一次

1. 下载本仓库：https://github.com/1358484518/cursor-tool
2. 安装 Python 3.10 或更高  
   - Windows：用 [python.org](https://www.python.org/downloads/windows/) 安装包，勾选 **Add python.exe to PATH**（自带 Tk 界面）  
   - Ubuntu：`sudo apt install python3 python3-tk`
3. 在仓库目录打开启动窗口：

```bash
python launch.py       # Windows，也可双击 launch.py / launch.bat
python3 launch.py      # Ubuntu
# 或
python3 -m workstation
```

Ubuntu 若提示没有 tkinter：`sudo apt install python3-tk`

4. 在窗口里：
   - **工作文件夹**：选你的固件工程目录（源码、hex 都放这儿）
   - **工位名称**：随便起，[cursor.com/agents](https://cursor.com/agents) 列表里会显示
   - **API Key**：留空
   - **HTTPS 代理**：一般留空。若启动时报 SSL / EPROTO，再填本地代理，例如 `http://127.0.0.1:7890`
   - 点 **检查并写入配置**（第一次会安装官方 `agent` CLI）
   - 点 **浏览器登录**（和 cursor.com **同一个账号**）
   - 点 **启动**，**窗口不要关**
5. 打开 [https://cursor.com/agents](https://cursor.com/agents)，在环境列表里选刚起的那台工位，再发任务。  
   例如：「编译这个工程并看串口日志」。

### 以后每次

打开 `launch.py` → 点 **启动** → 到 agents 里选这台机器。登录一般不用再做。

### 你提需求时 Agent 实际会做什么

- 在你选的文件夹里改代码、跑本机已安装的编译器 / 烧录器（走系统 PATH）
- Linux：串口用现成 [mcp-serial](https://github.com/HumbertoBernal/mcp-serial)，拍照用现成 [framegrab-mcp-server](https://pypi.org/project/framegrab-mcp-server/)
- Windows：串口 / 拍照走本仓库 MCP（对齐上面两个项目，避免再装 uv）

### 注意

- `launch.py` 关了，云端就连不上这台电脑。
- 工程、Keil / gcc / J-Link 等必须装在这台机器上，并已加入 PATH。
- 串口被串口助手占用会打不开。Linux 请执行 `sudo usermod -aG dialout "$USER"` 后**重新登录**。
- 在 cursor.com 里开任务时必须**选中这台工位**。没选中的 Cloud Agent 跑在云端虚拟机里，碰不到你桌上的板子。
- 浏览器能打开 cursor.com，不代表官方 worker 能连上 `api2.cursor.sh`（登录走浏览器，worker 走 Node HTTPS）。

## 这个套件有什么用

需求其实很普通：**让云端 Agent 用你桌上已经装好工具链、插着板子的那台电脑**。

| 你要的能力 | 用现成的什么 |
| --- | --- |
| 连上云端 Agent，在指定文件夹干活 | Cursor 官方 My Machines：`agent worker start --worker-dir …` |
| 编译器 / 烧录器 | worker 的终端 + 系统 PATH |
| 串口（Linux） | 现成 `uvx … mcp-serial` |
| 摄像头（Linux） | 现成 `uvx framegrab-mcp-server` |
| 串口 + 拍照（Windows 一键） | 本仓库 FastMCP（对齐上述两个项目，避免再装 Node/uv） |

## 命令行用法（可选）

不喜欢 GUI 时，也可以只用官方 CLI（与 [My Machines 文档](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines) 相同）：

```bash
# 1. 官方 Cursor CLI
curl https://cursor.com/install -fsS | bash          # macOS / Linux
# Windows PowerShell: irm 'https://cursor.com/install?win32=true' | iex
export PATH="$HOME/.local/bin:$PATH"
agent login

# 2. Linux 现成 MCP（串口 / 拍照）
curl -LsSf https://astral.sh/uv/install.sh | sh
cp mcp.off-the-shelf.json ~/.cursor/mcp.json

# 3. 启动 worker（在固件仓库目录，窗口不要关）
agent worker start --name "$(hostname)" --worker-dir "$PWD"
```

仓库里的封装脚本同样只调官方工具：

```bash
bash setup.sh && bash connect.sh     # Ubuntu
setup.bat / connect.bat              # Windows
```

`mcp.off-the-shelf.json` 与上游文档一致：

```json
{
  "mcpServers": {
    "serial": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/HumbertoBernal/mcp-serial", "mcp-serial"]
    },
    "framegrab": {
      "command": "uvx",
      "args": ["framegrab-mcp-server"],
      "env": { "ENABLE_FRAMEGRAB_AUTO_DISCOVERY": "true" }
    }
  }
}
```

## 环境要求

**Ubuntu / Linux**

- Python 3.10+（脚本向导用；官方 worker 本身不依赖本仓库 Python 包）
- `curl`；脚本会按官方方式安装 Cursor CLI 和 `uv`
- 串口：用户加入 `dialout` 组
- 工具链已在 PATH（`arm-none-eabi-gcc`、OpenOCD、`stm32flash`、J-Link 等）

**Windows 10/11**

- Python 3.10 或更高（没有的话，脚本会尝试用 `winget` 安装）
- 安装 Cursor CLI：`irm 'https://cursor.com/install?win32=true' | iex`
- 本机已安装 Keil、IAR、`arm-none-eabi-gcc`、STM32CubeProgrammer、J-Link 等，并已加入 PATH

## MCP 工具有什么用

**文件和命令不要走硬件 MCP。** 列目录、改源码、编译、烧录都用 worker 自带能力。

Ubuntu 上本仓库**不运行**自研 `windows-workstation` 服务，只写入现成 MCP：

| 来源 | 做什么 |
| --- | --- |
| [mcp-serial](https://github.com/HumbertoBernal/mcp-serial) | `list_ports` / `query` / `reset_device` 等串口工具 |
| [framegrab-mcp-server](https://pypi.org/project/framegrab-mcp-server/) | 发现摄像头并 `grab_frame` |

Windows 上一键配置仍启动本仓库 FastMCP（工具名见下表），避免再装 uv：

| 工具 | 做什么 | 有什么用 | 参考 |
| --- | --- | --- | --- |
| `list_ports` | 列出 COM 口和 USB VID/PID | 确认板子插在哪个口 | mcp-serial `list_ports` |
| `query` | 发送并读取；可 `expect` | MCU 日志、AT、bootloader | mcp-serial `query` |
| `serial_write` | 只发不等待 | hex 帧 | mcp-serial `write` |
| `reset_device` | 脉冲 DTR 并读启动输出 | 抓 boot log | mcp-serial `reset_device` |
| `take_photo` | 拍一帧并返回图像 | 核对 LED / 屏幕 | videocapture-mcp `quick_capture` |

典型一次任务：

1. worker 看工程、改代码、编译并烧录  
2. `list_ports` → `reset_device` 或 `query` 看启动日志  
3. `take_photo` 核对板上现象  

配置会写入：

- `%USERPROFILE%\.cursor\mcp.json` 或 Linux 的 `~/.cursor/mcp.json`
- `<工作文件夹>\.cursor\mcp.json`

工作区路径、工位名保存在套件目录的 `config.local.json`（已 gitignore）以及 `%USERPROFILE%\.cursor-workstation\config.json`。

若 Cloud Agent 没有拉起本机 MCP，把同一条 stdio 命令加到 [Cloud Agents 集成](https://cursor.com/dashboard/integrations)：命令为 Python，参数 `-m workstation.mcp_server`，工作目录/环境变量里带上 `PYTHONPATH`（本仓库根）和 `WORKSTATION_ROOT`。stdio 会在你的工位上跑，才能碰到 COM 口和摄像头。

可选：限制串口。Linux 现成配置默认允许 `/dev/ttyUSB*` 和 `/dev/ttyACM*`；也可设 `MCP_SERIAL_ALLOWED_PORTS`。Windows 自研 MCP 同样认这个环境变量。

## 路径与安全

- **工程文件**：由 Cursor worker 的 `--worker-dir` 限定工作区。终端里的子进程仍可能自行打开别的路径（官方 filesystem MCP 同样不拦截子进程），请把工程和产物放在该文件夹。
- **照片**：`take_photo` 的保存路径仍做 realpath 检查，不能写到工作区外（对齐 [官方 filesystem MCP](https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem) 的 allowed-directory 思路）。
- **串口 / 摄像头**：本机硬件，不走文件沙箱。

## 目录结构

```
cursor-tool/
  launch.py / launch.bat     跨平台 GUI（推荐）
  setup.sh / connect.sh      Ubuntu 命令行
  setup.bat / connect.bat    Windows 命令行
  mcp.off-the-shelf.json      现成 mcp-serial / framegrab
  workstation/gui.py          tkinter 界面
  workstation/launcher.py     组装官方 worker 命令
```

## 命令行等价操作

Ubuntu 直接用官方命令即可（见上文）。向导封装：

```bash
python3 launch.py
python3 -m workstation        # 默认打开 GUI
python3 -m workstation setup  # 命令行向导
python3 -m workstation start  # 无界面启动 worker
```

Windows：

```bat
python launch.py
python -m workstation setup
python -m workstation start
python -m workstation mcp
```

手动启动 worker：

```bash
agent worker start --name 你的工位名 --worker-dir 你的工作文件夹
```

## 排查

- **启动时报 `EPROTO` / `packet length too long` / Failed to validate worker account settings**：TLS 被中间设备打断，配置本身没问题。先点 **检查网络**。
  - 若直连 `api2.cursor.sh` 已是 OK，但系统只有 `HTTP_PROXY`、没有 `HTTPS_PROXY`：窗口代理**留空**再启动。本工具会让 worker 直连，避免 Node 把 TLS 打到公司 HTTP 代理上。
  - 直连失败时，再填 **HTTPS 代理**（`http://host:port`，不要 `https://`，末尾不要 `/`），或：
  ```bash
  export HTTPS_PROXY=http://127.0.0.1:7890
  export HTTP_PROXY="$HTTPS_PROXY"
  export NODE_USE_ENV_PROXY=1
  python3 launch.py
  ```
  也可先跑 `curl -vI https://api2.cursor.sh` 和 `agent worker debug`。桌面双击 `launch.py` **不会**读取 `~/.bashrc` 里的代理。
- **列表里看不到机器**：确认 `launch.py` 窗口还在；同一 Cursor 账号；任务里选中了这台工位；可运行 `agent worker start --debug`。
- **Ubuntu 没有串口/拍照**：确认已装 `uv`（`uvx --version`），`~/.cursor/mcp.json` 与 `mcp.off-the-shelf.json` 一致；可运行 `agent mcp enable serial`。
- **Linux 串口 Permission denied**：把用户加入 `dialout` 后重新登录；设备一般是 `/dev/ttyUSB0` 或 `/dev/ttyACM0`。
- **Windows MCP 没有串口/拍照**：看 `%USERPROFILE%\.cursor\mcp.json` 是否有 `windows-workstation`，然后 `agent mcp enable windows-workstation`。
- **拍照失败**：Linux 用 framegrab；Windows 安装摄像头驱动或 `opencv-python` / ffmpeg。
- **编译器找不到**：把工具链 `bin` 加入 PATH 后重新开 worker。

## 网络

Worker 只需要出站 HTTPS，不必开入站端口。需能访问：

- `api2.cursor.sh` / `api2direct.cursor.sh`
- 产物上传：`cloud-agent-artifacts.s3.us-east-1.amazonaws.com`

走代理时，在窗口填写 **HTTPS 代理**，或设置 `HTTPS_PROXY` / `https_proxy`，并加上 `NODE_USE_ENV_PROXY=1`（[官方说明](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)）。部分代理不能传 HTTP/2，填写代理后本工具会在 `~/.cursor/cli-config.json` 写入 `network.useHttp1ForAgent: true`。

详细说明见 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)。
