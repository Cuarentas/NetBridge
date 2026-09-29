#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetBridge GUI — 接入 sing-box / Xray
连接时启动本地混合代理 127.0.0.1:7890
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# ---------------- paths ----------------
def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_dir()
BIN_DIR = ROOT / "core" / "bin"
RUNTIME = ROOT / "runtime"
NODES_FILE = RUNTIME / "nodes.json"
PID_FILE = RUNTIME / "core.pid"
LOG_FILE = RUNTIME / "core.log"
CONFIG_FILE = RUNTIME / "config.json"

SINGBOX_VER = "1.11.0"
XRAY_VER = "25.3.6"
MIXED_PORT = 7890

BLUE, GREEN, ORANGE, RED = "#007AFF", "#34C759", "#FF9500", "#FF3B30"
BG, CARD, TEXT, SECONDARY = "#F2F2F7", "#FFFFFF", "#000000", "#8E8E93"


def ensure_dirs():
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)


# ---------------- core download ----------------
def _plat() -> tuple[str, str]:
    sysname = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    else:
        arch = "amd64"
    if sysname == "windows":
        return "windows", arch
    if sysname == "darwin":
        return "darwin", arch
    return "linux", arch


def singbox_path() -> Path:
    name = "sing-box.exe" if platform.system().lower() == "windows" else "sing-box"
    return BIN_DIR / name


def xray_path() -> Path:
    name = "xray.exe" if platform.system().lower() == "windows" else "xray"
    return BIN_DIR / name


def download_singbox(log=None):
    p = singbox_path()
    if p.exists():
        return p
    os_name, arch = _plat()
    if os_name == "windows":
        url = f"https://github.com/SagerNet/sing-box/releases/download/v{SINGBOX_VER}/sing-box-{SINGBOX_VER}-windows-{arch}.zip"
        is_zip = True
    else:
        url = f"https://github.com/SagerNet/sing-box/releases/download/v{SINGBOX_VER}/sing-box-{SINGBOX_VER}-{os_name}-{arch}.tar.gz"
        is_zip = False
    if log:
        log(f"下载 sing-box: {url}")
    tmp = Path(tempfile.mkdtemp())
    try:
        archive = tmp / ("sb.zip" if is_zip else "sb.tgz")
        urllib.request.urlretrieve(url, archive)
        if is_zip:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(tmp)
        else:
            with tarfile.open(archive, "r:gz") as tf:
                tf.extractall(tmp)
        found = None
        for f in tmp.rglob("sing-box*"):
            if f.is_file() and "sing-box" in f.name.lower():
                found = f
                break
        if not found:
            raise RuntimeError("压缩包内未找到 sing-box")
        shutil.copy2(found, p)
        if os_name != "windows":
            p.chmod(0o755)
        return p
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def download_xray(log=None):
    p = xray_path()
    if p.exists():
        return p
    os_name, arch = _plat()
    # Xray release naming
    if os_name == "windows":
        asset = f"Xray-windows-64.zip" if arch == "amd64" else f"Xray-windows-arm64-v8a.zip"
    elif os_name == "darwin":
        asset = f"Xray-macos-64.zip" if arch == "amd64" else f"Xray-macos-arm64-v8a.zip"
    else:
        asset = f"Xray-linux-64.zip" if arch == "amd64" else f"Xray-linux-arm64-v8a.zip"
    url = f"https://github.com/XTLS/Xray-core/releases/download/v{XRAY_VER}/{asset}"
    if log:
        log(f"下载 Xray: {url}")
    tmp = Path(tempfile.mkdtemp())
    try:
        archive = tmp / "xray.zip"
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        found = None
        for f in tmp.rglob("*"):
            if f.is_file() and f.name.lower() in ("xray", "xray.exe"):
                found = f
                break
        if not found:
            raise RuntimeError("压缩包内未找到 xray")
        shutil.copy2(found, p)
        if os_name != "windows":
            p.chmod(0o755)
        return p
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------- config builders ----------------
def build_singbox_config(node: dict) -> dict:
    """Minimal sing-box: mixed inbound + one outbound from node."""
    proto = node.get("protocol", "ss").lower()
    outbound: dict = {"tag": "proxy"}

    if proto in ("ss", "shadowsocks"):
        outbound.update({
            "type": "shadowsocks",
            "server": node["server"],
            "server_port": int(node["port"]),
            "method": node.get("method") or "aes-256-gcm",
            "password": node.get("password") or "",
        })
    elif proto == "vmess":
        outbound.update({
            "type": "vmess",
            "server": node["server"],
            "server_port": int(node["port"]),
            "uuid": node.get("uuid") or node.get("password") or "",
            "security": node.get("security") or "auto",
            "alter_id": int(node.get("alter_id") or 0),
        })
    elif proto == "vless":
        outbound.update({
            "type": "vless",
            "server": node["server"],
            "server_port": int(node["port"]),
            "uuid": node.get("uuid") or node.get("password") or "",
        })
        if node.get("tls") in (True, "1", "true", "yes"):
            outbound["tls"] = {"enabled": True, "server_name": node.get("sni") or node["server"]}
    elif proto == "trojan":
        outbound.update({
            "type": "trojan",
            "server": node["server"],
            "server_port": int(node["port"]),
            "password": node.get("password") or "",
            "tls": {"enabled": True, "server_name": node.get("sni") or node["server"]},
        })
    elif proto in ("socks", "socks5"):
        outbound.update({
            "type": "socks",
            "server": node["server"],
            "server_port": int(node["port"]),
        })
        if node.get("password"):
            outbound["username"] = node.get("username") or ""
            outbound["password"] = node.get("password") or ""
    elif proto == "http":
        outbound.update({
            "type": "http",
            "server": node["server"],
            "server_port": int(node["port"]),
        })
        if node.get("password"):
            outbound["username"] = node.get("username") or ""
            outbound["password"] = node.get("password") or ""
    else:
        # fallback: try shadowsocks fields
        outbound.update({
            "type": "shadowsocks",
            "server": node["server"],
            "server_port": int(node["port"]),
            "method": node.get("method") or "aes-256-gcm",
            "password": node.get("password") or "",
        })

    return {
        "log": {"level": "info", "timestamp": True},
        "inbounds": [{
            "type": "mixed",
            "tag": "mixed-in",
            "listen": "127.0.0.1",
            "listen_port": MIXED_PORT,
            "sniff": True,
        }],
        "outbounds": [
            outbound,
            {"type": "direct", "tag": "direct"},
            {"type": "block", "tag": "block"},
        ],
        "route": {"final": "proxy", "auto_detect_interface": True},
    }


