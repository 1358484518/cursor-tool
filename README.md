# Cursor-tool：本机工位一键配置（Windows / Ubuntu）

仓库：https://github.com/1358484518/cursor-tool

把你桌上的电脑登记为 Cursor Cloud Agent 的 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines) worker。云端任务在你指定的文件夹里改代码、跑终端，并可调用本机串口和摄像头。

## 最简单：跑一个 Python 窗口

Win / Linux 同一个入口（标准库 **tkinter**，不再写两套脚本）：

```bash
python launch.py          # Windows 也可双击 launch.py / launch.bat
python3 launch.py         # Ubuntu
# 或
python3 -m workstation
```

窗口里选工作文件夹 →（可选）浏览器登录 → 点 **启动**。它只做三件事：写入现成 MCP 配置、调用官方 `agent worker start`、把日志打在窗口里。

Ubuntu 若提示没有 tkinter：

```bash
sudo apt install python3-tk
```

然后到 [cursor.com/agents](https://cursor.com/agents) 选这台机器即可。

**Ubuntu 不必用本仓库自研 MCP。** 文件和终端用官方 `agent worker`；串口用现成的 [mcp-serial](https://github.com/HumbertoBernal/mcp-serial)；拍照用现成的 [framegrab-mcp-server](https://pypi.org/project/framegrab-mcp-server/)。

## 这个套件有什么用

需求其实很普通：**让云端 Agent 用你桌上已经装好工具链、插着板子的那台电脑**。

| 你要的能力 | 用现成的什么 |
| --- | --- |
| 连上云端 Agent，在指定文件夹干活 | Cursor 官方 My Machines：`agent worker start --worker-dir …` |
| 编译器 / 烧录器 | worker 的终端 + 系统 PATH |
| 串口（Linux） | 现成 `uvx … mcp-serial` |
| 摄像头（Linux） | 现成 `uvx framegrab-mcp-server` |
| 串口 + 拍照（Windows 一键） | 本仓库 FastMCP（对齐上述两个项目，避免再装 Node/uv） |

## Ubuntu 怎么用（推荐：直接用官方命令）

在工程目录里执行（与[官方文档](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)相同）：

```bash
# 1. 官方 Cursor CLI
curl https://cursor.com/install -fsS | bash
export PATH="$HOME/.local/bin:$PATH"
agent login

# 2. 现成 MCP 运行器
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# 3. 把仓库里的现成配置拷到 Cursor（或手动合并）
mkdir -p ~/.cursor
cp mcp.off-the-shelf.json ~/.cursor/mcp.json

# 4. 串口权限（USB 转串口）
sudo usermod -aG dialout "$USER"   # 然后注销再登录

# 5. 启动 worker（窗口不要关）
agent worker start --name "$(hostname)" --worker-dir "$PWD"
```

然后打开 [cursor.com/agents](https://cursor.com/agents)，在环境列表里选这台机器。

也可以在本仓库目录运行封装脚本（同样只调官方 CLI + 现成 MCP，不装自研服务）：

```bash
git clone https://github.com/1358484518/cursor-tool
cd cursor-tool
bash setup.sh
# 以后每次：
bash connect.sh
```

`mcp.off-the-shelf.json` 里的启动方式与上游文档一致：

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

## Windows 怎么用

1. 把本仓库放到电脑上，双击 **`setup.bat`**。
2. 指定 worker 工作文件夹（`--worker-dir`）。
3. 浏览器登录 Cursor。
4. 以后日常双击 **`connect.bat`**（或用 **`launch.py`**），窗口不要关。
5. 打开 [cursor.com/agents](https://cursor.com/agents)，选这台工位再发任务。

## 你要的能力

| 能力 | 怎么实现 |
| --- | --- |
| 连上 Cursor worker | `python launch.py`（官方 `agent worker start`） |
| 工作区限定一个文件夹 | 官方 `--worker-dir` |
| 编译器 / 烧录器可用 | worker 终端保留系统 PATH |
| 串口 / 拍照 | Ubuntu：现成 uvx MCP；Windows：本仓库 FastMCP |

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

- **列表里看不到机器**：确认 worker 终端还在；同一 Cursor 账号；`agent worker start --debug`。
- **Ubuntu 没有串口/拍照**：确认已装 `uv`（`uvx --version`），`~/.cursor/mcp.json` 与 `mcp.off-the-shelf.json` 一致；可运行 `agent mcp enable serial`。
- **Linux 串口 Permission denied**：把用户加入 `dialout` 后重新登录；设备一般是 `/dev/ttyUSB0` 或 `/dev/ttyACM0`。
- **Windows MCP 没有串口/拍照**：看 `%USERPROFILE%\.cursor\mcp.json` 是否有 `windows-workstation`，然后 `agent mcp enable windows-workstation`。
- **拍照失败**：Linux 用 framegrab；Windows 安装摄像头驱动或 `opencv-python` / ffmpeg。
- **编译器找不到**：把工具链 `bin` 加入 PATH 后重新开 worker。

## 网络

Worker 只需要出站 HTTPS，不必开入站端口。需能访问：

- `api2.cursor.sh` / `api2direct.cursor.sh`
- 产物上传：`cloud-agent-artifacts.s3.us-east-1.amazonaws.com`

详细说明见 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)。
