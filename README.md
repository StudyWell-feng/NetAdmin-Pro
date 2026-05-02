# NetAdmin Pro - Windows 网络管理员工具箱

一款基于 Python + CustomTkinter 的 Windows 桌面网络管理工具，提供 IP 配置、软件安装、网络检测、代理配置、网络修复、硬件信息检测等一站式功能。

## 项目介绍

NetAdmin Pro 是专为网络管理员和 IT 运维人员打造的效率工具。在日常运维工作中，经常需要频繁切换 IP 地址、安装常用软件、排查网络故障、查看硬件配置——这些操作通常需要打开各种系统设置、命令行窗口或第三方工具，流程繁琐且效率低下。

NetAdmin Pro 将这些常用操作整合到一个简洁的图形界面中，告别反复敲命令的繁琐流程：

- **预设方案，一键切换** — 提前配置好各办公区的 IP 方案、代理方案，到不同区域一秒钟切换，不用再手敲地址
- **批量安装，解放双手** — 将常用软件安装包路径写入配置，新机器装机时批量一键安装，不用逐个点下一步
- **网络排障，集成诊断** — Ping、Tracert、端口检测、DNS 查询集中在一个面板，排查网络问题不用开多个终端
- **硬件检测，一目了然** — 类似图吧工具箱的硬件信息检测，CPU/GPU 温度实时监控，硬盘 SSD/HDD 自动识别
- **绿色便携，无需安装** — 打包为单个 EXE 文件，拷到 U 盘随身携带，任何 Windows 10/11 电脑直接运行

适用于企业 IT 运维、机房管理、技术支持、个人电脑维护等场景。界面采用现代化深色主题，操作直观，上手即用。

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D6.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## 功能特性

### IP 配置
- 预设多套 IP 配置方案（办公区、服务器区等），一键切换
- 自动检测当前网络适配器，快速修改 IP / 子网掩码 / 网关 / DNS
- 管理员权限自动提示

### 软件安装
- 配置常用软件安装包路径，一键静默安装
- 支持配置安装参数（如 `/silent`、`/quiet`、`/S` 等）
- 支持批量安装，安装进度实时显示

### 网络检测
- **Ping 测试**：支持批量 Ping 多个目标地址，实时显示延迟和丢包率
- **Tracert 路由追踪**：可视化路由跳转路径
- **端口检测**：TCP 端口连通性测试
- **DNS 查询**：域名解析结果查看

### 代理配置
- 预设 HTTP / HTTPS / SOCKS5 代理方案，一键切换
- 支持代理例外地址配置
- 一键清除系统代理设置

### 网络修复
- 一键重置 Winsock 目录
- 一键刷新 DNS 缓存
- 一键释放/续租 IP 地址（ipconfig /release & /renew）
- 一键重置 TCP/IP 协议栈
- 一键清除 ARP 缓存

### 硬件信息检测
- **CPU**：型号、核心数、线程数、频率、实时使用率
- **GPU**：型号、显存、驱动版本、NVIDIA 温度检测
- **内存**：总容量、已用、可用、使用率
- **硬盘**：型号、容量、类型（SSD/HDD 自动识别）
- **主板**：制造商、型号、版本
- **系统**：操作系统版本、架构信息

## 截图预览

> 启动后左侧为功能导航栏，右侧为操作区域，底部为全局日志输出。

## 项目结构

```
NetAdmin/
├── net_admin.py          # 主程序入口，包含 IP/软件/网络/代理/修复 面板
├── hardware_panel.py     # 硬件信息检测模块（独立面板）
├── config.json           # 配置文件（IP方案/软件包/代理方案）
├── 启动.bat              # 普通启动脚本
├── 管理员启动.bat         # 管理员权限启动脚本
├── 打包exe.bat            # PyInstaller 打包脚本
└── README.md
```

## 快速开始

### 环境要求

- Windows 10 / 11
- Python 3.12+

### 安装依赖

```bash
pip install customtkinter pillow
```

### 运行

```bash
# 普通模式启动（部分功能需要管理员权限）
python net_admin.py

# 或使用管理员权限启动（推荐）
# 右键 "管理员启动.bat" → 以管理员身份运行
```

### 打包为 EXE

```bash
# 方式一：使用打包脚本
双击运行 "打包exe.bat"

# 方式二：手动打包
pip install pyinstaller
pyinstaller --onefile --windowed --name "NetAdmin Pro" --add-data "config.json;." net_admin.py
```

打包产物位于 `dist/NetAdmin Pro.exe`，可直接分发使用，无需安装 Python 环境。

> 注意：打包后的 EXE 首次运行会在同目录生成 `config.json`，可直接编辑该文件自定义配置。

## 配置说明

编辑 `config.json` 来自定义 IP 方案、软件包和代理配置：

### IP 配置方案

```json
{
  "ip_profiles": [
    {
      "name": "办公区 A 区",
      "ip": "192.168.1.100",
      "mask": "255.255.255.0",
      "gateway": "192.168.1.1",
      "dns1": "114.114.114.114",
      "dns2": "8.8.8.8"
    }
  ]
}
```

### 软件安装包

```json
{
  "packages": [
    {
      "name": "Chrome 浏览器",
      "icon": "🌐",
      "path": "C:\\Installers\\ChromeSetup.exe",
      "args": "/silent /install",
      "description": "Google Chrome 浏览器最新版"
    }
  ]
}
```

### 代理配置方案

```json
{
  "proxy_profiles": [
    {
      "name": "公司代理",
      "http_addr": "192.168.1.200",
      "http_port": "8080",
      "https_addr": "192.168.1.200",
      "https_port": "8080",
      "bypass": "localhost;127.0.0.1;<local>"
    }
  ]
}
```

## 技术栈

| 技术 | 说明 |
|------|------|
| Python 3.12 | 主开发语言 |
| CustomTkinter 5.x | 现代化深色主题 GUI 框架 |
| PyInstaller 6.x | 单文件 EXE 打包 |
| WMIC / PowerShell | Windows 硬件与网络信息采集 |
| nvidia-smi | NVIDIA GPU 温度检测 |

## 注意事项

- **IP 配置功能**需要以管理员权限运行，否则会提示权限不足
- **硬件温度检测**仅支持 NVIDIA 显卡（依赖 nvidia-smi 工具）
- **硬盘类型识别**（SSD/HDD）依赖 PowerShell `Get-PhysicalDisk` 命令，需要 Windows 8+ / Server 2012+
- 建议将常用软件安装包放到统一目录（如 `C:\Installers\`），并在 `config.json` 中配置路径

## License

[MIT](LICENSE)
