#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HardwarePanel - 硬件信息检测面板 (类似图吧工具箱)
"""

import subprocess
import threading
import tkinter as tk
import customtkinter as ctk
import platform as _platform

# 字体常量（与 net_admin.py 保持一致）
_sys = _platform.system()
if _sys == "Windows":
    _FONT_FAMILY = "Microsoft YaHei"
elif _sys == "Darwin":
    _FONT_FAMILY = "PingFang SC"
else:
    _FONT_FAMILY = "Noto Sans CJK SC"

# 颜色常量（与 net_admin.py 保持一致）
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


class HardwarePanel(ctk.CTkFrame):
    """硬件信息检测面板（类似图吧工具箱）"""

    def __init__(self, parent, log_box, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.log = log_box
        self.hw_cache = {}
        self._build_ui()
        # 延迟加载，避免启动时卡顿
        self.after(300, self._load_info)

    # ───────────────────────────────────────────────
    #  UI 构建
    # ───────────────────────────────────────────────

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 顶部标题栏
        hdr = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            hdr, text="🖥  硬件信息检测",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=18, weight="bold"),
            text_color=COLORS["text_primary"],
        ).grid(row=0, column=0, padx=20, pady=14, sticky="w")

        ctk.CTkButton(
            hdr, text="🔄  刷新检测", width=130, height=36,
            font=ctk.CTkFont(family=_FONT_FAMILY, size=13, weight="bold"),
            fg_color=COLORS["accent_purple"],
            hover_color="#7d3cbb",
            command=self._load_info,
        ).grid(row=0, column=1, padx=20, pady=10, sticky="e")

        # 滚动区域
        self._init_scroll_area()

    def _init_scroll_area(self):
        """初始化可滚动区域"""
        self.canvas = tk.Canvas(
            self, bg=COLORS["bg_dark"],
            highlightthickness=0, relief="flat",
        )
        self.vbar = ctk.CTkScrollbar(
            self, orientation="vertical", command=self.canvas.yview,
        )
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.canvas.grid(row=1, column=0, sticky="nsew")
        self.vbar.grid(  row=1, column=1, sticky="ns")

        self.inner = ctk.CTkFrame(self.canvas, fg_color="transparent")
        self.win_id = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw",
        )

        # 画布宽度随窗口自适应
        def _on_canvas_configure(e):
            self.canvas.itemconfig(self.win_id, width=e.width)
            self._update_scroll_region()

        self.canvas.bind("<Configure>", _on_canvas_configure)
        self.inner.bind("<Configure>", lambda _: self._update_scroll_region())
        # 鼠标滚轮滚动
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.inner.grid_columnconfigure(0, weight=1)

    def _update_scroll_region(self):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ───────────────────────────────────────────────
    #  后台数据采集
    # ───────────────────────────────────────────────

    def _load_info(self):
        """启动后台硬件信息采集"""
        self.log.log("正在检测硬件信息...", "INFO")
        for w in self.inner.winfo_children():
            w.destroy()
        self._show_placeholder()
        threading.Thread(target=self._collect_all, daemon=True).start()

    def _show_placeholder(self):
        self._ph = ctk.CTkLabel(
            self.inner,
            text="⏳  正在检测硬件信息，请稍候...\n\n"
                 "将读取  CPU / GPU / 内存 / 硬盘 / 主板 信息",
            font=ctk.CTkFont(family=_FONT_FAMILY, size=13),
            text_color=COLORS["text_secondary"],
        )
        self._ph.grid(row=0, column=0, pady=60)

    def _collect_all(self):
        data = {
            "cpu":   self._get_cpu(),
            "gpu":   self._get_gpu(),
            "ram":   self._get_ram(),
            "disk":  self._get_disk(),
            "board": self._get_board(),
            "os":    self._get_os(),
        }
        self.hw_cache = data
        self.after(0, lambda: self._render(data))
        self.log.log("硬件信息检测完成", "SUCCESS")

    # ───────────────────────────────────────────────
    #  数据采集方法
    # ───────────────────────────────────────────────

    @staticmethod
    def _run_cmd(cmd, timeout=12):
        """运行命令，返回 stdout 行列表（GBK 编码）"""
        try:
            r = subprocess.run(
                cmd, shell=True, capture_output=True,
                encoding="gbk", errors="ignore", timeout=timeout,
            )
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except Exception:
            return []

    @staticmethod
    def _run_ps(ps_cmd, timeout=12):
        """直接调用 PowerShell，避免引号嵌套问题"""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True, encoding="gbk",
                errors="ignore", timeout=timeout,
            )
            return [l.strip() for l in r.stdout.splitlines() if l.strip()]
        except Exception:
            return []

    def _get_cpu(self):
        info = {"name": "N/A", "cores": "?", "threads": "?",
                "freq": "N/A", "usage": "N/A"}
        lines = HardwarePanel._run_cmd(
            "wmic cpu get Name,NumberOfCores,"
            "NumberOfLogicalProcessors,MaxClockSpeed /value"
        )
        for ln in lines:
            if "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            v = v.strip()
            if   k == "Name":                       info["name"]    = v
            elif k == "NumberOfCores":              info["cores"]   = v
            elif k == "NumberOfLogicalProcessors":  info["threads"] = v
            elif k == "MaxClockSpeed":
                try:
                    info["freq"] = f"{int(v) / 1000:.2f} GHz"
                except Exception:
                    pass
        # CPU 使用率（3 秒平均）
        ps = (
            "Get-Counter '\\Processor(_Total)\\% Processor Time' "
            "-MaxSamples 3 "
            "| Select-Object -ExpandProperty CounterSamples "
            "| Select-Object -ExpandProperty CookedValue"
        )
        lines2 = HardwarePanel._run_cmd(
            f'powershell -NoProfile -Command "{ps}"', timeout=15)
        vals = []
        for l in lines2:
            try:
                vals.append(float(l.strip()))
            except Exception:
                pass
        if vals:
            info["usage"] = f"{sum(vals) / len(vals):.1f}%"
        return info

    def _get_gpu(self):
        gpus = []
        lines = HardwarePanel._run_cmd(
            "wmic path Win32_VideoController get "
            "Name,AdapterRAM,DriverVersion /value"
        )
        cur = {}
        for ln in lines:
            if "=" not in ln:
                if cur:
                    gpus.append(cur)
                    cur = {}
                continue
            k, v = ln.split("=", 1)
            v = v.strip()
            if   k == "Name":         cur["name"]   = v
            elif k == "AdapterRAM":
                try:
                    cur["vram"] = f"{int(v) / (1024 ** 3):.1f} GB"
                except Exception:
                    cur["vram"] = "N/A"
            elif k == "DriverVersion": cur["driver"] = v
        if cur:
            gpus.append(cur)
        # 补充默认值 + NVIDIA 温度
        for g in gpus:
            g.setdefault("name", "N/A")
            g.setdefault("vram", "N/A")
            g.setdefault("driver", "N/A")
            g["temp"] = self._get_nv_temp(g["name"])
        return gpus

    @staticmethod
    def _get_nv_temp(gpu_name):
        """获取 NVIDIA GPU 温度（仅 N 卡有效）"""
        if "nvidia" not in gpu_name.lower():
            return "N/A"
        lines = HardwarePanel._run_cmd(
            "nvidia-smi --query-gpu=temperature.gpu "
            "--format=csv,noheader,nounits",
            timeout=5,
        )
        if lines and lines[0].strip().isdigit():
            return f"{lines[0].strip()}°C"
        return "N/A"

    def _get_ram(self):
        info = {"total": "N/A", "used": "N/A",
                "free": "N/A", "pct": "N/A"}
        lines = HardwarePanel._run_cmd(
            "wmic ComputerSystem get TotalPhysicalMemory /value")
        total_b = None
        for ln in lines:
            if "=" in ln:
                try:
                    total_b = int(ln.split("=", 1)[1].strip())
                    info["total"] = f"{total_b / (1024 ** 3):.1f} GB"
                except Exception:
                    pass
        lines = HardwarePanel._run_cmd(
            "wmic OS get FreePhysicalMemory /value")
        for ln in lines:
            if "=" in ln:
                try:
                    free_kb = int(ln.split("=", 1)[1].strip())
                    free_gb = free_kb / (1024 ** 2)
                    info["free"] = f"{free_gb:.1f} GB"
                    if total_b:
                        total_gb = total_b / (1024 ** 3)
                        used_gb = total_gb - free_gb
                        info["used"] = f"{used_gb:.1f} GB"
                        info["pct"]  = f"{(used_gb / total_gb) * 100:.0f}%"
                except Exception:
                    pass
        return info

    def _get_disk(self):
        """获取硬盘信息（使用 PowerShell 准确区分 SSD/HDD）"""
        disks = []
        # 使用 _run_ps 避免引号嵌套问题
        ps_cmd = (
            'Get-PhysicalDisk | Select-Object DeviceId,Model,Size,MediaType | '
            'ForEach-Object { "DeviceId=" + $_.DeviceId + ";" + '
            '"Model=" + $_.Model + ";" + '
            '"Size=" + $_.Size + ";" + '
            '"MediaType=" + $_.MediaType }'
        )
        lines = HardwarePanel._run_ps(ps_cmd, timeout=10)
        if lines:
            for ln in lines:
                parts = ln.split(";")
                d = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        d[k.strip()] = v.strip()
                if d:
                    model = d.get("Model", "N/A")
                    media = d.get("MediaType", "Unknown")
                    size_str = d.get("Size", "0")
                    try:
                        size_gb = f"{int(size_str) / (1024 ** 3):.0f} GB"
                    except Exception:
                        size_gb = "N/A"
                    disks.append({
                        "model": model,
                        "size":  size_gb,
                        "media": media,
                    })
            return disks
        # 降级方案：使用 WMIC（可能无法区分 SSD/HDD）
        return self._get_disk_wmic()

    def _get_disk_wmic(self):
        """降级方案：使用 WMIC 获取硬盘信息"""
        disks = []
        lines = HardwarePanel._run_cmd(
            "wmic diskdrive get Model,Size,MediaType /value")
        cur = {}
        for ln in lines:
            if "=" not in ln:
                if cur:
                    disks.append(cur)
                    cur = {}
                continue
            k, v = ln.split("=", 1)
            v = v.strip()
            if   k == "Model":    cur["model"] = v
            elif k == "Size":
                try:
                    cur["size"] = f"{int(v) / (1024 ** 3):.0f} GB"
                except Exception:
                    cur["size"] = "N/A"
            elif k == "MediaType": cur["media"] = v
        if cur:
            disks.append(cur)
        return disks

    def _get_board(self):
        info = {"manufacturer": "N/A", "product": "N/A", "version": "N/A"}
        lines = HardwarePanel._run_cmd(
            "wmic baseboard get Manufacturer,Product,Version /value")
        for ln in lines:
            if "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            v = v.strip()
            if   k == "Manufacturer": info["manufacturer"] = v
            elif k == "Product":      info["product"]      = v
            elif k == "Version":      info["version"]      = v
        return info

    def _get_os(self):
        info = {"caption": "N/A", "version": "N/A", "arch": "N/A"}
        lines = HardwarePanel._run_cmd(
            "wmic os get Caption,Version,OSArchitecture /value")
        for ln in lines:
            if "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            v = v.strip()
            if   k == "Caption":        info["caption"] = v
            elif k == "Version":        info["version"] = v
            elif k == "OSArchitecture": info["arch"]    = v
        return info

    # ───────────────────────────────────────────────
    #  UI 渲染
    # ───────────────────────────────────────────────

    def _render(self, d):
        """将采集到的硬件信息渲染到 UI"""
        for w in self.inner.winfo_children():
            w.destroy()
        row = 0
        row = self._render_overview(row, d)
        row = self._render_cpu(row, d.get("cpu", {}))
        for gpu in d.get("gpu", []):
            row = self._render_gpu(row, gpu)
        row = self._render_ram(row, d.get("ram", {}))
        for disk in d.get("disk", []):
            row = self._render_disk(row, disk)
        row = self._render_board_os(row, d.get("board", {}), d.get("os", {}))

    def _render_overview(self, row, d):
        """顶部概览卡片（CPU 使用率 / 内存使用率 / 硬盘数）"""
        card = ctk.CTkFrame(
            self.inner, fg_color=COLORS["bg_card2"], corner_radius=14)
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure((0, 1, 2), weight=1)

        self._ov_item(card, 0, "🔲  CPU 使用率",
                      d.get("cpu", {}).get("usage", "N/A"),
                      COLORS["accent_blue"])
        self._ov_item(card, 1, "🧠  内存使用率",
                      d.get("ram", {}).get("pct", "N/A"),
                      COLORS["accent_green"])
        self._ov_item(card, 2, "💾  硬盘数量",
                      f"{len(d.get('disk', []))} 个",
                      COLORS["accent_orange"])
        return row + 1

    def _ov_item(self, parent, col, title, value, color):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, padx=16, pady=16, sticky="nsew")
        ctk.CTkLabel(
            f, text=title, font=ctk.CTkFont(family=_FONT_FAMILY, size=11),
            text_color=COLORS["text_secondary"],
        ).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(
            f, text=value,
            font=ctk.CTkFont(family=_FONT_FAMILY, size=22, weight="bold"),
            text_color=color,
        ).pack(anchor="w")

    def _render_cpu(self, row, cpu):
        card = self._info_card(self.inner, "🔲  CPU 处理器")
        self._fill_card(card, [
            ("型号",        cpu.get("name",   "N/A")),
            ("核心 / 线程", f"{cpu.get('cores',  '?')} 核 / {cpu.get('threads', '?')} 线程"),
            ("基准频率",     cpu.get("freq",    "N/A")),
            ("当前使用率",   cpu.get("usage",   "N/A")),
        ])
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        return row + 1

    def _render_gpu(self, row, gpu):
        card = self._info_card(self.inner, "🎮  GPU 显卡")
        self._fill_card(card, [
            ("型号",     gpu.get("name",   "N/A")),
            ("显存",     gpu.get("vram",   "N/A")),
            ("驱动版本", gpu.get("driver", "N/A")),
            ("温度",     gpu.get("temp",   "N/A")),
        ])
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        return row + 1

    def _render_ram(self, row, ram):
        card = self._info_card(self.inner, "🧠  内存 (RAM)")
        self._fill_card(card, [
            ("总容量", ram.get("total", "N/A")),
            ("已使用", ram.get("used",  "N/A")),
            ("可用",   ram.get("free",  "N/A")),
            ("使用率", ram.get("pct",   "N/A")),
        ])
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        return row + 1

    def _render_disk(self, row, disk):
        media = disk.get("media", "")
        if "SSD" in str(media).upper():
            title = "💾  固态硬盘 (SSD)"
            title_color = COLORS["accent_blue"]
        elif "HDD" in str(media).upper():
            title = "💿  机械硬盘 (HDD)"
            title_color = COLORS["accent_orange"]
        else:
            title = "💾  硬盘"
            title_color = COLORS["accent_blue"]
        card = self._info_card(self.inner, title, title_color=title_color)
        self._fill_card(card, [
            ("型号", disk.get("model", "N/A")),
            ("容量", disk.get("size",  "N/A")),
            ("类型", disk.get("media", "N/A")),
        ])
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        return row + 1

    def _render_board_os(self, row, board, os_info):
        card = self._info_card(self.inner, "🖥  主板 & 系统")
        self._fill_card(card, [
            ("主板制造商", board.get("manufacturer", "N/A")),
            ("主板型号",   board.get("product",      "N/A")),
            ("操作系统",   os_info.get("caption",    "N/A")),
            ("系统架构",   os_info.get("arch",        "N/A")),
        ])
        card.grid(row=row, column=0, sticky="ew", pady=(0, 10))
        return row + 1

    # ───────────────────────────────────────────────
    #  UI 辅助方法
    # ───────────────────────────────────────────────

    @staticmethod
    def _info_card(parent, title, title_color=None):
        """创建一个带标题的信息卡片 Frame"""
        if title_color is None:
            title_color = COLORS["accent_blue"]
        card = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=14)
        card.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(family=_FONT_FAMILY, size=15, weight="bold"),
            text_color=title_color,
        ).grid(row=0, column=0, columnspan=2,
               padx=20, pady=(14, 8), sticky="w")
        return card

    @staticmethod
    def _fill_card(card, items):
        """向 info_card 填充 key-value 行（交替底色）"""
        for i, (key, val) in enumerate(items):
            r = i + 1
            bg = COLORS["bg_card2"] if i % 2 == 0 else COLORS["bg_card"]
            row_bg = ctk.CTkFrame(card, fg_color=bg, corner_radius=6)
            row_bg.grid(row=r, column=0, columnspan=2,
                        padx=16, pady=(0, 4), sticky="ew")
            row_bg.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(
                row_bg, text=f"{key}：",
                font=ctk.CTkFont(family=_FONT_FAMILY, size=12),
                text_color=COLORS["text_secondary"],
            ).grid(row=0, column=0, padx=(12, 6), pady=7, sticky="w")
            val_color = HardwarePanel._temp_color(val)
            ctk.CTkLabel(
                row_bg, text=str(val),
                font=ctk.CTkFont(family=_FONT_FAMILY, size=12, weight="bold"),
                text_color=val_color,
            ).grid(row=0, column=1, padx=(0, 12), pady=7, sticky="w")

    @staticmethod
    def _temp_color(val):
        """根据温度值返回对应颜色"""
        if "°C" in str(val):
            try:
                t = int(str(val).replace("°C", ""))
                if   t > 80: return COLORS["accent_red"]
                elif t > 65: return COLORS["accent_orange"]
                else:        return COLORS["accent_green"]
            except Exception:
                pass
        return COLORS["text_primary"]
