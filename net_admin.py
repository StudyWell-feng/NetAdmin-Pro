#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络管理员工具 - NetAdmin Pro
功能: 一键配置IP地址 | 一键安装软件包 | 网络信息查看
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import json
import os
import sys
import subprocess
import threading
import socket
import struct
import ctypes
import re
from datetime import datetime
from pathlib import Path

from hardware_panel import HardwarePanel

# ─── 主题设置 ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ─── 全局字体设置（确保跨机器中文显示一致） ────────────────────────────────────
import platform as _platform
_sys = _platform.system()
if _sys == "Windows":
    _FONT_FAMILY = "Microsoft YaHei"   # 微软雅黑，Windows 7+ 自带
elif _sys == "Darwin":
    _FONT_FAMILY = "PingFang SC"       # 苹方，macOS 自带
else:
    _FONT_FAMILY = "Noto Sans CJK SC"  # Linux 常见中文字体

# ─── 配置文件路径 ─────────────────────────────────────────────────────────────
# PyInstaller 打包后 __file__ 指向临时目录，配置文件应该放在 EXE 同目录以便持久化
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
# 如果 EXE 同目录没有 config.json，从内置资源复制一份
if getattr(sys, 'frozen', False) and not CONFIG_FILE.exists():
    _bundled = Path(sys._MEIPASS) / "config.json"
    if _bundled.exists():
        import shutil
        shutil.copy2(str(_bundled), str(CONFIG_FILE))

# ─── 颜色常量 ─────────────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":       "#0f1117",
    "bg_card":       "#1a1d2e",
    "bg_card2":      "#1e2235",
    "accent_blue":   "#4f8ef7",
    "accent_green":  "#2ecc71",
    "accent_orange": "#f39c12",
    "accent_red":    "#e74c3c",
    "accent_purple": "#9b59b6",
    "text_primary":  "#e8eaf6",
    "text_secondary":"#8892b0",
    "border":        "#2a2d3e",
    "hover":         "#252840",
}

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """请求管理员权限重启"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )

def load_config():
    """加载配置文件"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {"packages": [], "ip_profiles": []}

def save_config(config):
    """保存配置文件"""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# ─── 代理配置相关函数 ────────────────────────────────────────────────────────
def get_proxy_settings():
    """读取当前系统代理设置 (注册表 HKCU\\...\\Internet Settings)"""
    result = {"enabled": False, "server": "", "http": "", "https": "",
              "socks": "", "override": ""}
    try:
        out = subprocess.run(
            ["reg", "query",
             "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"],
            capture_output=True, text=True, encoding="gbk", errors="ignore"
        ).stdout
        for line in out.splitlines():
            if "ProxyEnable" in line and "ProxyOverride" not in line:
                if "0x1" in line:
                    result["enabled"] = True
            elif "ProxyServer" in line and "ProxyServer\\" not in line:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    result["server"] = parts[2].strip()
            elif "ProxyOverride" in line:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    result["override"] = parts[2].strip()
        # 解析协议专用代理
        svr = result["server"]
        if svr and "=" in svr:
            for part in svr.split(";"):
                if part.startswith("http="):
                    result["http"] = part[5:]
                elif part.startswith("https="):
                    result["https"] = part[6:]
                elif part.startswith("socks="):
                    result["socks"] = part[6:]
        elif svr:
            result["http"] = result["https"] = svr
    except Exception:
        pass
    return result