def build_xray_config(node: dict) -> dict:
    proto = node.get("protocol", "ss").lower()
    outbound: dict = {"tag": "proxy", "protocol": "freedom"}

    if proto in ("ss", "shadowsocks"):
        outbound = {
            "tag": "proxy",
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "method": node.get("method") or "aes-256-gcm",
                    "password": node.get("password") or "",
                }]
            },
        }
    elif proto == "vmess":
        outbound = {
            "tag": "proxy",
            "protocol": "vmess",
            "settings": {
                "vnext": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "users": [{
                        "id": node.get("uuid") or node.get("password") or "",
                        "alterId": int(node.get("alter_id") or 0),
                        "security": node.get("security") or "auto",
                    }],
                }]
            },
        }
    elif proto == "vless":
        outbound = {
            "tag": "proxy",
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "users": [{"id": node.get("uuid") or node.get("password") or "", "encryption": "none"}],
                }]
            },
        }
        if node.get("tls") in (True, "1", "true", "yes"):
            outbound["streamSettings"] = {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {"serverName": node.get("sni") or node["server"]},
            }
    elif proto == "trojan":
        outbound = {
            "tag": "proxy",
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "password": node.get("password") or "",
                }]
            },
            "streamSettings": {
                "network": "tcp",
                "security": "tls",
                "tlsSettings": {"serverName": node.get("sni") or node["server"]},
            },
        }
    elif proto in ("socks", "socks5"):
        user = []
        if node.get("password"):
            user = [{"user": node.get("username") or "", "pass": node.get("password") or ""}]
        outbound = {
            "tag": "proxy",
            "protocol": "socks",
            "settings": {
                "servers": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "users": user,
                }]
            },
        }
    else:
        outbound = {
            "tag": "proxy",
            "protocol": "shadowsocks",
            "settings": {
                "servers": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "method": node.get("method") or "aes-256-gcm",
                    "password": node.get("password") or "",
                }]
            },
        }

    return {
        "log": {"loglevel": "info"},
        "inbounds": [{
            "tag": "mixed-in",
            "port": MIXED_PORT,
            "listen": "127.0.0.1",
            "protocol": "mixed",
            "settings": {"udp": True},
            "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
        }],
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [],
        },
    }


