# Cusor-tool：Windows 工位一键配置

在 Windows 电脑上双击 **`一键配置.bat`**，即可把这台机器连到 Cursor Cloud Agent（My Machines / worker）。之后云端任务会在你的工位上执行：读写你指定的**一个文件夹**，并可以调用系统里已经装好的编译器、烧录器。

## 你要的能力

| 能力 | 怎么实现 |
| --- | --- |
| 双击就能连上 Cursor worker | `一键配置.bat` 安装 CLI、登录、写 MCP；`启动连接.bat` 保持连接 |
| 只能读写一个指定文件夹 | Python `workstation/sandbox.py` 解析真实路径，拦截 `..` 和符号链接逃逸 |
| 编译器 / 烧录器可用 | `run_command` 保留系统 PATH，工作目录锁在该文件夹内 |
| MCP 工具 | 列目录、读写文件、跑命令、串口、拍照 |

## 使用步骤

1. 把本仓库放到 Windows 电脑上（克隆或下载均可）。
2. 双击 **`一键配置.bat`**。
3. 按提示指定**唯一允许读写的工作文件夹**（没有会询问是否创建）。
4. 浏览器里登录 Cursor（和 cursor.com 同一个账号）。
5. 配置结束会询问是否立刻启动连接；以后日常只需双击 **`启动连接.bat`**，并保持窗口不要关。
6. 打开 [https://cursor.com/agents](https://cursor.com/agents)，在环境列表里选择这台工位，再发任务。

## 环境要求

- Windows 10/11
- Python 3.10 或更高（没有的话，脚本会尝试用 `winget` 安装）
- 能访问外网，以便安装 Cursor CLI：`irm 'https://cursor.com/install?win32=true' | iex`
- 本机已安装你需要的工具链（Keil、IAR、`arm-none-eabi-gcc`、STM32CubeProgrammer、J-Link 等），并已加入 PATH

## MCP 工具

Cursor worker 会在本机拉起 stdio MCP（`windows-workstation`）：

| 工具 | 作用 |
| --- | --- |
| `list_dir` | 列出工作文件夹内的目录 |
| `read_file` | 读工作文件夹内的文件（文本或 hex） |
| `write_file` | 写工作文件夹内的文件 |
| `run_command` | 在该文件夹内执行命令；可调用系统编译器/烧录器 |
| `serial_list` | 列出 COM 口 |
| `serial_send` | 串口收发（`encoding=hex` 可发十六进制） |
| `take_photo` | 摄像头拍照，保存到工作文件夹（默认 `capture.jpg`） |

配置会写入：

- `%USERPROFILE%\.cursor\mcp.json`
- `<工作文件夹>\.cursor\mcp.json`

工作区路径、工位名保存在套件目录的 `config.local.json`（已 gitignore）以及 `%USERPROFILE%\.cursor-workstation\config.json`。

## 路径限制说明

- 所有文件 MCP 都经过 `resolve_in_root()`：相对路径从工作区算起，绝对路径也必须落在工作区内。
- `..`、符号链接、盘符跳转如果最终落到工作区外，会返回错误，不会读写。
- `run_command` 的 **cwd 必须在工作区内**。`gcc`、`STM32_Programmer_CLI`、`JLink.exe` 等可以走系统 PATH。
- 串口和摄像头是本机硬件，不走文件沙箱；拍下的照片仍必须存进工作区。

Python 无法像操作系统沙箱那样拦截子进程自己去打开别的磁盘文件。请把工程、产物都放在指定文件夹里，不要让命令去读写别的目录。

## 目录结构

```
Cusor-tool/
  一键配置.bat          首次安装、选文件夹、登录、可选立即连接
  启动连接.bat          以后每次连 worker
  requirements.txt      pyserial、opencv-python
  workstation/          Python 套件
    sandbox.py          路径限制
    mcp_server.py       MCP stdio 服务
    fs_tools.py         列目录 / 读写 / 跑命令
    serial_io.py        串口
    camera.py           拍照
    setup.py / start.py 向导与启动
  tests/                路径限制与 MCP 协议测试
```

## 命令行等价操作

```bat
python -m workstation setup
python -m workstation start
python -m workstation mcp
```

手动启动 worker（配置完成后）：

```bat
agent worker start --name 你的工位名 --worker-dir 你的工作文件夹
```

## 排查

- **列表里看不到机器**：确认 `启动连接.bat` 窗口还在；用同一个 Cursor 账号；可运行 `agent worker start --debug`。
- **MCP 没有工具**：看 `%USERPROFILE%\.cursor\mcp.json` 是否有 `windows-workstation`，然后执行 `agent mcp enable windows-workstation`。
- **拍照失败**：安装摄像头驱动，或 `pip install opencv-python`；也可安装 ffmpeg。
- **串口打不开**：设备管理器里确认 COM 口号，关闭占用该口的串口助手。
- **编译器找不到**：在「系统环境变量 → Path」里加入工具链的 `bin` 目录，然后重新开 `启动连接.bat`。

## 网络

Worker 只需要出站 HTTPS，不必开入站端口。需能访问：

- `api2.cursor.sh` / `api2direct.cursor.sh`
- 产物上传：`cloud-agent-artifacts.s3.us-east-1.amazonaws.com`

详细说明见 [My Machines](https://cursor.com/docs/cloud-agent/self-hosted-guides/my-machines)。