def set_system_proxy(http_addr="", http_port="", https_addr="", https_port="",
                     socks_addr="", socks_port="",
                     override="localhost;127.0.0.1;<local>", enable=True):
    """设置 Windows 系统代理（写入注册表并通知系统）
    地址和端口分开传入，内部拼接为 ProxyServer 格式。
    当 HTTP 和 HTTPS 相同时使用单一代理格式(Windows设置界面可正确显示)，
    不同时使用分协议格式。
    """
    try:
        key = "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings"
        if enable and (http_addr or https_addr or socks_addr):
            http_str = f"{http_addr}:{http_port}" if http_addr and http_port else (http_addr or "")
            https_str = f"{https_addr}:{https_port}" if https_addr and https_port else (https_addr or "")
            socks_str = f"{socks_addr}:{socks_port}" if socks_addr and socks_port else (socks_addr or "")

            # 判断 HTTP 和 HTTPS 是否相同
            http_same_as_https = (http_str == https_str) or (not https_addr)

            if http_same_as_https and not socks_addr:
                # 单一代理模式: ProxyServer = "地址:端口" (Windows设置界面友好)
                server_str = http_str
            else:
                # 分协议模式
                parts = []
                if http_str:
                    parts.append(f"http={http_str}")
                if https_str:
                    parts.append(f"https={https_str}")
                if socks_str:
                    parts.append(f"socks={socks_str}")
                server_str = ";".join(parts)

            for cmd in [
                ["reg", "add", key, "/v", "ProxyServer",
                 "/t", "REG_SZ", "/d", server_str, "/f"],
                ["reg", "add", key, "/v", "ProxyOverride",
                 "/t", "REG_SZ", "/d", override, "/f"],
                ["reg", "add", key, "/v", "ProxyEnable",
                 "/t", "REG_DWORD", "/d", "1", "/f"],
            ]:
                subprocess.run(cmd, check=True, capture_output=True)
        else:
            subprocess.run(
                ["reg", "add", key, "/v", "ProxyEnable",
                 "/t", "REG_DWORD", "/d", "0", "/f"],
                check=True, capture_output=True
            )
        # 通知系统代理设置已变更（应用和关闭都需要）
        # 方法1: 通知 WinINet 库
        ctypes.windll.Wininet.InternetSetOptionW(0, 39, None, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
        ctypes.windll.Wininet.InternetSetOptionW(0, 37, None, 0)  # INTERNET_OPTION_PROXY
        # 方法2: 广播 WM_SETTINGCHANGE 通知整个系统（让设置界面也刷新）
        try:
            _env = ctypes.create_unicode_buffer("Internet Settings")
            _lparam = ctypes.cast(_env, ctypes.c_wchar_p).value
            ctypes.windll.user32.SendMessageTimeoutW(
                0xFFFF,  # HWND_BROADCAST
                0x001A,  # WM_SETTINGCHANGE
                0, _lparam,
                0x0002,  # SMTO_ABORTIFHUNG
                5000, ctypes.byref(ctypes.c_uint64(0))
            )
        except Exception:
            pass
        return True, "代理设置已应用"
    except subprocess.CalledProcessError as e:
        return False, f"注册表写入失败: {e}"
    except Exception as e:
        return False, str(e)


def disable_system_proxy():
    """关闭系统代理"""
    return set_system_proxy(enable=False)


def get_network_adapters():
    """获取网络适配器列表"""
    result = subprocess.run(
        ["netsh", "interface", "show", "interface"],
        capture_output=True, text=True, encoding="gbk", errors="ignore"
    )
    adapters = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[0] in ("已启用", "Enabled"):
            name = " ".join(parts[3:])
            adapters.append(name)
    return adapters if adapters else ["以太网", "WLAN"]

def get_current_ip(adapter):
    """获取当前网卡的IP配置"""
    result = subprocess.run(
        ["netsh", "interface", "ip", "show", "config", f"name={adapter}"],
        capture_output=True, text=True, encoding="gbk", errors="ignore"
    )
    info = {"ip": "", "mask": "", "gateway": "", "dns1": "", "dns2": ""}
    lines = result.stdout.splitlines()
    for i, line in enumerate(lines):
        if "IP 地址" in line or "IP Address" in line:
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                info["ip"] = m.group(1)
        elif "子网前缀" in line or "Subnet Prefix" in line:
            m = re.search(r"掩码 (\d+\.\d+\.\d+\.\d+)|mask (\d+\.\d+\.\d+\.\d+)", line, re.I)
            if m:
                info["mask"] = m.group(1) or m.group(2)
        elif "默认网关" in line or "Default Gateway" in line:
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                info["gateway"] = m.group(1)
        elif "DNS 服务器" in line or "DNS Servers" in line:
            m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
            if m:
                info["dns1"] = m.group(1)
            if i + 1 < len(lines):
                m2 = re.search(r"(\d+\.\d+\.\d+\.\d+)", lines[i + 1])
                if m2:
                    info["dns2"] = m2.group(1)
    return info

def set_ip_config(adapter, ip, mask, gateway, dns1, dns2="", use_dhcp=False):
    """设置IP配置"""
    try:
        if use_dhcp:
            subprocess.run(
                ["netsh", "interface", "ip", "set", "address", f"name={adapter}", "dhcp"],
                check=True, capture_output=True
            )
            subprocess.run(
                ["netsh", "interface", "ip", "set", "dns", f"name={adapter}", "dhcp"],
                capture_output=True
            )
        else:
            subprocess.run([
                "netsh", "interface", "ip", "set", "address",
                f"name={adapter}", "static", ip, mask, gateway
            ], check=True, capture_output=True)
            subprocess.run([
                "netsh", "interface", "ip", "set", "dns",
                f"name={adapter}", "static", dns1
            ], check=True, capture_output=True)
            if dns2:
                subprocess.run([
                    "netsh", "interface", "ip", "add", "dns",
                    f"name={adapter}", dns2, "index=2"
                ], capture_output=True)
        return True, "配置成功！"
    except subprocess.CalledProcessError as e:
        return False, f"配置失败: {e}"
    except Exception as e:
        return False, str(e)

# ═══════════════════════════════════════════════════════════════════════════════
#  自定义控件
# ═══════════════════════════════════════════════════════════════════════════════

class StatusDot(ctk.CTkFrame):
    """状态指示点"""
    def __init__(self, parent, color=COLORS["accent_green"], **kwargs):
        super().__init__(parent, width=10, height=10, corner_radius=5,
                         fg_color=color, **kwargs)

class SectionTitle(ctk.CTkFrame):
    """带左边框的区块标题"""
    def __init__(self, parent, text, icon="", **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(1, weight=1)
        # 左侧彩色条
        bar = ctk.CTkFrame(self, width=4, height=28, corner_radius=2,
                           fg_color=COLORS["accent_blue"])
        bar.grid(row=0, column=0, padx=(0, 10), pady=2, sticky="ns")
        # 标题文字
        lbl = ctk.CTkLabel(self, text=f"{icon}  {text}" if icon else text,
                           font=ctk.CTkFont(family=_FONT_FAMILY, size=16, weight="bold"),
                           text_color=COLORS["text_primary"])
        lbl.grid(row=0, column=1, sticky="w")

class LogBox(ctk.CTkTextbox):
    """日志输出框"""
    LEVEL_COLORS = {
        "INFO":    COLORS["text_secondary"],
        "SUCCESS": COLORS["accent_green"],
        "WARNING": COLORS["accent_orange"],
        "ERROR":   COLORS["accent_red"],
    }

    def log(self, msg, level="INFO"):
        self.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        tag = f"[{level}]"
        line = f"{ts}  {tag:<10} {msg}\n"
        self.insert("end", line)
        self.see("end")
        self.configure(state="disabled")

    def clear(self):
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")

# ═══════════════════════════════════════════════════════════════════════════════
#  IP 配置面板
# ═══════════════════════════════════════════════════════════════════════════════

class IPConfigPanel(ctk.CTkFrame):
    def __init__(self, parent, config, log_box, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.config_data = config
        self.log = log_box
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── 左列：手动配置 ──
        left = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        left.grid(row=0, column=0, padx=(0, 8), pady=4, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        SectionTitle(left, "手动配置 IP", "🖥").pack(padx=20, pady=(18, 12), anchor="w")

        # 网卡选择
        adp_frame = ctk.CTkFrame(left, fg_color="transparent")
        adp_frame.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(adp_frame, text="网络适配器", width=90,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]).pack(side="left")
        self.adapter_var = ctk.StringVar()
        self.adapters = get_network_adapters()
        self.adapter_combo = ctk.CTkComboBox(adp_frame, values=self.adapters,
                                             variable=self.adapter_var,
                                             font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                                             command=self._on_adapter_change)
        if self.adapters:
            self.adapter_var.set(self.adapters[0])
        self.adapter_combo.pack(side="left", fill="x", expand=True, padx=(8, 0))

        # IP字段
        fields = [
            ("IP 地址", "ip_entry", "192.168.1.100"),
            ("子网掩码", "mask_entry", "255.255.255.0"),
            ("默认网关", "gw_entry", "192.168.1.1"),
            ("首选 DNS", "dns1_entry", "114.114.114.114"),
            ("备用 DNS", "dns2_entry", "8.8.8.8"),
        ]
        for label, attr, placeholder in fields:
            row = ctk.CTkFrame(left, fg_color="transparent")
            row.pack(fill="x", padx=20, pady=4)
            ctk.CTkLabel(row, text=label, width=90, font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                         text_color=COLORS["text_secondary"]).pack(side="left")
            entry = ctk.CTkEntry(row, placeholder_text=placeholder,
                                 font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=36,
                                 border_color=COLORS["border"])
            entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
            setattr(self, attr, entry)

        # 按钮区
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(12, 8))

        ctk.CTkButton(btn_row, text="📋 读取当前", width=110, height=36,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._read_current).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="✅ 应用配置", width=110, height=36,
                      fg_color=COLORS["accent_blue"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
                      command=self._apply_static).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="🔄 自动获取", width=110, height=36,
                      fg_color=COLORS["accent_green"], hover_color="#27ae60",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._apply_dhcp).pack(side="left")

        # ── 右列：预设配置 ──
        right = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        right.grid(row=0, column=1, padx=(8, 0), pady=4, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(18, 8))
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "预设配置方案", "⚡").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="＋ 添加方案", width=90, height=30,
                      fg_color=COLORS["accent_purple"], hover_color="#8e44ad",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                      command=self._add_profile).grid(row=0, column=1, sticky="e")

        # 方案列表滚动区
        self.profile_scroll = ctk.CTkScrollableFrame(right, fg_color="transparent",
                                                      label_text="")
        self.profile_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.profile_scroll.grid_columnconfigure(0, weight=1)
        self._refresh_profiles()

        # ── 第二行：网络信息 ──
        info_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        info_card.grid(row=1, column=0, columnspan=2, padx=0, pady=(12, 0), sticky="ew")
        info_card.grid_columnconfigure((0, 1, 2, 3), weight=1)

        SectionTitle(info_card, "本机网络信息", "📊").pack(padx=20, pady=(14, 10), anchor="w")

        stats_row = ctk.CTkFrame(info_card, fg_color="transparent")
        stats_row.pack(fill="x", padx=20, pady=(0, 14))
        for i in range(4):
            stats_row.grid_columnconfigure(i, weight=1)

        self.info_labels = {}
        items = [
            ("hostname", "主机名", "💻"),
            ("local_ip", "本机IP", "🌐"),
            ("mac", "MAC地址", "🔗"),
            ("gateway", "网关", "🚀"),
        ]
        for i, (key, title, icon) in enumerate(items):
            card = ctk.CTkFrame(stats_row, fg_color=COLORS["bg_card2"], corner_radius=12)
            card.grid(row=0, column=i, padx=6, pady=4, sticky="ew")
            ctk.CTkLabel(card, text=f"{icon} {title}",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=11), text_color=COLORS["text_secondary"]
                         ).pack(pady=(10, 2))
            lbl = ctk.CTkLabel(card, text="—",
                                font=ctk.CTkFont(family=_FONT_FAMILY, size=14, weight="bold"),
                                text_color=COLORS["text_primary"])
            lbl.pack(pady=(0, 10))
            self.info_labels[key] = lbl

        ctk.CTkButton(info_card, text="🔍 刷新网络信息", width=140, height=34,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._refresh_net_info).pack(pady=(0, 14))

        # 初始化
        self._refresh_net_info()
        self._read_current()

    def _on_adapter_change(self, value):
        self._read_current()

    def _read_current(self):
        adapter = self.adapter_var.get()
        if not adapter:
            return
        info = get_current_ip(adapter)
        for attr, key in [("ip_entry", "ip"), ("mask_entry", "mask"),
                           ("gw_entry", "gateway"), ("dns1_entry", "dns1"),
                           ("dns2_entry", "dns2")]:
            entry = getattr(self, attr)
            entry.delete(0, "end")
            if info.get(key):
                entry.insert(0, info[key])
        self.log.log(f"已读取 [{adapter}] 当前配置", "INFO")

    def _apply_static(self):
        if not is_admin():
            messagebox.showwarning("权限不足", "修改IP地址需要管理员权限！\n请右键以管理员身份运行本程序。")
            return
        adapter = self.adapter_var.get()
        ip    = self.ip_entry.get().strip()
        mask  = self.mask_entry.get().strip()
        gw    = self.gw_entry.get().strip()
        dns1  = self.dns1_entry.get().strip()
        dns2  = self.dns2_entry.get().strip()

        if not all([adapter, ip, mask]):
            messagebox.showwarning("参数缺失", "请填写 IP 地址和子网掩码！")
            return

        self.log.log(f"正在配置 [{adapter}] → {ip} / {mask} / GW:{gw}", "INFO")

        def task():
            ok, msg = set_ip_config(adapter, ip, mask, gw, dns1, dns2)
            level = "SUCCESS" if ok else "ERROR"
            self.log.log(msg, level)
            if ok:
                self.after(100, lambda: messagebox.showinfo("成功", f"IP 配置已应用！\n{ip}"))
            else:
                self.after(100, lambda: messagebox.showerror("失败", msg))

        threading.Thread(target=task, daemon=True).start()

    def _apply_dhcp(self):
        if not is_admin():
            messagebox.showwarning("权限不足", "需要管理员权限！")
            return
        adapter = self.adapter_var.get()
        self.log.log(f"正在设置 [{adapter}] 为 DHCP 自动获取...", "INFO")

        def task():
            ok, msg = set_ip_config(adapter, "", "", "", "", use_dhcp=True)
            level = "SUCCESS" if ok else "ERROR"
            self.log.log(msg, level)
            if ok:
                self.after(100, lambda: messagebox.showinfo("成功", "已切换为自动获取 IP！"))

        threading.Thread(target=task, daemon=True).start()

    def _refresh_profiles(self):
        for w in self.profile_scroll.winfo_children():
            w.destroy()
        profiles = self.config_data.get("ip_profiles", [])
        if not profiles:
            ctk.CTkLabel(self.profile_scroll, text='暂无预设方案，点击上方"添加方案"',
                         text_color=COLORS["text_secondary"],
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=12)).pack(pady=20)
            return
        for i, prof in enumerate(profiles):
            self._make_profile_card(i, prof)

    def _make_profile_card(self, idx, prof):
        card = ctk.CTkFrame(self.profile_scroll, fg_color=COLORS["bg_card2"],
                            corner_radius=12)
        card.pack(fill="x", pady=4)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 4))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(top, text=prof.get("name", "未命名"),
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
                     text_color=COLORS["text_primary"]).grid(row=0, column=0, sticky="w")

        btn_frame = ctk.CTkFrame(top, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        ctk.CTkButton(btn_frame, text="应用", width=52, height=26,
                      fg_color=COLORS["accent_blue"], font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=lambda p=prof: self._apply_profile(p)
                      ).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="删除", width=52, height=26,
                      fg_color=COLORS["accent_red"], hover_color="#c0392b",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=lambda i=idx: self._delete_profile(i)
                      ).pack(side="left", padx=2)

        info = (f"IP: {prof.get('ip','')}  掩码: {prof.get('mask','')}  "
                f"网关: {prof.get('gateway','')}  DNS: {prof.get('dns1','')}")
        ctk.CTkLabel(card, text=info, font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                     text_color=COLORS["text_secondary"]).pack(anchor="w", padx=14, pady=(0, 10))

    def _apply_profile(self, prof):
        for attr, key in [("ip_entry", "ip"), ("mask_entry", "mask"),
                           ("gw_entry", "gateway"), ("dns1_entry", "dns1"),
                           ("dns2_entry", "dns2")]:
            entry = getattr(self, attr)
            entry.delete(0, "end")
            if prof.get(key):
                entry.insert(0, prof[key])
        self.log.log(f"已加载预设方案: {prof.get('name', '')}", "INFO")

    def _delete_profile(self, idx):
        if messagebox.askyesno("确认删除", "确定要删除该预设方案吗？"):
            self.config_data["ip_profiles"].pop(idx)
            save_config(self.config_data)
            self._refresh_profiles()
            self.log.log("已删除预设方案", "WARNING")

    def _add_profile(self):
        dialog = ProfileDialog(self.winfo_toplevel(), self.config_data)
        self.wait_window(dialog)
        self._refresh_profiles()

    def _refresh_net_info(self):
        def task():
            try:
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
            except:
                hostname, local_ip = "N/A", "N/A"

            # 获取MAC地址
            try:
                result = subprocess.run(
                    ["getmac", "/fo", "csv", "/nh"],
                    capture_output=True, text=True, encoding="gbk", errors="ignore"
                )
                mac_line = result.stdout.strip().splitlines()
                mac = mac_line[0].split(",")[0].strip('"') if mac_line else "N/A"
            except:
                mac = "N/A"

            # 获取网关
            try:
                result = subprocess.run(
                    ["ipconfig"], capture_output=True, text=True,
                    encoding="gbk", errors="ignore"
                )
                gw = "N/A"
                for line in result.stdout.splitlines():
                    if "默认网关" in line or "Default Gateway" in line:
                        m = re.search(r"(\d+\.\d+\.\d+\.\d+)", line)
                        if m:
                            gw = m.group(1)
                            break
            except:
                gw = "N/A"

            self.after(0, lambda: self._update_info_labels(hostname, local_ip, mac, gw))

        threading.Thread(target=task, daemon=True).start()

    def _update_info_labels(self, hostname, ip, mac, gw):
        self.info_labels["hostname"].configure(text=hostname)
        self.info_labels["local_ip"].configure(text=ip)
        self.info_labels["mac"].configure(text=mac)
        self.info_labels["gateway"].configure(text=gw)