# ---------------- process control ----------------
def is_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        return False
    if platform.system().lower() == "windows":
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_core():
    if not PID_FILE.exists():
        return
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return
    try:
        if platform.system().lower() == "windows":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.3)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    except Exception:
        pass
    PID_FILE.unlink(missing_ok=True)


def start_core(core: str, node: dict, log_cb=None) -> None:
    ensure_dirs()
    stop_core()

    if core == "xray":
        binary = download_xray(log_cb)
        cfg = build_xray_config(node)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [str(binary), "run", "-c", str(CONFIG_FILE)]
    else:
        binary = download_singbox(log_cb)
        cfg = build_singbox_config(node)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [str(binary), "run", "-c", str(CONFIG_FILE)]

    log_f = open(LOG_FILE, "w", encoding="utf-8")
    kwargs = {"stdout": log_f, "stderr": subprocess.STDOUT}
    if platform.system().lower() == "windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore
    proc = subprocess.Popen(cmd, **kwargs)
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    time.sleep(0.8)
    if proc.poll() is not None:
        log_f.close()
        err = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-2000:]
        PID_FILE.unlink(missing_ok=True)
        raise RuntimeError(f"核心启动失败:\n{err}")


# ---------------- nodes storage ----------------
def load_nodes() -> list:
    ensure_dirs()
    if NODES_FILE.exists():
        try:
            return json.loads(NODES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_nodes(nodes: list):
    ensure_dirs()
    NODES_FILE.write_text(json.dumps(nodes, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- GUI ----------------
class NetBridgeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NetBridge")
        self.geometry("420x680")
        self.minsize(380, 600)
        self.configure(bg=BG)

        ensure_dirs()
        self.nodes = load_nodes()
        self.current_index = 0
        self.status = "disconnected"
        self.core_var = tk.StringVar(value="sing-box")
        self.upload = "0 B/s"
        self.download = "0 B/s"

        if not self.nodes:
            self.nodes = [{
                "name": "请添加真实节点",
                "protocol": "ss",
                "server": "",
                "port": 443,
                "password": "",
                "method": "aes-256-gcm",
                "uuid": "",
            }]
            save_nodes(self.nodes)

        self._build_ui()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def current_node(self) -> dict:
        if not self.nodes:
            return {}
        self.current_index = max(0, min(self.current_index, len(self.nodes) - 1))
        return self.nodes[self.current_index]

    def _build_ui(self):
        # core selector
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=20, pady=(12, 0))
        tk.Label(bar, text="核心", bg=BG, fg=SECONDARY, font=("Segoe UI", 10)).pack(side="left")
        ttk.Radiobutton(bar, text="sing-box", variable=self.core_var, value="sing-box").pack(side="left", padx=6)
        ttk.Radiobutton(bar, text="Xray", variable=self.core_var, value="xray").pack(side="left", padx=6)

        # node card
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x", padx=20, pady=(12, 8))
        self.lbl_node = tk.Label(top, text="", font=("Segoe UI", 14, "bold"), bg=CARD, fg=TEXT, cursor="hand2")
        self.lbl_node.pack(pady=(16, 4))
        self.lbl_sub = tk.Label(top, text="", font=("Segoe UI", 11), bg=CARD, fg=SECONDARY, cursor="hand2")
        self.lbl_sub.pack(pady=(0, 16))
        for w in (top, self.lbl_node, self.lbl_sub):
            w.bind("<Button-1>", lambda e: self._open_nodes())

        # button
        mid = tk.Frame(self, bg=BG)
        mid.pack(expand=True, fill="both")
        self.canvas = tk.Canvas(mid, width=180, height=180, bg=BG, highlightthickness=0)
        self.canvas.pack(expand=True)
        self.btn_id = self.canvas.create_oval(10, 10, 170, 170, fill=BLUE, outline="")
        self.txt_id = self.canvas.create_text(90, 90, text="连接", fill="white", font=("Segoe UI", 18, "bold"))
        self.canvas.bind("<Button-1>", lambda e: self._toggle())

        # speed + proxy tip
        self.lbl_up = tk.Label(self, text="↑ 0 B/s", font=("Segoe UI", 12), bg=BG, fg=SECONDARY)
        self.lbl_up.pack()
        self.lbl_down = tk.Label(self, text="↓ 0 B/s", font=("Segoe UI", 12), bg=BG, fg=SECONDARY)
        self.lbl_down.pack()
        self.lbl_proxy = tk.Label(
            self, text=f"本地代理 127.0.0.1:{MIXED_PORT} (HTTP/SOCKS5)",
            font=("Segoe UI", 10), bg=BG, fg=SECONDARY
        )
        self.lbl_proxy.pack(pady=(6, 0))

        # bottom
        bottom = tk.Frame(self, bg=CARD)
        bottom.pack(fill="x", padx=20, pady=(12, 16))
        for text, cmd in [("节点", self._open_nodes), ("添加", self._add_node_dialog), ("设置", self._settings)]:
            tk.Button(
                bottom, text=text, font=("Segoe UI", 11), bg=CARD, fg=TEXT,
                relief="flat", cursor="hand2", command=cmd, padx=12, pady=12
            ).pack(side="left", expand=True)

        self.lbl_status = tk.Label(self, text="", font=("Segoe UI", 9), bg=BG, fg=SECONDARY)
        self.lbl_status.pack(pady=(0, 10))

    def _refresh(self):
        n = self.current_node()
        name = n.get("name") or f"{n.get('server','')}:{n.get('port','')}"
        proto = n.get("protocol", "?")
        self.lbl_node.config(text=name or "未选择节点")
        self.lbl_sub.config(text=f"{proto} · {n.get('server','')}:{n.get('port','')}")
        colors = {"disconnected": BLUE, "connecting": ORANGE, "connected": GREEN, "error": RED}
        labels = {"disconnected": "连接", "connecting": "连接中", "connected": "已连接", "error": "重试"}
        self.canvas.itemconfig(self.btn_id, fill=colors.get(self.status, BLUE))
        self.canvas.itemconfig(self.txt_id, text=labels.get(self.status, "连接"))
        self.lbl_up.config(text=f"↑ {self.upload}")
        self.lbl_down.config(text=f"↓ {self.download}")
        if self.status == "connected":
            self.lbl_status.config(text=f"已启动 · 请将系统/浏览器代理设为 127.0.0.1:{MIXED_PORT}")
        elif self.status == "error":
            self.lbl_status.config(text="启动失败，请查看设置中的日志")
        else:
            self.lbl_status.config(text="添加真实节点后点击连接")

    def _toggle(self):
        if self.status == "connected":
            stop_core()
            self.status = "disconnected"
            self.upload = "0 B/s"
            self.download = "0 B/s"
            self._refresh()
            return
        if self.status == "connecting":
            return

        node = self.current_node()
        if not node.get("server"):
            messagebox.showwarning("提示", "请先添加真实节点（服务器地址不能为空）")
            self._add_node_dialog()
            return

        self.status = "connecting"
        self._refresh()
        core = self.core_var.get()

        def work():
            try:
                def log(msg):
                    self.after(0, lambda: self.lbl_status.config(text=msg))

                start_core(core, node, log)
                self.status = "connected"
                self.upload = "--"
                self.download = "--"
            except Exception as e:
                self.status = "error"
                self.after(0, lambda: messagebox.showerror("连接失败", str(e)))
            self.after(0, self._refresh)

        threading.Thread(target=work, daemon=True).start()

    def _open_nodes(self):
        win = tk.Toplevel(self)
        win.title("节点列表")
        win.geometry("380x440")
        win.configure(bg=BG)

        tk.Label(win, text="点击选择节点", font=("Segoe UI", 12, "bold"), bg=BG).pack(pady=10)
        box = tk.Frame(win, bg=BG)
        box.pack(fill="both", expand=True, padx=12)

        for i, n in enumerate(self.nodes):
            label = n.get("name") or f"{n.get('server')}:{n.get('port')}"
            sub = f"{n.get('protocol')} · {n.get('server')}:{n.get('port')}"

            def select(idx=i):
                self.current_index = idx
                self._refresh()
                win.destroy()

            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", pady=3)
            tk.Button(
                row, text=f"{label}\n{sub}", font=("Segoe UI", 10),
                bg=CARD, fg=TEXT, relief="flat", anchor="w", justify="left",
                command=select, padx=10, pady=8
            ).pack(fill="x")

        tk.Button(win, text="添加节点", command=lambda: (win.destroy(), self._add_node_dialog())).pack(pady=10)

    def _add_node_dialog(self):
        win = tk.Toplevel(self)
        win.title("添加节点")
        win.geometry("360x420")
        win.configure(bg=BG)

        fields = {}
        labels = [
            ("名称", "name", ""),
            ("协议 ss/vmess/vless/trojan/socks", "protocol", "ss"),
            ("服务器", "server", ""),
            ("端口", "port", "443"),
            ("密码/UUID", "password", ""),
            ("加密方式(SS)", "method", "aes-256-gcm"),
            ("SNI/域名(可选)", "sni", ""),
        ]
        form = tk.Frame(win, bg=BG)
        form.pack(fill="both", expand=True, padx=16, pady=12)
        for i, (lab, key, default) in enumerate(labels):
            tk.Label(form, text=lab, bg=BG, anchor="w").grid(row=i, column=0, sticky="w", pady=4)
            ent = tk.Entry(form, width=28)
            ent.insert(0, default)
            ent.grid(row=i, column=1, pady=4)
            fields[key] = ent

        def save():
            try:
                port = int(fields["port"].get().strip() or "443")
            except ValueError:
                messagebox.showerror("错误", "端口必须是数字")
                return
            node = {
                "name": fields["name"].get().strip() or fields["server"].get().strip(),
                "protocol": fields["protocol"].get().strip().lower() or "ss",
                "server": fields["server"].get().strip(),
                "port": port,
                "password": fields["password"].get().strip(),
                "uuid": fields["password"].get().strip(),
                "method": fields["method"].get().strip() or "aes-256-gcm",
                "sni": fields["sni"].get().strip(),
                "tls": True,
            }
            if not node["server"]:
                messagebox.showerror("错误", "服务器不能为空")
                return
            # remove placeholder empty nodes
            self.nodes = [n for n in self.nodes if n.get("server")]
            self.nodes.append(node)
            save_nodes(self.nodes)
            self.current_index = len(self.nodes) - 1
            self._refresh()
            win.destroy()

        tk.Button(win, text="保存", command=save, padx=20, pady=8).pack(pady=10)

    def _settings(self):
        win = tk.Toplevel(self)
        win.title("设置 / 日志")
        win.geometry("480x400")
        txt = tk.Text(win, font=("Consolas", 9))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        info = [
            f"核心目录: {BIN_DIR}",
            f"配置文件: {CONFIG_FILE}",
            f"日志文件: {LOG_FILE}",
            f"本地代理: 127.0.0.1:{MIXED_PORT}",
            "",
            "使用方法:",
            "1. 添加真实节点（服务器/端口/密码或UUID）",
            "2. 选择核心 sing-box 或 Xray",
            "3. 点击连接（首次会自动下载核心）",
            "4. 将系统或浏览器代理设为 127.0.0.1:7890",
            "",
            "--- 最近日志 ---",
            "",
        ]
        txt.insert("end", "\n".join(info))
        if LOG_FILE.exists():
            txt.insert("end", LOG_FILE.read_text(encoding="utf-8", errors="replace")[-4000:])
        txt.config(state="disabled")

    def _on_close(self):
        stop_core()
        self.destroy()


def main():
    ensure_dirs()
    app = NetBridgeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
