# Cursor-tool：Windows 工位一键配置

仓库：https://github.com/1358484518/cursor-tool

在 Windows 电脑上双击 **`一键配置.bat`**，即可把这台机器连到 Cursor Cloud Agent（My Machines / worker）。之后云端任务会在你的工位上执行：读写你指定的**一个文件夹**，并可以调用系统里已经装好的编译器、烧录器。

## 这个套件有什么用

把你的 Windows 电脑变成云端 Agent 的工位，专门给**嵌入式 / 固件开发**用：人坐在板子旁边，Agent 在云端改代码、编译、烧录、看串口、拍照核对现象。

没有它时，Cloud Agent 跑在云端虚拟机里，碰不到你桌上的 Keil、J-Link、COM 口和摄像头。有了它之后：

- 云端任务落在你指定的**一个工程文件夹**里，不会随便扫整块硬盘。
- 本机已装好的工具链仍可用（Keil、IAR、`arm-none-eabi-gcc`、STM32CubeProgrammer、J-Link 等）。
- 开发板插在这台电脑上就能烧录、看日志、拍一张板子照片给 Agent 看。

适合：STM32 / ARM 固件改 bug、编译烧录、串口调 AT、核对 LED/屏幕是否按预期亮。

## 你要的能力

| 能力 | 怎么实现 |
| --- | --- |
| 双击就能连上 Cursor worker | `一键配置.bat` 安装 CLI、登录、写 MCP；`启动连接.bat` 保持连接 |
| 只能读写一个指定文件夹 | Python `workstation/sandbox.py` 解析真实路径，拦截 `..` 和符号链接逃逸 |
| 编译器 / 烧录器可用 | `run_command` 保留系统 PATH，工作目录锁在该文件夹内 |
| MCP 工具 | 列目录、读写、编译烧录、串口、拍照；每项用途见下方表格 |

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

## MCP 工具有什么用

Cursor worker 会在本机拉起 stdio MCP（`windows-workstation`）。下面这些工具是给**云端 Agent** 调用的；说明里写清了「能做什么」和「什么时候用」。

| 工具 | 做什么 | 有什么用 |
| --- | --- | --- |
| `list_dir` | 列出工作文件夹内的目录 | 摸清工程结构，找到 `.uvprojx` / Makefile / 源码目录，定位 hex、bin、map 产物 |
| `read_file` | 读工作文件夹内的文件（文本或 hex） | 看源码、链接脚本、编译日志、map；固件二进制用 `encoding=hex` |
| `write_file` | 写工作文件夹内的文件 | 改源码、打补丁、生成编译/烧录脚本、保存日志；不能写出工作区 |
| `run_command` | 在该文件夹内执行命令 | 编译（gcc / Keil / IAR）、烧录（STM32CubeProgrammer / J-Link）、跑测试；cwd 锁在工作区，可执行文件走系统 PATH |
| `serial_list` | 列出本机 COM 口 | 确认板子插在哪个口、排查被串口助手占用，给 `serial_send` 选 `port` |
| `serial_send` | 串口收发（默认 8N1；`encoding=hex` 可发十六进制） | MCU 日志、AT 命令、bootloader 交互；确认烧录后设备是否起来。不传 `data` 则只读 |
| `take_photo` | 摄像头拍照，保存到工作文件夹（默认 `capture.jpg`） | 核对 LED / 屏幕 / 接线；烧录后目视确认，把现场照片交给 Agent 分析 |

典型一次任务会串起来用：

1. `list_dir` → `read_file` 看工程和源码  
2. `write_file` 改代码  
3. `run_command` 编译并烧录  
4. `serial_list` → `serial_send` 看启动日志  
5. `take_photo` 核对板上现象

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
cursor-tool/
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