# ═══════════════════════════════════════════════════════════════════════════════
#  软件安装面板
# ═══════════════════════════════════════════════════════════════════════════════

class InstallPanel(ctk.CTkFrame):
    def __init__(self, parent, config, log_box, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.config_data = config
        self.log = log_box
        self.install_vars = {}
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)

        # ── 顶部工具栏 ──
        toolbar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        toolbar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        toolbar.grid_columnconfigure(2, weight=1)

        SectionTitle(toolbar, "软件安装管理", "📦").grid(
            row=0, column=0, padx=20, pady=14, sticky="w")

        ctk.CTkButton(toolbar, text="＋ 添加软件", width=100, height=34,
                      fg_color=COLORS["accent_purple"], hover_color="#8e44ad",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._add_package).grid(row=0, column=1, padx=8)

        # 搜索框
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search = ctk.CTkEntry(toolbar, textvariable=self.search_var,
                              placeholder_text="🔍  搜索软件...",
                              font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34,
                              border_color=COLORS["border"])
        search.grid(row=0, column=2, padx=(0, 8), sticky="ew")

        # 批量操作
        ctk.CTkButton(toolbar, text="☑ 全选", width=70, height=34,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                      command=self._select_all).grid(row=0, column=3, padx=4)
        ctk.CTkButton(toolbar, text="☐ 全取消", width=80, height=34,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                      command=self._select_none).grid(row=0, column=4, padx=4)
        ctk.CTkButton(toolbar, text="▶ 安装选中", width=100, height=34,
                      fg_color=COLORS["accent_green"], hover_color="#27ae60",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
                      command=self._install_selected).grid(row=0, column=5, padx=(4, 20))

        # ── 软件包网格 ──
        self.pkg_scroll = ctk.CTkScrollableFrame(self, fg_color=COLORS["bg_card"],
                                                  corner_radius=16, label_text="")
        self.pkg_scroll.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        self.grid_rowconfigure(1, weight=1)

        self._refresh_packages()

        # ── 安装进度区 ──
        progress_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        progress_card.grid(row=2, column=0, sticky="ew")
        progress_card.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(progress_card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(14, 6))
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "安装进度", "⚙").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="清空日志", width=80, height=28,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=lambda: self.log.clear()
                      ).grid(row=0, column=1, sticky="e")

        self.progress_bar = ctk.CTkProgressBar(progress_card, height=8,
                                                progress_color=COLORS["accent_green"])
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 6))
        self.progress_bar.set(0)

        self.progress_label = ctk.CTkLabel(progress_card, text="就绪",
                                            font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                                            text_color=COLORS["text_secondary"])
        self.progress_label.pack(anchor="w", padx=20, pady=(0, 14))

    def _refresh_packages(self, filter_text=""):
        for w in self.pkg_scroll.winfo_children():
            w.destroy()
        self.install_vars.clear()

        packages = self.config_data.get("packages", [])
        filtered = [p for p in packages
                    if filter_text.lower() in p.get("name", "").lower()] if filter_text else packages

        if not filtered:
            ctk.CTkLabel(self.pkg_scroll,
                         text='暂无软件包，点击"添加软件"进行配置' if not filter_text else "没有匹配的软件",
                         text_color=COLORS["text_secondary"],
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13)).pack(pady=30)
            return

        # 每行3列
        cols = 3
        self.pkg_scroll.grid_columnconfigure(tuple(range(cols)), weight=1)
        for i, pkg in enumerate(filtered):
            row, col = divmod(i, cols)
            var = ctk.BooleanVar(value=False)
            self.install_vars[pkg.get("name", "")] = var
            self._make_pkg_card(self.pkg_scroll, pkg, var, row, col)

    def _make_pkg_card(self, parent, pkg, var, row, col):
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card2"], corner_radius=14)
        card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)

        # 顶部: 图标 + 复选框
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(14, 4))
        top.grid_columnconfigure(0, weight=1)

        icon_lbl = ctk.CTkLabel(top, text=pkg.get("icon", "📦"),
                                 font=ctk.CTkFont(family=_FONT_FAMILY, size=28))
        icon_lbl.grid(row=0, column=0, sticky="w")

        cb = ctk.CTkCheckBox(top, text="", variable=var, width=24, height=24,
                             checkbox_width=20, checkbox_height=20,
                             fg_color=COLORS["accent_blue"])
        cb.grid(row=0, column=1, sticky="e")

        # 软件名
        ctk.CTkLabel(card, text=pkg.get("name", "未命名"),
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=14, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w", padx=14)

        # 描述
        ctk.CTkLabel(card, text=pkg.get("description", ""),
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=11), text_color=COLORS["text_secondary"],
                     wraplength=180).pack(anchor="w", padx=14, pady=(2, 8))

        # 路径显示
        path_short = str(pkg.get("path", "未设置"))
        if len(path_short) > 30:
            path_short = "..." + path_short[-27:]
        ctk.CTkLabel(card, text=f"📂 {path_short}",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=10), text_color=COLORS["text_secondary"]
                     ).pack(anchor="w", padx=14, pady=(0, 6))

        # 操作按钮
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(0, 12))

        ctk.CTkButton(btn_row, text="立即安装", height=30, font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                      fg_color=COLORS["accent_blue"],
                      command=lambda p=pkg: self._install_one(p)
                      ).pack(side="left", fill="x", expand=True, padx=2)
        ctk.CTkButton(btn_row, text="删除", height=30, width=48,
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                      fg_color=COLORS["accent_red"], hover_color="#c0392b",
                      command=lambda p=pkg: self._delete_package(p)
                      ).pack(side="left", padx=2)

    def _on_search(self, *args):
        self._refresh_packages(self.search_var.get())

    def _select_all(self):
        for v in self.install_vars.values():
            v.set(True)

    def _select_none(self):
        for v in self.install_vars.values():
            v.set(False)

    def _install_one(self, pkg):
        self._do_install([pkg])

    def _install_selected(self):
        selected = [p for p in self.config_data.get("packages", [])
                    if self.install_vars.get(p.get("name", ""), ctk.BooleanVar()).get()]
        if not selected:
            messagebox.showinfo("提示", "请先勾选要安装的软件！")
            return
        self._do_install(selected)

    def _do_install(self, packages):
        total = len(packages)

        def task():
            for i, pkg in enumerate(packages):
                name = pkg.get("name", "未知")
                path = pkg.get("path", "")
                args = pkg.get("args", "")

                self.after(0, lambda n=name, ii=i: self._update_progress(
                    ii / total, f"正在安装 {n}... ({ii+1}/{total})"))
                self.log.log(f"开始安装: {name}", "INFO")

                if not os.path.exists(path):
                    self.log.log(f"❌ 找不到安装包: {path}", "ERROR")
                    continue

                try:
                    cmd = [path] + (args.split() if args else [])
                    proc = subprocess.run(cmd, timeout=300)
                    if proc.returncode == 0:
                        self.log.log(f"✅ {name} 安装成功", "SUCCESS")
                    else:
                        self.log.log(f"⚠ {name} 安装程序退出码: {proc.returncode}", "WARNING")
                except subprocess.TimeoutExpired:
                    self.log.log(f"⏱ {name} 安装超时 (>5分钟)", "WARNING")
                except Exception as e:
                    self.log.log(f"❌ {name} 安装出错: {e}", "ERROR")

            self.after(0, lambda: self._update_progress(1.0, f"完成，共处理 {total} 个软件包"))

        threading.Thread(target=task, daemon=True).start()

    def _update_progress(self, value, text):
        self.progress_bar.set(value)
        self.progress_label.configure(text=text)

    def _add_package(self):
        dialog = PackageDialog(self.winfo_toplevel(), self.config_data)
        self.wait_window(dialog)
        self._refresh_packages()

    def _delete_package(self, pkg):
        name = pkg.get("name", "")
        if messagebox.askyesno("确认删除", f"确定要从列表中删除 {name}？\n（不会删除实际文件）"):
            pkgs = self.config_data.get("packages", [])
            self.config_data["packages"] = [p for p in pkgs if p.get("name") != name]
            save_config(self.config_data)
            self._refresh_packages()
            self.log.log(f"已从列表删除: {name}", "WARNING")


# ═══════════════════════════════════════════════════════════════════════════════
#  网络检测面板
# ═══════════════════════════════════════════════════════════════════════════════

class PingPanel(ctk.CTkFrame):
    def __init__(self, parent, log_box, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.log = log_box
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Ping 工具 ──
        ping_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        ping_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ping_card.grid_columnconfigure(1, weight=1)

        SectionTitle(ping_card, "网络连通性检测", "🔍").grid(
            row=0, column=0, columnspan=4, padx=20, pady=(16, 10), sticky="w")

        ctk.CTkLabel(ping_card, text="目标地址",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).grid(row=1, column=0, padx=(20, 8), pady=8, sticky="w")
        self.ping_entry = ctk.CTkEntry(ping_card, placeholder_text="输入IP或域名，如 8.8.8.8",
                                       font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=36)
        self.ping_entry.grid(row=1, column=1, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(ping_card, text="次数",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).grid(row=1, column=2, padx=8, pady=8)
        self.count_var = ctk.StringVar(value="4")
        ctk.CTkEntry(ping_card, textvariable=self.count_var, width=60,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=36
                     ).grid(row=1, column=3, padx=8, pady=8)

        ctk.CTkButton(ping_card, text="▶ Ping", width=80, height=36,
                      fg_color=COLORS["accent_blue"], font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._do_ping).grid(row=1, column=4, padx=(8, 8), pady=8)
        ctk.CTkButton(ping_card, text="路由追踪", width=90, height=36,
                      fg_color=COLORS["accent_orange"], hover_color="#e67e22",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._do_tracert).grid(row=1, column=5, padx=(0, 20), pady=8)

        # 常用检测目标
        quick_frame = ctk.CTkFrame(ping_card, fg_color="transparent")
        quick_frame.grid(row=2, column=0, columnspan=6, padx=20, pady=(0, 14), sticky="w")
        ctk.CTkLabel(quick_frame, text="快速检测: ",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left", padx=(0, 4))
        for target in ["114.114.114.114", "8.8.8.8", "www.baidu.com", "www.qq.com"]:
            ctk.CTkButton(quick_frame, text=target, width=130, height=26,
                          fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                          font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                          command=lambda t=target: self._quick_ping(t)
                          ).pack(side="left", padx=3)

        # ── 结果输出 ──
        result_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        result_card.grid(row=1, column=0, sticky="nsew")
        result_card.grid_columnconfigure(0, weight=1)
        result_card.grid_rowconfigure(1, weight=1)

        hdr = ctk.CTkFrame(result_card, fg_color="transparent")
        hdr.grid(row=0, column=0, padx=20, pady=(14, 6), sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "检测结果", "📋").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="清空", width=60, height=28,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=self._clear_result).grid(row=0, column=1, sticky="e")

        self.result_box = ctk.CTkTextbox(result_card, font=ctk.CTkFont(family="Consolas", size=12),
                                          fg_color=COLORS["bg_card2"], text_color=COLORS["text_primary"],
                                          state="disabled")
        self.result_box.grid(row=1, column=0, padx=16, pady=(0, 16), sticky="nsew")

        # ── 端口扫描 ──
        port_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        port_card.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        port_card.grid_columnconfigure(1, weight=1)

        SectionTitle(port_card, "端口连通检测", "🔌").grid(
            row=0, column=0, columnspan=5, padx=20, pady=(14, 8), sticky="w")

        ctk.CTkLabel(port_card, text="主机",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).grid(row=1, column=0, padx=(20, 8))
        self.port_host = ctk.CTkEntry(port_card, placeholder_text="192.168.1.1",
                                       font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
        self.port_host.grid(row=1, column=1, padx=8, sticky="ew")

        ctk.CTkLabel(port_card, text="端口",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).grid(row=1, column=2, padx=8)
        self.port_num = ctk.CTkEntry(port_card, placeholder_text="80",
                                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34, width=80)
        self.port_num.grid(row=1, column=3, padx=8)
        ctk.CTkButton(port_card, text="检测", width=70, height=34,
                      fg_color=COLORS["accent_purple"], font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._check_port
                      ).grid(row=1, column=4, padx=(8, 20), pady=10)

    def _append_result(self, text):
        self.result_box.configure(state="normal")
        self.result_box.insert("end", text + "\n")
        self.result_box.see("end")
        self.result_box.configure(state="disabled")

    def _clear_result(self):
        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.configure(state="disabled")

    def _quick_ping(self, target):
        self.ping_entry.delete(0, "end")
        self.ping_entry.insert(0, target)
        self._do_ping()

    def _do_ping(self):
        host = self.ping_entry.get().strip()
        if not host:
            messagebox.showwarning("提示", "请输入目标地址！")
            return
        count = self.count_var.get().strip() or "4"
        self.log.log(f"Ping {host} (x{count})", "INFO")
        self._append_result(f"\n{'='*50}")
        self._append_result(f"  Ping {host}  (发送{count}个包)")
        self._append_result(f"{'='*50}")

        def task():
            result = subprocess.run(
                ["ping", "-n", count, host],
                capture_output=True, text=True, encoding="gbk", errors="ignore"
            )
            self.after(0, lambda: self._append_result(result.stdout))
            level = "SUCCESS" if result.returncode == 0 else "ERROR"
            self.log.log(f"Ping {host} {'成功' if result.returncode==0 else '失败'}", level)

        threading.Thread(target=task, daemon=True).start()

    def _do_tracert(self):
        host = self.ping_entry.get().strip()
        if not host:
            messagebox.showwarning("提示", "请输入目标地址！")
            return
        self.log.log(f"路由追踪: {host}", "INFO")
        self._append_result(f"\n{'='*50}")
        self._append_result(f"  Tracert {host}")
        self._append_result(f"{'='*50}")

        def task():
            result = subprocess.run(
                ["tracert", "-d", "-h", "15", host],
                capture_output=True, text=True, encoding="gbk", errors="ignore",
                timeout=60
            )
            self.after(0, lambda: self._append_result(result.stdout))

        threading.Thread(target=task, daemon=True).start()

    def _check_port(self):
        host = self.port_host.get().strip()
        port_str = self.port_num.get().strip()
        if not host or not port_str:
            messagebox.showwarning("提示", "请填写主机和端口！")
            return
        try:
            port = int(port_str)
        except:
            messagebox.showerror("错误", "端口必须为数字！")
            return

        def task():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((host, port))
                sock.close()
                if result == 0:
                    msg = f"✅ {host}:{port} 端口开放"
                    self.after(0, lambda: self.log.log(msg, "SUCCESS"))
                    self.after(0, lambda: self._append_result(f"\n{msg}"))
                else:
                    msg = f"❌ {host}:{port} 端口关闭或不可达"
                    self.after(0, lambda: self.log.log(msg, "ERROR"))
                    self.after(0, lambda: self._append_result(f"\n{msg}"))
            except Exception as e:
                self.after(0, lambda: self.log.log(f"端口检测失败: {e}", "ERROR"))

        threading.Thread(target=task, daemon=True).start()


# ══════════════════════════════════════════════════════
#  代理配置面板
# ══════════════════════════════════════════════════════

class ProxyPanel(ctk.CTkFrame):
    """系统代理配置面板"""
    def __init__(self, parent, config, log_box, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.config_data = config
        self.log = log_box
        self.same_as_http = ctk.BooleanVar(value=True)
        self._build_ui()
        self._load_current()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── 当前状态卡片 ──
        status_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=16)
        status_card.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        status_card.grid_columnconfigure(1, weight=1)

        SectionTitle(status_card, "当前代理状态", "🔒").grid(
            row=0, column=0, columnspan=3, padx=20, pady=(14, 8), sticky="w")

        self.status_label = ctk.CTkLabel(
            status_card, text="检测中...", font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
            text_color=COLORS["text_secondary"])
        self.status_label.grid(row=1, column=0, padx=20, pady=(0, 4), sticky="w")

        self.addr_label = ctk.CTkLabel(
            status_card, text="—", font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
            text_color=COLORS["text_secondary"])
        self.addr_label.grid(row=2, column=0, padx=20, pady=(0, 14), sticky="w")

        ctk.CTkButton(status_card, text="🔄 刷新状态", width=100, height=32,
                      fg_color=COLORS["bg_card2"], hover_color=COLORS["hover"],
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                      command=self._load_current).grid(row=0, column=2, rowspan=3,
                                                    padx=20, pady=14)

        # ── 主内容区：左列（手动配置）+ 右列（预设方案）──
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # ── 左列：手动配置 ──
        left = ctk.CTkFrame(body, fg_color=COLORS["bg_card"], corner_radius=16)
        left.grid(row=0, column=0, padx=(0, 8), pady=0, sticky="nsew")
        left.grid_columnconfigure(0, weight=1)

        SectionTitle(left, "手动配置代理", "⚙").pack(padx=20, pady=(16, 10), anchor="w")

        # HTTP 代理（地址 + 端口）
        http_row = ctk.CTkFrame(left, fg_color="transparent")
        http_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(http_row, text="HTTP 代理", width=90,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        self.http_addr_entry = ctk.CTkEntry(http_row, placeholder_text="地址 如 192.168.1.100",
                                              font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
        self.http_addr_entry.pack(side="left", fill="x", expand=True, padx=(8, 4))
        ctk.CTkLabel(http_row, text="端口",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"],
                     width=30).pack(side="left")
        self.http_port_entry = ctk.CTkEntry(http_row, placeholder_text="8080",
                                              font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34, width=70)
        self.http_port_entry.pack(side="left")

        # HTTPS 代理（地址 + 端口）
        https_row = ctk.CTkFrame(left, fg_color="transparent")
        https_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(https_row, text="HTTPS 代理", width=90,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        self.https_addr_entry = ctk.CTkEntry(https_row, placeholder_text="留空则同 HTTP",
                                               font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
        self.https_addr_entry.pack(side="left", fill="x", expand=True, padx=(8, 4))
        ctk.CTkLabel(https_row, text="端口",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"],
                     width=30).pack(side="left")
        self.https_port_entry = ctk.CTkEntry(https_row, placeholder_text="8080",
                                               font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34, width=70)
        self.https_port_entry.pack(side="left")

        cb_row = ctk.CTkFrame(left, fg_color="transparent")
        cb_row.pack(fill="x", padx=20, pady=(0, 4))
        ctk.CTkCheckBox(cb_row, text="HTTPS 使用与 HTTP 相同地址和端口", variable=self.same_as_http,
                        font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"],
                        fg_color=COLORS["accent_blue"]
                        ).pack(anchor="w")

        # SOCKS 代理（地址 + 端口）
        socks_row = ctk.CTkFrame(left, fg_color="transparent")
        socks_row.pack(fill="x", padx=20, pady=4)
        ctk.CTkLabel(socks_row, text="SOCKS 代理", width=90,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        self.socks_addr_entry = ctk.CTkEntry(socks_row, placeholder_text="地址 如 127.0.0.1",
                                               font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
        self.socks_addr_entry.pack(side="left", fill="x", expand=True, padx=(8, 4))
        ctk.CTkLabel(socks_row, text="端口",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"],
                     width=30).pack(side="left")
        self.socks_port_entry = ctk.CTkEntry(socks_row, placeholder_text="1080",
                                               font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34, width=70)
        self.socks_port_entry.pack(side="left")

        # 绕过列表
        row4 = ctk.CTkFrame(left, fg_color="transparent")
        row4.pack(fill="x", padx=20, pady=(8, 4))
        ctk.CTkLabel(row4, text="绕过列表", width=90,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        ctk.CTkLabel(row4, text="（分号分隔）",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=11), text_color=COLORS["text_secondary"]
                     ).pack(side="left", padx=(4, 0))

        self.bypass_entry = ctk.CTkEntry(left,
                                         placeholder_text="localhost;127.0.0.1;<local>",
                                         font=ctk.CTkFont(family=_FONT_FAMILY, size=12), height=32)
        self.bypass_entry.pack(fill="x", padx=20, pady=(0, 10))

        # 操作按钮
        btn_row = ctk.CTkFrame(left, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 16))
        ctk.CTkButton(btn_row, text="✅ 应用代理", width=120, height=36,
                      fg_color=COLORS["accent_blue"], hover_color="#3a7de8",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
                      command=self._apply_proxy).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="❌ 关闭代理", width=120, height=36,
                      fg_color=COLORS["accent_red"], hover_color="#c0392b",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                      command=self._disable_proxy).pack(side="left")

        # ── 右列：预设方案 ──
        right = ctk.CTkFrame(body, fg_color=COLORS["bg_card"], corner_radius=16)
        right.grid(row=0, column=1, padx=(8, 0), pady=0, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)

        hdr = ctk.CTkFrame(right, fg_color="transparent")
        hdr.pack(fill="x", padx=14, pady=(14, 8))
        hdr.grid_columnconfigure(0, weight=1)
        SectionTitle(hdr, "预设代理方案", "⚡").grid(row=0, column=0, sticky="w")
        ctk.CTkButton(hdr, text="＋ 添加", width=70, height=28,
                      fg_color=COLORS["accent_purple"], hover_color="#8e44ad",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=self._add_profile).grid(row=0, column=1)

        self.proxy_profile_scroll = ctk.CTkScrollableFrame(
            right, fg_color="transparent", label_text="")
        self.proxy_profile_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        self.proxy_profile_scroll.grid_columnconfigure(0, weight=1)

        self._refresh_proxy_profiles()

    def _load_current(self):
        def task():
            settings = get_proxy_settings()
            enabled = settings.get("enabled", False)
            http = settings.get("http", "")
            https = settings.get("https", "")
            socks = settings.get("socks", "")

            status_text = "✅ 代理已启用" if enabled else "❌ 代理未启用"
            color = COLORS["accent_green"] if enabled else COLORS["text_secondary"]

            addr_parts = []
            if http:
                addr_parts.append(f"HTTP: {http}")
            if https:
                addr_parts.append(f"HTTPS: {https}")
            if socks:
                addr_parts.append(f"SOCKS: {socks}")
            addr_text = "  |  ".join(addr_parts) if addr_parts else "无"

            self.after(0, lambda: [
                self.status_label.configure(text=status_text, text_color=color),
                self.addr_label.configure(text=addr_text)
            ])

        threading.Thread(target=task, daemon=True).start()

    def _apply_proxy(self):
        if not is_admin():
            messagebox.showwarning("权限不足", "配置系统代理需要管理员权限！\n请右键以管理员身份运行本程序。")
            return
        http_addr = self.http_addr_entry.get().strip()
        if not http_addr:
            messagebox.showwarning("提示", "请至少填写 HTTP 代理地址！")
            return
        http_port = self.http_port_entry.get().strip()

        https_addr = self.https_addr_entry.get().strip()
        https_port = self.https_port_entry.get().strip()
        if self.same_as_http.get():
            https_addr = http_addr
            https_port = http_port

        socks_addr = self.socks_addr_entry.get().strip()
        socks_port = self.socks_port_entry.get().strip()
        bypass = self.bypass_entry.get().strip() or "localhost;127.0.0.1;<local>"

        self.log.log(f"应用代理: HTTP={http_addr}:{http_port} HTTPS={https_addr}:{https_port} SOCKS={socks_addr}:{socks_port}", "INFO")

        def task():
            ok, msg = set_system_proxy(http_addr=http_addr, http_port=http_port,
                                        https_addr=https_addr, https_port=https_port,
                                        socks_addr=socks_addr, socks_port=socks_port,
                                        override=bypass, enable=True)
            level = "SUCCESS" if ok else "ERROR"
            self.log.log(msg, level)
            if ok:
                self.after(0, lambda: [messagebox.showinfo("成功", "代理已应用！"),
                                           self._load_current()])
            else:
                self.after(0, lambda: messagebox.showerror("失败", msg))

        threading.Thread(target=task, daemon=True).start()

    def _disable_proxy(self):
        if not is_admin():
            messagebox.showwarning("权限不足", "需要管理员权限！")
            return
        self.log.log("正在关闭系统代理...", "INFO")

        def task():
            ok, msg = disable_system_proxy()
            level = "SUCCESS" if ok else "ERROR"
            self.log.log(msg, level)
            if ok:
                self.after(0, lambda: [messagebox.showinfo("成功", "代理已关闭！"),
                                           self._load_current()])

        threading.Thread(target=task, daemon=True).start()

    def _refresh_proxy_profiles(self):
        for w in self.proxy_profile_scroll.winfo_children():
            w.destroy()
        profiles = self.config_data.get("proxy_profiles", [])
        if not profiles:
            ctk.CTkLabel(self.proxy_profile_scroll,
                         text='暂无预设方案，点击上方"添加"',
                         text_color=COLORS["text_secondary"],
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=12)).pack(pady=20)
            return
        for i, prof in enumerate(profiles):
            self._make_proxy_profile_card(i, prof)

    def _make_proxy_profile_card(self, idx, prof):
        card = ctk.CTkFrame(self.proxy_profile_scroll,
                              fg_color=COLORS["bg_card2"], corner_radius=12)
        card.pack(fill="x", pady=4)
        card.grid_columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, padx=12, pady=(10, 4), sticky="ew")
        top.grid_columnconfigure(0, weight=1)

        name = prof.get("name", "未命名")
        ctk.CTkLabel(top, text=name,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
                     text_color=COLORS["text_primary"]
                     ).grid(row=0, column=0, sticky="w")

        btns = ctk.CTkFrame(top, fg_color="transparent")
        btns.grid(row=0, column=1, sticky="e")
        ctk.CTkButton(btns, text="应用", width=52, height=26,
                      fg_color=COLORS["accent_blue"], font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=lambda p=prof: self._apply_profile(p)
                      ).pack(side="left", padx=2)
        ctk.CTkButton(btns, text="删除", width=52, height=26,
                      fg_color=COLORS["accent_red"], hover_color="#c0392b",
                      font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                      command=lambda i=idx: self._delete_proxy_profile(i)
                      ).pack(side="left", padx=2)

        info_parts = []
        if prof.get("http_addr"):
            info_parts.append(f"HTTP:{prof['http_addr']}:{prof.get('http_port', '')}")
        if prof.get("https_addr"):
            info_parts.append(f"HTTPS:{prof['https_addr']}:{prof.get('https_port', '')}")
        if prof.get("socks_addr"):
            info_parts.append(f"SOCKS:{prof['socks_addr']}:{prof.get('socks_port', '')}")
        info_str = "  ".join(info_parts) if info_parts else "无代理地址"

        ctk.CTkLabel(card, text=info_str,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                     text_color=COLORS["text_secondary"]
                     ).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

    def _apply_profile(self, prof):
        # 清空所有输入框
        for e in [self.http_addr_entry, self.http_port_entry,
                  self.https_addr_entry, self.https_port_entry,
                  self.socks_addr_entry, self.socks_port_entry,
                  self.bypass_entry]:
            e.delete(0, "end")

        if prof.get("http_addr"):
            self.http_addr_entry.insert(0, prof["http_addr"])
        if prof.get("http_port"):
            self.http_port_entry.insert(0, prof["http_port"])
        if prof.get("https_addr"):
            self.https_addr_entry.insert(0, prof["https_addr"])
        if prof.get("https_port"):
            self.https_port_entry.insert(0, prof["https_port"])
        if prof.get("socks_addr"):
            self.socks_addr_entry.insert(0, prof["socks_addr"])
        if prof.get("socks_port"):
            self.socks_port_entry.insert(0, prof["socks_port"])
        if prof.get("bypass"):
            self.bypass_entry.insert(0, prof["bypass"])

        self.log.log(f"已加载代理预设: {prof.get('name', '')}", "INFO")
        self._apply_proxy()

    def _delete_proxy_profile(self, idx):
        if messagebox.askyesno("确认删除", "确定要删除该代理预设方案吗？"):
            self.config_data["proxy_profiles"].pop(idx)
            save_config(self.config_data)
            self._refresh_proxy_profiles()
            self.log.log("已删除代理预设方案", "WARNING")

    def _add_profile(self):
        dialog = ProxyProfileDialog(self.winfo_toplevel(), self.config_data)
        self.wait_window(dialog)
        self._refresh_proxy_profiles()


# ═══════════════════════════════════════════════════════════════════════════════
#  对话框
# ═══════════════════════════════════════════════════════════════════════════════

class BaseDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, width=480, height=420):
        super().__init__(parent)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)
        self.grab_set()
        self.configure(fg_color=COLORS["bg_card"])
        # 居中
        self.update_idletasks()
        pw = parent.winfo_x() + parent.winfo_width() // 2
        ph = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"{width}x{height}+{pw - width//2}+{ph - height//2}")

class ProfileDialog(BaseDialog):
    def __init__(self, parent, config):
        super().__init__(parent, "添加IP预设方案", 460, 440)
        self.config_data = config
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="➕ 添加 IP 预设方案",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(pady=(24, 16))

        fields = [
            ("方案名称", "name", "如: 办公区 A 区"),
            ("IP 地址", "ip", "192.168.1.100"),
            ("子网掩码", "mask", "255.255.255.0"),
            ("默认网关", "gateway", "192.168.1.1"),
            ("首选 DNS", "dns1", "114.114.114.114"),
            ("备用 DNS", "dns2", "8.8.8.8"),
        ]
        self.entries = {}
        for label, key, placeholder in fields:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=30, pady=4)
            ctk.CTkLabel(row, text=label, width=80,
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                         ).pack(side="left")
            e = ctk.CTkEntry(row, placeholder_text=placeholder,
                              font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
            e.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.entries[key] = e

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=18)
        ctk.CTkButton(btn_row, text="取消", width=100, height=36,
                      fg_color=COLORS["bg_card2"], command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="✅ 保存", width=100, height=36,
                      fg_color=COLORS["accent_blue"],
                      font=ctk.CTkFont(weight="bold"),
                      command=self._save).pack(side="left", padx=8)

    def _save(self):
        data = {k: e.get().strip() for k, e in self.entries.items()}
        if not data["name"] or not data["ip"]:
            messagebox.showwarning("提示", "方案名称和IP地址不能为空！", parent=self)
            return
        self.config_data.setdefault("ip_profiles", []).append(data)
        save_config(self.config_data)
        self.destroy()

class PackageDialog(BaseDialog):
    def __init__(self, parent, config):
        super().__init__(parent, "添加软件包", 500, 460)
        self.config_data = config
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="📦 添加软件包",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(pady=(24, 16))

        fields = [
            ("软件名称", "name", "Chrome 浏览器"),
            ("图标 Emoji", "icon", "🌐"),
            ("描述", "description", "软件简短描述"),
            ("启动参数", "args", "/silent /install"),
        ]
        self.entries = {}
        for label, key, placeholder in fields:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=30, pady=5)
            ctk.CTkLabel(row, text=label, width=80,
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                         ).pack(side="left")
            e = ctk.CTkEntry(row, placeholder_text=placeholder,
                              font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
            e.pack(side="left", fill="x", expand=True, padx=(8, 0))
            self.entries[key] = e

        # 安装包路径选择
        path_row = ctk.CTkFrame(self, fg_color="transparent")
        path_row.pack(fill="x", padx=30, pady=5)
        ctk.CTkLabel(path_row, text="安装包路径", width=80,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        self.path_entry = ctk.CTkEntry(path_row, placeholder_text="C:\\Installers\\setup.exe",
                                        font=ctk.CTkFont(family=_FONT_FAMILY, size=12), height=34)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        ctk.CTkButton(path_row, text="📂", width=36, height=34,
                      fg_color=COLORS["bg_card2"],
                      command=self._browse).pack(side="left", padx=(4, 0))

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=18)
        ctk.CTkButton(btn_row, text="取消", width=100, height=36,
                      fg_color=COLORS["bg_card2"], command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="✅ 保存", width=100, height=36,
                      fg_color=COLORS["accent_blue"],
                      font=ctk.CTkFont(weight="bold"),
                      command=self._save).pack(side="left", padx=8)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="选择安装包",
            filetypes=[("安装程序", "*.exe *.msi"), ("所有文件", "*.*")]
        )
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)

    def _save(self):
        data = {k: e.get().strip() for k, e in self.entries.items()}
        data["path"] = self.path_entry.get().strip()
        if not data["name"] or not data["path"]:
            messagebox.showwarning("提示", "软件名称和安装包路径不能为空！", parent=self)
            return
        self.config_data.setdefault("packages", []).append(data)
        save_config(self.config_data)
        self.destroy()

class ProxyProfileDialog(BaseDialog):
    """添加代理预设方案对话框"""
    def __init__(self, parent, config):
        super().__init__(parent, "添加代理预设方案", 520, 440)
        self.config_data = config
        self._build()

    def _build(self):
        ctk.CTkLabel(self, text="➕ 添加代理预设方案",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=16, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(pady=(24, 16))

        self.entries = {}

        # 方案名称
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=30, pady=4)
        ctk.CTkLabel(row, text="方案名称", width=80,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
                     text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(row, placeholder_text="如: 公司代理",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=34)
        e.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.entries["name"] = e

        # HTTP 代理（地址 + 端口）
        ctk.CTkLabel(self, text="HTTP 代理", font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                     text_color=COLORS["accent_blue"],
                     anchor="w").pack(fill="x", padx=34, pady=(10, 2))
        http_row = ctk.CTkFrame(self, fg_color="transparent")
        http_row.pack(fill="x", padx=30, pady=2)
        ctk.CTkLabel(http_row, text="地址", width=40,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(http_row, placeholder_text="192.168.1.100",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=32)
        e.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self.entries["http_addr"] = e
        ctk.CTkLabel(http_row, text="端口", width=30,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(http_row, placeholder_text="8080",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=32, width=70)
        e.pack(side="left")
        self.entries["http_port"] = e

        # HTTPS 代理（地址 + 端口）
        ctk.CTkLabel(self, text="HTTPS 代理", font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                     text_color=COLORS["accent_blue"],
                     anchor="w").pack(fill="x", padx=34, pady=(8, 2))
        https_row = ctk.CTkFrame(self, fg_color="transparent")
        https_row.pack(fill="x", padx=30, pady=2)
        ctk.CTkLabel(https_row, text="地址", width=40,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(https_row, placeholder_text="留空则同 HTTP",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=32)
        e.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self.entries["https_addr"] = e
        ctk.CTkLabel(https_row, text="端口", width=30,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(https_row, placeholder_text="8080",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=32, width=70)
        e.pack(side="left")
        self.entries["https_port"] = e

        # SOCKS 代理（地址 + 端口）
        ctk.CTkLabel(self, text="SOCKS 代理", font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                     text_color=COLORS["accent_blue"],
                     anchor="w").pack(fill="x", padx=34, pady=(8, 2))
        socks_row = ctk.CTkFrame(self, fg_color="transparent")
        socks_row.pack(fill="x", padx=30, pady=2)
        ctk.CTkLabel(socks_row, text="地址", width=40,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(socks_row, placeholder_text="127.0.0.1",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=32)
        e.pack(side="left", fill="x", expand=True, padx=(4, 6))
        self.entries["socks_addr"] = e
        ctk.CTkLabel(socks_row, text="端口", width=30,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(socks_row, placeholder_text="1080",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=13), height=32, width=70)
        e.pack(side="left")
        self.entries["socks_port"] = e

        # 绕过列表
        bypass_row = ctk.CTkFrame(self, fg_color="transparent")
        bypass_row.pack(fill="x", padx=30, pady=(10, 2))
        ctk.CTkLabel(bypass_row, text="绕过列表", width=80,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                     text_color=COLORS["text_secondary"]
                     ).pack(side="left")
        e = ctk.CTkEntry(bypass_row, placeholder_text="localhost;127.0.0.1;<local>",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=12), height=30)
        e.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.entries["bypass"] = e

        btn_row = ctk.CTkFrame(self, fg_color="transparent")
        btn_row.pack(pady=14)
        ctk.CTkButton(btn_row, text="取消", width=100, height=36,
                      fg_color=COLORS["bg_card2"],
                      command=self.destroy).pack(side="left", padx=8)
        ctk.CTkButton(btn_row, text="✅ 保存", width=100, height=36,
                      fg_color=COLORS["accent_blue"],
                      font=ctk.CTkFont(weight="bold"),
                      command=self._save).pack(side="left", padx=8)

    def _save(self):
        data = {k: e.get().strip() for k, e in self.entries.items()}
        if not data["name"]:
            messagebox.showwarning("提示", "方案名称不能为空！", parent=self)
            return
        # 清理空的端口字段
        for k in ("http_port", "https_port", "socks_port"):
            if not data.get(k):
                data.pop(k, None)
        self.config_data.setdefault("proxy_profiles", []).append(data)
        save_config(self.config_data)
        self.destroy()


class ToolboxPanel(ctk.CTkFrame):
    """网络修复工具箱"""
    def __init__(self, parent, log_box, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.log = log_box
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── 工具卡片定义 ──
        tools = [
            {
                "title": "刷新 DNS 缓存",
                "desc": "清除本地 DNS 解析缓存\n解决网站打不开、域名解析错误",
                "icon": "🔄",
                "color": COLORS["accent_blue"],
                "cmd": self._flush_dns,
                "admin": False,
            },
            {
                "title": "重置网络协议栈",
                "desc": "重置 Winsock + TCP/IP 协议栈\n解决连不上网、网络图标异常",
                "icon": "🔧",
                "color": COLORS["accent_orange"],
                "cmd": self._reset_winsock,
                "admin": True,
            },
            {
                "title": "释放/续约 IP",
                "desc": "释放当前 DHCP 租约并重新获取\n解决获取不到 IP 地址的问题",
                "icon": "📡",
                "color": COLORS["accent_green"],
                "cmd": self._renew_ip,
                "admin": True,
            },
            {
                "title": "清除 ARP 缓存",
                "desc": "清除 ARP 解析表\n解决局域网通信异常",
                "icon": "🧹",
                "color": COLORS["accent_purple"],
                "cmd": self._flush_arp,
                "admin": True,
            },
            {
                "title": "重置网络适配器",
                "desc": "禁用并重新启用所有网络适配器\n相当于重启网卡",
                "icon": "🔌",
                "color": COLORS["accent_red"],
                "cmd": self._reset_adapter,
                "admin": True,
            },
            {
                "title": "网络诊断一键修复",
                "desc": "依次执行：DNS刷新 + ARP清除 + IP续约 + Winsock重置\n适合一键修复大部分网络问题",
                "icon": "🛠",
                "color": "#e67e22",
                "cmd": self._repair_all,
                "admin": True,
            },
        ]

        for i, tool in enumerate(tools):
            row = i // 2
            col = i % 2
            self._make_tool_card(tool, row, col)

    def _make_tool_card(self, tool, row, col):
        card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"],
                            corner_radius=16, cursor="hand2")
        card.grid(row=row, column=col, padx=(0 if col == 0 else 8, 0 if col == 1 else 8),
                  pady=(0 if row == 0 else 10, 0), sticky="nsew")

        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=0)

        # 头部: 图标 + 标题 + 管理员标记
        hdr = ctk.CTkFrame(card, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 4))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text=f"{tool['icon']}  {tool['title']}",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=15, weight="bold"),
                     text_color=COLORS["text_primary"]).grid(row=0, column=0, sticky="w")
        if tool["admin"]:
            ctk.CTkLabel(hdr, text="需管理员",
                         font=ctk.CTkFont(family=_FONT_FAMILY, size=10),
                         text_color=COLORS["accent_orange"]).grid(row=0, column=1, sticky="e")

        # 描述
        desc_text = tool["desc"].replace("\n", " | ")
        ctk.CTkLabel(card, text=desc_text,
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
                     text_color=COLORS["text_secondary"],
                     wraplength=380, justify="left"
                     ).pack(padx=20, pady=(2, 12), anchor="w")

        # 按钮
        btn = ctk.CTkButton(card, text=f"{tool['icon']}  执行",
                            width=100, height=34,
                            fg_color=tool["color"],
                            hover_color=self._darken(tool["color"]),
                            font=ctk.CTkFont(family=_FONT_FAMILY, size=12, weight="bold"),
                            command=tool["cmd"])
        btn.pack(padx=20, pady=(0, 16), anchor="e")

    @staticmethod
    def _darken(hex_color, factor=0.8):
        """将颜色变暗"""
        hex_color = hex_color.lstrip("#")
        r = int(int(hex_color[0:2], 16) * factor)
        g = int(int(hex_color[2:4], 16) * factor)
        b = int(int(hex_color[4:6], 16) * factor)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _check_admin(self):
        if not is_admin():
            messagebox.showwarning("权限不足",
                                   "此操作需要管理员权限！\n请右键以管理员身份运行本程序。")
            return False
        return True

    def _flush_dns(self):
        """刷新 DNS 缓存"""
        self.log.log("正在刷新 DNS 缓存...", "INFO")
        def task():
            r = subprocess.run("ipconfig /flushdns", capture_output=True, text=True, shell=True)
            for line in r.stdout.splitlines():
                line = line.strip()
                if line:
                    self.log.log(line, "SUCCESS" if "成功" in line else "INFO")
            if r.returncode == 0:
                self.after(0, lambda: messagebox.showinfo("完成", "DNS 缓存已刷新！"))
            else:
                self.after(0, lambda: messagebox.showerror("失败", r.stderr or "操作失败"))
        threading.Thread(target=task, daemon=True).start()

    def _reset_winsock(self):
        """重置 Winsock"""
        if not self._check_admin():
            return
        if not messagebox.askyesno("确认", "重置 Winsock 需要重启计算机才能生效。\n\n确定要继续吗？"):
            return
        self.log.log("正在重置 Winsock 协议栈...", "WARNING")
        def task():
            cmds = [
                ("netsh winsock reset", "Winsock 重置"),
                ("netsh int ip reset", "TCP/IP 重置"),
            ]
            for cmd, label in cmds:
                r = subprocess.run(cmd, capture_output=True, text=True, shell=True)
                self.log.log(f"[{label}] 执行完毕", "INFO")
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if line:
                        self.log.log(line, "INFO")
            self.log.log("Winsock 和 TCP/IP 已重置，建议重启计算机", "SUCCESS")
            self.after(0, lambda: messagebox.showinfo("完成",
                "Winsock 和 TCP/IP 协议栈已重置！\n\n请重启计算机使更改生效。"))
        threading.Thread(target=task, daemon=True).start()

    def _renew_ip(self):
        """释放/续约 DHCP IP"""
        if not self._check_admin():
            return
        self.log.log("正在释放 IP 地址...", "INFO")
        def task():
            # 释放
            r1 = subprocess.run("ipconfig /release", capture_output=True, text=True, shell=True)
            self.log.log("IP 地址已释放", "INFO")
            # 续约
            r2 = subprocess.run("ipconfig /renew", capture_output=True, text=True, shell=True)
            self.log.log("正在重新获取 IP...", "INFO")
            for line in r2.stdout.splitlines():
                line = line.strip()
                if "IPv4" in line or "子网掩码" in line or "默认网关" in line:
                    self.log.log(line, "SUCCESS")
            self.log.log("IP 地址续约完成", "SUCCESS")
            self.after(0, lambda: messagebox.showinfo("完成", "IP 地址已释放并重新获取！"))
        threading.Thread(target=task, daemon=True).start()

    def _flush_arp(self):
        """清除 ARP 缓存"""
        if not self._check_admin():
            return
        self.log.log("正在清除 ARP 缓存...", "INFO")
        def task():
            r = subprocess.run("arp -d *", capture_output=True, text=True, shell=True)
            if r.returncode == 0:
                self.log.log("ARP 缓存已清除", "SUCCESS")
                self.after(0, lambda: messagebox.showinfo("完成", "ARP 缓存已清除！"))
            else:
                self.log.log(f"ARP 清除失败: {r.stderr}", "ERROR")
                self.after(0, lambda: messagebox.showerror("失败", "ARP 缓存清除失败"))

            # 显示当前 ARP 表
            r2 = subprocess.run("arp -a", capture_output=True, text=True, shell=True)
            self.log.log("当前 ARP 表:", "INFO")
            for line in r2.stdout.splitlines():
                line = line.strip()
                if line:
                    self.log.log(line, "INFO")
        threading.Thread(target=task, daemon=True).start()

    def _reset_adapter(self):
        """重置网络适配器"""
        if not self._check_admin():
            return
        self.log.log("正在获取网络适配器列表...", "INFO")
        def task():
            adapters = get_network_adapters()
            if not adapters:
                self.log.log("未找到网络适配器", "ERROR")
                self.after(0, lambda: messagebox.showerror("失败", "未找到可用的网络适配器！"))
                return

            for adapter in adapters:
                self.log.log(f"正在禁用适配器: {adapter}...", "WARNING")
                subprocess.run(f'netsh interface set interface "{adapter}" admin=disable',
                               capture_output=True, text=True, shell=True)
                self.log.log(f"已禁用: {adapter}", "INFO")

            import time
            time.sleep(2)

            for adapter in adapters:
                self.log.log(f"正在启用适配器: {adapter}...", "INFO")
                subprocess.run(f'netsh interface set interface "{adapter}" admin=enable',
                               capture_output=True, text=True, shell=True)
                self.log.log(f"已启用: {adapter}", "SUCCESS")

            self.log.log("所有网络适配器已重置", "SUCCESS")
            self.after(0, lambda: messagebox.showinfo("完成",
                f"已重置 {len(adapters)} 个网络适配器！\n\n网络可能需要几秒钟恢复。"))
        threading.Thread(target=task, daemon=True).start()

    def _repair_all(self):
        """一键网络诊断修复"""
        if not self._check_admin():
            return
        if not messagebox.askyesno("确认",
            "将依次执行以下修复操作：\n\n"
            "1. 刷新 DNS 缓存\n"
            "2. 清除 ARP 缓存\n"
            "3. 释放并续约 IP 地址\n"
            "4. 重置 Winsock + TCP/IP 协议栈\n\n"
            "重置协议栈需要重启计算机。\n\n确定要继续吗？"):
            return

        self.log.log("=" * 40, "WARNING")
        self.log.log("开始一键网络修复...", "WARNING")
        self.log.log("=" * 40, "WARNING")

        def task():
            import time

            # 步骤1: DNS
            self.log.log("[1/4] 刷新 DNS 缓存...", "INFO")
            r = subprocess.run("ipconfig /flushdns", capture_output=True, text=True, shell=True)
            self.log.log("DNS 缓存已刷新 ✓", "SUCCESS")
            time.sleep(1)

            # 步骤2: ARP
            self.log.log("[2/4] 清除 ARP 缓存...", "INFO")
            subprocess.run("arp -d *", capture_output=True, text=True, shell=True)
            self.log.log("ARP 缓存已清除 ✓", "SUCCESS")
            time.sleep(1)

            # 步骤3: IP续约
            self.log.log("[3/4] 释放并续约 IP 地址...", "INFO")
            subprocess.run("ipconfig /release", capture_output=True, text=True, shell=True)
            time.sleep(1)
            subprocess.run("ipconfig /renew", capture_output=True, text=True, shell=True)
            self.log.log("IP 地址已续约 ✓", "SUCCESS")
            time.sleep(1)

            # 步骤4: Winsock 重置
            self.log.log("[4/4] 重置 Winsock + TCP/IP...", "WARNING")
            subprocess.run("netsh winsock reset", capture_output=True, text=True, shell=True)
            subprocess.run("netsh int ip reset", capture_output=True, text=True, shell=True)
            self.log.log("协议栈已重置 ✓", "SUCCESS")

            self.log.log("=" * 40, "WARNING")
            self.log.log("一键修复完成！建议重启计算机", "SUCCESS")
            self.log.log("=" * 40, "WARNING")

            self.after(0, lambda: messagebox.showinfo("修复完成",
                "所有修复操作已执行完毕！\n\n"
                "建议立即重启计算机，使所有更改生效。"))
        threading.Thread(target=task, daemon=True).start()


# ═══════════════════════════════════════════════════════════════════════════════
#  主窗口
# ═══════════════════════════════════════════════════════════════════════════════

class NetAdminApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config_data = load_config()

        # ── 全局设置默认字体（解决跨机器字体不一致问题） ──
        self._setup_fonts()

        # ── 窗口设置 ──
        self.title("NetAdmin Pro  |  网络管理员工具")
        self.geometry("1280x820")
        self.minsize(1100, 700)
        self.configure(fg_color=COLORS["bg_dark"])

        # 设置图标（如果存在）
        icon_path = BASE_DIR / "icon.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except:
                pass

        self._build_ui()
        self._check_admin()

    def _setup_fonts(self):
        """全局设置字体，确保跨机器中文显示正常"""
        import tkinter.font as tkfont
        _families = ("Microsoft YaHei", "微软雅黑", "SimHei", "PingFang SC",
                      "Segoe UI", "Noto Sans CJK SC",
                      "WenQuanYi Micro Hei", "Arial")
        _available = tkfont.families()
        _chosen = "Arial"
        for _f in _families:
            if _f in _available:
                _chosen = _f
                break
        # 更新模块级字体常量
        global _FONT_FAMILY
        _FONT_FAMILY = _chosen

    def _check_admin(self):
        if not is_admin():
            self.status_dot.configure(fg_color=COLORS["accent_orange"])
            self.admin_label.configure(text="⚠ 非管理员模式 (IP配置功能受限)",
                                        text_color=COLORS["accent_orange"])
        else:
            self.status_dot.configure(fg_color=COLORS["accent_green"])
            self.admin_label.configure(text="✅ 管理员模式",
                                        text_color=COLORS["accent_green"])

    def _build_ui(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ══ 顶部状态栏 ══
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_card"],
                               corner_radius=0, height=58)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(2, weight=1)
        header.grid_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(header, fg_color="transparent")
        logo_frame.grid(row=0, column=0, padx=(20, 0), pady=10, sticky="w")
        ctk.CTkLabel(logo_frame, text="🛡",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=26)).pack(side="left", padx=(0, 8))
        title_frame = ctk.CTkFrame(logo_frame, fg_color="transparent")
        title_frame.pack(side="left")
        ctk.CTkLabel(title_frame, text="NetAdmin Pro",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=18, weight="bold"),
                     text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(title_frame, text="网络管理员工具",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=11), text_color=COLORS["text_secondary"]
                     ).pack(anchor="w")

        # 分隔
        ctk.CTkFrame(header, width=1, height=36, fg_color=COLORS["border"]
                     ).grid(row=0, column=1, padx=20, pady=10)

        # 权限状态
        status_frame = ctk.CTkFrame(header, fg_color="transparent")
        status_frame.grid(row=0, column=2, padx=0, pady=10, sticky="w")
        self.status_dot = StatusDot(status_frame)
        self.status_dot.pack(side="left", padx=(0, 6))
        self.admin_label = ctk.CTkLabel(status_frame, text="检测中...",
                                         font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                                         text_color=COLORS["text_secondary"])
        self.admin_label.pack(side="left")

        # 右侧按钮
        right_btns = ctk.CTkFrame(header, fg_color="transparent")
        right_btns.grid(row=0, column=3, padx=(0, 20), pady=10, sticky="e")

        if not is_admin():
            ctk.CTkButton(right_btns, text="🔓 提升权限", width=100, height=32,
                          fg_color=COLORS["accent_orange"], hover_color="#d68910",
                          font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                          command=lambda: [run_as_admin(), self.destroy()]
                          ).pack(side="left", padx=4)

        ctk.CTkLabel(right_btns, text=datetime.now().strftime("%Y-%m-%d"),
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=12), text_color=COLORS["text_secondary"]
                     ).pack(side="left", padx=10)

        # ══ 主体区域: 左侧导航 + 右侧内容 ══
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        main.grid_columnconfigure(1, weight=1)
        main.grid_rowconfigure(0, weight=1)

        # ── 左侧导航栏 ──
        nav = ctk.CTkFrame(main, fg_color=COLORS["bg_card"],
                           corner_radius=0, width=200)
        nav.grid(row=0, column=0, sticky="nsew")
        nav.grid_propagate(False)
        nav.grid_rowconfigure(10, weight=1)

        ctk.CTkLabel(nav, text="功能菜单",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=11, weight="bold"),
                     text_color=COLORS["text_secondary"]).pack(pady=(24, 8), padx=20, anchor="w")

        self.nav_buttons = []
        nav_items = [
            ("🖥  IP 配置", 0),
            ("📦  软件安装", 1),
            ("🔍  网络检测", 2),
            ("🔒  代理配置", 3),
            ("🛠  网络修复", 4),
            ("🖥  硬件信息", 5),
        ]
        for label, idx in nav_items:
            btn = ctk.CTkButton(nav, text=label, anchor="w", height=44, width=180,
                                font=ctk.CTkFont(family=_FONT_FAMILY, size=14),
                                fg_color="transparent",
                                text_color=COLORS["text_secondary"],
                                hover_color=COLORS["hover"],
                                command=lambda i=idx: self._switch_tab(i))
            btn.pack(padx=10, pady=3)
            self.nav_buttons.append(btn)

        # 底部版本信息
        ctk.CTkLabel(nav, text="v1.0.0  NetAdmin Pro",
                     font=ctk.CTkFont(family=_FONT_FAMILY, size=10), text_color=COLORS["border"]
                     ).pack(side="bottom", pady=16)

        # ── 右侧内容区 ──
        content = ctk.CTkFrame(main, fg_color=COLORS["bg_dark"], corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        # 全局日志框（底部）
        self.log_box = LogBox(content, height=130, state="disabled",
                              font=ctk.CTkFont(family="Consolas", size=11),
                              fg_color=COLORS["bg_card"],
                              text_color=COLORS["text_secondary"],
                              border_width=0)
        self.log_box.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))

        # 页面容器
        self.page_frame = ctk.CTkFrame(content, fg_color="transparent")
        self.page_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        self.page_frame.grid_columnconfigure(0, weight=1)
        self.page_frame.grid_rowconfigure(0, weight=1)

        # 初始化六个面板
        self.panels = [
            IPConfigPanel(self.page_frame, self.config_data, self.log_box),
            InstallPanel(self.page_frame, self.config_data, self.log_box),
            PingPanel(self.page_frame, self.log_box),
            ProxyPanel(self.page_frame, self.config_data, self.log_box),
            ToolboxPanel(self.page_frame, self.log_box),
            HardwarePanel(self.page_frame, self.log_box),
        ]
        for p in self.panels:
            p.grid(row=0, column=0, sticky="nsew")

        # 默认显示第一个
        self._switch_tab(0)

        # 欢迎日志
        self.log_box.log("NetAdmin Pro 已启动，欢迎使用！", "SUCCESS")
        if not is_admin():
            self.log_box.log("当前非管理员模式，IP配置功能需要管理员权限", "WARNING")

    def _switch_tab(self, idx):
        for i, (btn, panel) in enumerate(zip(self.nav_buttons, self.panels)):
            if i == idx:
                btn.configure(fg_color=COLORS["accent_blue"],
                               text_color=COLORS["text_primary"])
                panel.tkraise()
            else:
                btn.configure(fg_color="transparent",
                               text_color=COLORS["text_secondary"])


# ═══════════════════════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = NetAdminApp()
    app.mainloop()
