#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NetBridge GUI v0.4
- sing-box / Xray
- WS / gRPC / Reality 等传输
- 订阅一键导入
- 系统代理自动设置
- TUN 模式（需管理员权限，sing-box）
"""

from __future__ import annotations

import base64
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import concurrent.futures
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# ===================== paths =====================
def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


ROOT = app_dir()
BIN_DIR = ROOT / "core" / "bin"
RUNTIME = ROOT / "runtime"
NODES_FILE = RUNTIME / "nodes.json"
SUBS_FILE = RUNTIME / "subscriptions.json"
SETTINGS_FILE = RUNTIME / "settings.json"
PID_FILE = RUNTIME / "core.pid"
LOG_FILE = RUNTIME / "core.log"
CONFIG_FILE = RUNTIME / "config.json"

SINGBOX_VER = "1.11.0"
XRAY_VER = "25.3.6"
MIXED_PORT = 7890
APP_VERSION = "1.0.1"

def app_version() -> str:
    """与工程 VERSION 文件保持一致；找不到则用内置 APP_VERSION。"""
    candidates = [
        Path(__file__).resolve().parent.parent / "VERSION",
        Path(__file__).resolve().parent / "VERSION",
        Path.cwd() / "VERSION",
    ]
    # PyInstaller 解压目录旁
    if getattr(sys, "frozen", False):
        candidates.insert(0, Path(sys.executable).resolve().parent / "VERSION")
    for c in candidates:
        try:
            if c.is_file():
                v = c.read_text(encoding="utf-8").strip().splitlines()[0].strip()
                if v:
                    return v.lstrip("vV")
        except Exception:
            pass
    return APP_VERSION


BLUE, GREEN, ORANGE, RED = "#007AFF", "#34C759", "#FF9500", "#FF3B30"
BG, CARD, TEXT, SECONDARY = "#F2F2F7", "#FFFFFF", "#000000", "#8E8E93"


def ensure_dirs():
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def save_json(path: Path, data):
    ensure_dirs()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ===================== settings =====================
DEFAULT_SETTINGS = {
    "core": "sing-box",
    "system_proxy": True,
    "tun": False,
    "mixed_port": MIXED_PORT,
    "allow_lan": False,
    "log_level": "info",  # trace/debug/info/warn/error/fatal/panic
}


def load_settings() -> dict:
    s = load_json(SETTINGS_FILE, {})
    out = dict(DEFAULT_SETTINGS)
    out.update(s)
    # 统一默认端口 7890（1314 在部分 Windows 环境无法监听）
    if out.get("mixed_port") in (1314, "1314", None, 7890, "7890"):
        out["mixed_port"] = MIXED_PORT
    return out


def save_settings(s: dict):
    save_json(SETTINGS_FILE, s)


# ===================== platform helpers =====================
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


def is_windows() -> bool:
    return platform.system().lower() == "windows"


def is_mac() -> bool:
    return platform.system().lower() == "darwin"


def no_window_kwargs():
    if is_windows():
        return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    return {}


# ===================== core download =====================
def singbox_path() -> Path:
    return BIN_DIR / ("sing-box.exe" if is_windows() else "sing-box")


def xray_path() -> Path:
    return BIN_DIR / ("xray.exe" if is_windows() else "xray")


def download_singbox(log=None) -> Path:
    p = singbox_path()
    if p.exists():
        if log:
            log("使用内置 sing-box")
        return p
    os_name, arch = _plat()
    if os_name == "windows":
        url = f"https://github.com/SagerNet/sing-box/releases/download/v{SINGBOX_VER}/sing-box-{SINGBOX_VER}-windows-{arch}.zip"
        is_zip = True
    else:
        url = f"https://github.com/SagerNet/sing-box/releases/download/v{SINGBOX_VER}/sing-box-{SINGBOX_VER}-{os_name}-{arch}.tar.gz"
        is_zip = False
    if log:
        log(f"下载 sing-box ...")
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
        found = next((f for f in tmp.rglob("sing-box*") if f.is_file()), None)
        if not found:
            raise RuntimeError("未找到 sing-box 二进制")
        shutil.copy2(found, p)
        if not is_windows():
            p.chmod(0o755)
        return p
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def download_xray(log=None) -> Path:
    p = xray_path()
    if p.exists():
        if log:
            log("使用内置 Xray")
        return p
    os_name, arch = _plat()
    if os_name == "windows":
        asset = "Xray-windows-64.zip" if arch == "amd64" else "Xray-windows-arm64-v8a.zip"
    elif os_name == "darwin":
        asset = "Xray-macos-64.zip" if arch == "amd64" else "Xray-macos-arm64-v8a.zip"
    else:
        asset = "Xray-linux-64.zip" if arch == "amd64" else "Xray-linux-arm64-v8a.zip"
    url = f"https://github.com/XTLS/Xray-core/releases/download/v{XRAY_VER}/{asset}"
    if log:
        log("下载 Xray ...")
    tmp = Path(tempfile.mkdtemp())
    try:
        archive = tmp / "xray.zip"
        urllib.request.urlretrieve(url, archive)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
        found = next(
            (f for f in tmp.rglob("*") if f.is_file() and f.name.lower() in ("xray", "xray.exe")),
            None,
        )
        if not found:
            raise RuntimeError("未找到 xray 二进制")
        shutil.copy2(found, p)
        if not is_windows():
            p.chmod(0o755)
        return p
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===================== subscription / link parse =====================
def _b64decode(s: str) -> str:
    s = s.strip().replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    if pad:
        s += "=" * pad
    return base64.b64decode(s).decode("utf-8", errors="ignore")


def _safe_b64_json(s: str) -> dict:
    try:
        return json.loads(_b64decode(s))
    except Exception:
        return {}


def parse_ss(url: str) -> dict | None:
    # ss://method:password@host:port#name  or ss://base64#name
    try:
        u = url.strip()
        if not u.startswith("ss://"):
            return None
        u = u[5:]
        name = ""
        if "#" in u:
            u, name = u.split("#", 1)
            name = urllib.parse.unquote(name)
        if "@" not in u:
            decoded = _b64decode(u)
            if "@" in decoded:
                userinfo, hostport = decoded.rsplit("@", 1)
            else:
                return None
        else:
            userinfo, hostport = u.rsplit("@", 1)
            if ":" not in userinfo:
                userinfo = _b64decode(userinfo)
        method, password = userinfo.split(":", 1)
        host, port = hostport.rsplit(":", 1)
        return {
            "name": name or f"SS-{host}",
            "protocol": "ss",
            "server": host,
            "port": int(port),
            "method": method,
            "password": password,
            "network": "tcp",
        }
    except Exception:
        return None


def parse_trojan(url: str) -> dict | None:
    try:
        if not url.startswith("trojan://"):
            return None
        p = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(p.query)
        name = urllib.parse.unquote(p.fragment) if p.fragment else f"Trojan-{p.hostname}"
        node = {
            "name": name,
            "protocol": "trojan",
            "server": p.hostname or "",
            "port": p.port or 443,
            "password": urllib.parse.unquote(p.username or ""),
            "network": (q.get("type") or ["tcp"])[0],
            "tls": True,
            "sni": (q.get("sni") or q.get("peer") or [p.hostname or ""])[0],
            "path": (q.get("path") or [""])[0],
            "host": (q.get("host") or [""])[0],
            "service_name": (q.get("serviceName") or q.get("service_name") or [""])[0],
            "fp": (q.get("fp") or [""])[0],
        }
        return node
    except Exception:
        return None


def parse_vmess(url: str) -> dict | None:
    try:
        if not url.startswith("vmess://"):
            return None
        data = _safe_b64_json(url[8:])
        if not data:
            return None
        net = data.get("net") or data.get("type") or "tcp"
        node = {
            "name": data.get("ps") or data.get("name") or f"VMess-{data.get('add')}",
            "protocol": "vmess",
            "server": data.get("add") or data.get("host") or "",
            "port": int(data.get("port") or 443),
            "uuid": data.get("id") or "",
            "password": data.get("id") or "",
            "alter_id": int(data.get("aid") or 0),
            "security": data.get("scy") or data.get("security") or "auto",
            "network": net,
            "path": data.get("path") or "",
            "host": data.get("host") or data.get("sni") or "",
            "sni": data.get("sni") or data.get("host") or "",
            "tls": (data.get("tls") or "") in ("tls", "1", "true", True),
            "service_name": data.get("serviceName") or data.get("path") or "",
        }
        return node
    except Exception:
        return None


def parse_vless(url: str) -> dict | None:
    try:
        if not url.startswith("vless://"):
            return None
        p = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(p.query)
        name = urllib.parse.unquote(p.fragment) if p.fragment else f"VLESS-{p.hostname}"
        security = (q.get("security") or ["none"])[0]
        network = (q.get("type") or ["tcp"])[0]
        node = {
            "name": name,
            "protocol": "vless",
            "server": p.hostname or "",
            "port": p.port or 443,
            "uuid": urllib.parse.unquote(p.username or ""),
            "password": urllib.parse.unquote(p.username or ""),
            "network": network,
            "tls": security in ("tls", "reality"),
            "reality": security == "reality",
            "sni": (q.get("sni") or [""])[0],
            "path": urllib.parse.unquote((q.get("path") or [""])[0]),
            "host": (q.get("host") or [""])[0],
            "service_name": (q.get("serviceName") or q.get("service_name") or [""])[0],
            "fp": (q.get("fp") or ["chrome"])[0],
            "pbk": (q.get("pbk") or [""])[0],
            "sid": (q.get("sid") or [""])[0],
            "spx": (q.get("spx") or [""])[0],
            "flow": (q.get("flow") or [""])[0],
            "alpn": (q.get("alpn") or [""])[0],
        }
        return node
    except Exception:
        return None


def parse_share_link(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    for parser in (parse_ss, parse_vmess, parse_vless, parse_trojan):
        n = parser(line)
        if n and n.get("server"):
            return n
    return None


def parse_subscription_content(text: str) -> list[dict]:
    """Parse base64 subscription, plain share links, or simple clash-like proxies list."""
    text = text.strip()
    nodes: list[dict] = []

    # try whole-text base64
    if "://" not in text[:80]:
        try:
            decoded = _b64decode(text)
            if "://" in decoded or "\n" in decoded:
                text = decoded
        except Exception:
            pass

    # line by line share links
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        n = parse_share_link(line)
        if n:
            nodes.append(n)

    # clash yaml proxies: very light parser for type/server/port/uuid etc
    if not nodes and ("proxies:" in text or "type:" in text):
        nodes.extend(_parse_clash_proxies(text))

    return nodes


def _parse_clash_proxies(text: str) -> list[dict]:
    """Minimal YAML-ish proxy block parser (no full YAML dependency)."""
    nodes = []
    blocks = re.split(r"\n\s*-\s+", text)
    for block in blocks:
        d = {}
        for line in block.splitlines():
            m = re.match(r"\s*([A-Za-z0-9_-]+)\s*:\s*(.+)\s*$", line)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip().strip("\"'")
            d[k] = v
        if "server" not in d or "port" not in d:
            continue
        typ = (d.get("type") or "ss").lower()
        node = {
            "name": d.get("name") or f"{typ}-{d['server']}",
            "protocol": "ss" if typ == "ss" else typ,
            "server": d["server"],
            "port": int(d["port"]),
            "password": d.get("password") or d.get("uuid") or "",
            "uuid": d.get("uuid") or d.get("password") or "",
            "method": d.get("cipher") or d.get("method") or "aes-256-gcm",
            "network": d.get("network") or "tcp",
            "tls": str(d.get("tls", "")).lower() in ("true", "1", "yes"),
            "sni": d.get("servername") or d.get("sni") or "",
            "path": "",
            "host": "",
            "reality": False,
            "pbk": "",
            "sid": "",
            "fp": d.get("client-fingerprint") or "",
            "flow": d.get("flow") or "",
            "service_name": "",
        }
        # opts
        # path/host often nested; try flat keys
        if d.get("ws-opts") or "path" in d:
            node["path"] = d.get("path") or ""
        if d.get("grpc-opts"):
            node["network"] = "grpc"
        if str(d.get("reality-opts", "")) or d.get("public-key"):
            node["reality"] = True
            node["tls"] = True
            node["pbk"] = d.get("public-key") or ""
            node["sid"] = d.get("short-id") or ""
        nodes.append(node)
    return nodes


def fetch_subscription(url: str, timeout: int = 20) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": f"NetBridge/{APP_VERSION}"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        text = raw.decode("utf-8")
    except Exception:
        text = raw.decode("utf-8", errors="ignore")
    return parse_subscription_content(text)


# ===================== config builders (WS/gRPC/Reality) =====================
def _sb_tls(node: dict) -> dict | None:
    if not (node.get("tls") or node.get("reality")):
        return None
    tls: dict = {
        "enabled": True,
        "server_name": node.get("sni") or node.get("host") or node.get("server") or "",
    }
    if node.get("fp"):
        tls["utls"] = {"enabled": True, "fingerprint": node["fp"]}
    if node.get("alpn"):
        alpn = node["alpn"]
        tls["alpn"] = [a.strip() for a in alpn.split(",") if a.strip()]
    if node.get("reality"):
        tls["reality"] = {
            "enabled": True,
            "public_key": node.get("pbk") or "",
            "short_id": node.get("sid") or "",
        }
    return tls


def _sb_transport(node: dict) -> dict | None:
    net = (node.get("network") or "tcp").lower()
    if net in ("ws", "websocket"):
        t = {"type": "ws", "path": node.get("path") or "/"}
        if node.get("host"):
            t["headers"] = {"Host": node["host"]}
        return t
    if net == "grpc":
        return {
            "type": "grpc",
            "service_name": node.get("service_name") or node.get("path") or "GunService",
        }
    if net == "httpupgrade":
        t = {"type": "httpupgrade", "path": node.get("path") or "/"}
        if node.get("host"):
            t["host"] = node["host"]
        return t
    if net in ("h2", "http"):
        t = {"type": "http", "path": [node.get("path") or "/"]}
        if node.get("host"):
            t["host"] = [node["host"]]
        return t
    return None


def build_singbox_config(node: dict, settings: dict) -> dict:
    proto = (node.get("protocol") or "ss").lower()
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
        if node.get("flow"):
            outbound["flow"] = node["flow"]
    elif proto == "trojan":
        outbound.update({
            "type": "trojan",
            "server": node["server"],
            "server_port": int(node["port"]),
            "password": node.get("password") or "",
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
    else:
        outbound.update({
            "type": "shadowsocks",
            "server": node["server"],
            "server_port": int(node["port"]),
            "method": node.get("method") or "aes-256-gcm",
            "password": node.get("password") or "",
        })

    tls = _sb_tls(node)
    if tls:
        outbound["tls"] = tls
    transport = _sb_transport(node)
    if transport:
        outbound["transport"] = transport

    # trojan/vmess/vless 走 ws 时通常需要 TLS
    net = (node.get("network") or "tcp").lower()
    if net in ("ws", "websocket", "grpc") and not node.get("reality"):
        if node.get("tls") in (None, "", True, "1", "true", "yes") or proto in ("trojan", "vless"):
            if "tls" not in outbound:
                tls = _sb_tls({**node, "tls": True})
                if tls:
                    outbound["tls"] = tls

    port = int(settings.get("mixed_port") or MIXED_PORT)
    listen = "0.0.0.0" if settings.get("allow_lan") else "127.0.0.1"
    log_level = (settings.get("log_level") or "info").lower()
    inbounds = [
        {
            "type": "mixed",
            "tag": "mixed-in",
            "listen": listen,
            "listen_port": port,
            "sniff": True,
        },
        {
            "type": "socks",
            "tag": "socks-in",
            "listen": listen,
            "listen_port": port + 1,
            "sniff": True,
        },
    ]

    use_tun = bool(settings.get("tun"))
    if use_tun:
        inbounds.append({
            "type": "tun",
            "tag": "tun-in",
            "address": ["172.19.0.1/30"],
            "auto_route": True,
            "strict_route": False,
            "stack": "mixed",
            "sniff": True,
        })

    # 不再使用 dns/block 等 legacy special outbounds（sing-box 1.11+ 会告警）
    cfg = {
        "log": {"level": log_level, "timestamp": True},
        "dns": {
            "servers": [
                {"address": "8.8.8.8", "detour": "proxy"},
                {"address": "1.1.1.1", "detour": "proxy"},
                {"address": "local", "detour": "direct"},
            ],
            "strategy": "prefer_ipv4",
        },
        "inbounds": inbounds,
        "outbounds": [
            outbound,
            {"type": "direct", "tag": "direct"},
        ],
        "route": {
            "auto_detect_interface": True,
            "final": "proxy",
        },
    }
    return cfg


def _xray_stream(node: dict) -> dict:
    net = (node.get("network") or "tcp").lower()
    stream: dict = {"network": "tcp"}

    if net in ("ws", "websocket"):
        stream["network"] = "ws"
        stream["wsSettings"] = {"path": node.get("path") or "/"}
        if node.get("host"):
            stream["wsSettings"]["headers"] = {"Host": node["host"]}
    elif net == "grpc":
        stream["network"] = "grpc"
        stream["grpcSettings"] = {
            "serviceName": node.get("service_name") or node.get("path") or "GunService"
        }
    elif net in ("h2", "http"):
        stream["network"] = "h2"
        stream["httpSettings"] = {"path": node.get("path") or "/"}
        if node.get("host"):
            stream["httpSettings"]["host"] = [node["host"]]

    if node.get("reality"):
        stream["security"] = "reality"
        stream["realitySettings"] = {
            "serverName": node.get("sni") or node.get("server") or "",
            "fingerprint": node.get("fp") or "chrome",
            "publicKey": node.get("pbk") or "",
            "shortId": node.get("sid") or "",
            "spiderX": node.get("spx") or "",
        }
    elif node.get("tls"):
        stream["security"] = "tls"
        tls: dict = {"serverName": node.get("sni") or node.get("host") or node.get("server") or ""}
        if node.get("fp"):
            tls["fingerprint"] = node["fp"]
        if node.get("alpn"):
            tls["alpn"] = [a.strip() for a in node["alpn"].split(",") if a.strip()]
        stream["tlsSettings"] = tls

    return stream


def build_xray_config(node: dict, settings: dict) -> dict:
    proto = (node.get("protocol") or "ss").lower()
    stream = _xray_stream(node)

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
            "streamSettings": stream,
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
            "streamSettings": stream,
        }
    elif proto == "vless":
        user = {
            "id": node.get("uuid") or node.get("password") or "",
            "encryption": "none",
        }
        if node.get("flow"):
            user["flow"] = node["flow"]
        outbound = {
            "tag": "proxy",
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": node["server"],
                    "port": int(node["port"]),
                    "users": [user],
                }]
            },
            "streamSettings": stream,
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
            "streamSettings": stream,
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
            "streamSettings": stream,
        }

    port = int(settings.get("mixed_port") or MIXED_PORT)
    listen = "0.0.0.0" if settings.get("allow_lan") else "127.0.0.1"
    log_level = (settings.get("log_level") or "info").lower()
    xray_level = {"trace": "debug", "warn": "warning", "fatal": "error", "panic": "error"}.get(log_level, log_level)
    if xray_level not in ("debug", "info", "warning", "error", "none"):
        xray_level = "info"
    return {
        "log": {"loglevel": xray_level},
        "inbounds": [{
            "tag": "mixed-in",
            "port": port,
            "listen": listen,
            "protocol": "mixed",
            "settings": {"udp": True},
            "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
        }],
        "outbounds": [
            outbound,
            {"tag": "direct", "protocol": "freedom"},
            {"tag": "block", "protocol": "blackhole"},
        ],
        "routing": {"domainStrategy": "AsIs", "rules": []},
    }


# ===================== system proxy =====================
class SystemProxy:
    """Best-effort system HTTP(S) proxy. TUN is handled by core config."""

    def __init__(self):
        self._enabled = False
        self._port = MIXED_PORT

    def enable(self, port: int = MIXED_PORT):
        self._port = port
        host = "127.0.0.1"
        try:
            if is_windows():
                self._win_set(host, port, True)
            elif is_mac():
                self._mac_set(host, port, True)
            else:
                self._linux_set(host, port, True)
            self._enabled = True
        except Exception as e:
            raise RuntimeError(f"设置系统代理失败: {e}")

    def disable(self):
        if not self._enabled:
            # still try clean
            pass
        try:
            if is_windows():
                self._win_set("127.0.0.1", self._port, False)
            elif is_mac():
                self._mac_set("127.0.0.1", self._port, False)
            else:
                self._linux_set("127.0.0.1", self._port, False)
        except Exception:
            pass
        self._enabled = False

    def _win_set(self, host: str, port: int, enable: bool):
        import winreg  # type: ignore
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
            0,
            winreg.KEY_SET_VALUE,
        )
        try:
            if enable:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                # Windows 设置界面需要「地址 + 端口」分离；注册表用 host:port 最兼容
                winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, f"{host}:{port}")
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, "localhost;127.*;<local>")
            else:
                winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        finally:
            winreg.CloseKey(key)
        try:
            import ctypes
            internet_set_option = ctypes.windll.Wininet.InternetSetOptionW
            internet_set_option(0, 39, 0, 0)  # SETTINGS_CHANGED
            internet_set_option(0, 37, 0, 0)  # REFRESH
        except Exception:
            pass
        # WinHTTP（部分系统服务/程序走这条）
        try:
            if enable:
                subprocess.run(
                    ["netsh", "winhttp", "set", "proxy", f"{host}:{port}"],
                    capture_output=True, **no_window_kwargs(),
                )
            else:
                subprocess.run(
                    ["netsh", "winhttp", "reset", "proxy"],
                    capture_output=True, **no_window_kwargs(),
                )
        except Exception:
            pass

    def _mac_set(self, host: str, port: int, enable: bool):
        # Apply to common services
        services = ["Wi-Fi", "Ethernet"]
        for svc in services:
            if enable:
                subprocess.run(
                    ["networksetup", "-setwebproxy", svc, host, str(port)],
                    check=False, **no_window_kwargs(),
                )
                subprocess.run(
                    ["networksetup", "-setsecurewebproxy", svc, host, str(port)],
                    check=False, **no_window_kwargs(),
                )
                subprocess.run(
                    ["networksetup", "-setsocksfirewallproxy", svc, host, str(port)],
                    check=False, **no_window_kwargs(),
                )
            else:
                for flag in (
                    "-setwebproxystate",
                    "-setsecurewebproxystate",
                    "-setsocksfirewallproxystate",
                ):
                    subprocess.run(
                        ["networksetup", flag, svc, "off"],
                        check=False, **no_window_kwargs(),
                    )

    def _linux_set(self, host: str, port: int, enable: bool):
        # GNOME
        if enable:
            subprocess.run(
                ["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"],
                check=False, **no_window_kwargs(),
            )
            for proto in ("http", "https", "socks"):
                subprocess.run(
                    ["gsettings", "set", f"org.gnome.system.proxy.{proto}", "host", host],
                    check=False, **no_window_kwargs(),
                )
                subprocess.run(
                    ["gsettings", "set", f"org.gnome.system.proxy.{proto}", "port", str(port)],
                    check=False, **no_window_kwargs(),
                )
        else:
            subprocess.run(
                ["gsettings", "set", "org.gnome.system.proxy", "mode", "none"],
                check=False, **no_window_kwargs(),
            )


SYS_PROXY = SystemProxy()


# ===================== process control =====================
def is_running() -> bool:
    if not PID_FILE.exists():
        return False
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        return False
    if is_windows():
        r = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True, text=True, **no_window_kwargs(),
        )
        return str(pid) in r.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def stop_core():
    try:
        SYS_PROXY.disable()
    except Exception:
        pass
    if not PID_FILE.exists():
        return
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        PID_FILE.unlink(missing_ok=True)
        return
    try:
        if is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True, **no_window_kwargs(),
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


def start_core(core: str, node: dict, settings: dict, log_cb=None):
    ensure_dirs()
    stop_core()

    if core == "xray":
        if settings.get("tun"):
            if log_cb:
                log_cb("TUN 目前仅 sing-box 支持，已忽略 TUN")
        binary = download_xray(log_cb)
        cfg = build_xray_config(node, settings)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [str(binary), "run", "-c", str(CONFIG_FILE)]
    else:
        binary = download_singbox(log_cb)
        cfg = build_singbox_config(node, settings)
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [str(binary), "run", "-c", str(CONFIG_FILE)]

    log_f = open(LOG_FILE, "w", encoding="utf-8", buffering=1)
    env = os.environ.copy()
    env.setdefault("ENABLE_DEPRECATED_TUN_ADDRESS_X", "true")
    env.setdefault("ENABLE_DEPRECATED_SPECIAL_OUTBOUNDS", "true")
    kwargs = {"stdout": log_f, "stderr": subprocess.STDOUT, "env": env, **no_window_kwargs()}
    proc = subprocess.Popen(cmd, **kwargs)
    PID_FILE.write_text(str(proc.pid), encoding="utf-8")
    time.sleep(0.8)
    if proc.poll() is not None:
        log_f.close()
        err = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-2500:]
        PID_FILE.unlink(missing_ok=True)
        raise RuntimeError(f"核心启动失败:\n{err}")

    port = int(settings.get("mixed_port") or MIXED_PORT)

    # 等待端口就绪（最多约 6 秒）
    ok = wait_port_open("127.0.0.1", port, tries=24, delay=0.25)
    if not ok:
        # 进程还在但端口未开 → 仍报错
        if proc.poll() is not None:
            log_f.close()
            err = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-2500:]
            PID_FILE.unlink(missing_ok=True)
            raise RuntimeError(f"核心已退出:\n{err}")
        if log_cb:
            log_cb(f"警告: 127.0.0.1:{port} 尚未就绪，请稍候或查看日志")

    # TUN 失败率高：未开 TUN 时默认开系统代理；开了 TUN 也尽量再开系统代理兜底
    want_proxy = settings.get("system_proxy") or not settings.get("tun")
    if want_proxy:
        try:
            SYS_PROXY.enable(port)
            if log_cb:
                log_cb(f"系统代理已设为 127.0.0.1:{port}")
        except Exception as e:
            if log_cb:
                log_cb(f"系统代理设置失败: {e}（可手动设置 127.0.0.1:{port}）")



def wait_port_open(host: str, port: int, tries: int = 20, delay: float = 0.25) -> bool:
    """等待本地端口开始监听。"""
    import socket
    for _ in range(tries):
        try:
            with socket.create_connection((host, int(port)), timeout=0.6):
                return True
        except OSError:
            time.sleep(delay)
    return False


def test_proxy_connectivity(port: int = MIXED_PORT, timeout: float = 5.0) -> tuple[bool, str]:
    """先检测本地端口，再经代理访问外网。"""
    import socket
    import urllib.request

    # 1) 端口是否在听（多等一会，避免刚启动误判）
    if not wait_port_open("127.0.0.1", port, tries=24, delay=0.25):
        # 再试 0.0.0.0 映射到本机的情况
        if not wait_port_open("127.0.0.1", port, tries=8, delay=0.3):
            return False, f"本地端口 127.0.0.1:{port} 未在监听（核心可能已退出，请看日志）"

    # 2) 经 HTTP 代理访问（不走环境变量代理，避免套娃）
    url = "http://www.gstatic.com/generate_204"
    proxy = f"http://127.0.0.1:{port}"
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    opener = urllib.request.build_opener(handler)
    try:
        with opener.open(url, timeout=timeout) as resp:
            code = getattr(resp, "status", None) or resp.getcode()
            if code in (204, 200):
                return True, f"代理连通正常 (HTTP {code})"
            return False, f"代理返回 HTTP {code}"
    except Exception as e:
        return False, f"端口已开但经代理访问失败（多为节点无效）: {e}"



def tcp_latency_ms(host: str, port: int, timeout: float = 3.0) -> int:
    """TCP 连接延迟（毫秒），失败返回 -1。"""
    import socket
    if not host or not port:
        return -1
    t0 = time.perf_counter()
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            pass
        return max(1, int((time.perf_counter() - t0) * 1000))
    except Exception:
        return -1


def measure_download_speed(proxy_port: int, timeout: float = 12.0) -> tuple[float, str]:
    """
    经本地 HTTP 代理下载一小段数据测速。
    返回 (KB/s, 说明)。失败 KB/s=0。
    """
    import urllib.request
    # Cloudflare 小文件 / 或 generate_204 仅测延迟不够，用 httpbin 或 gstatic
    url = "http://speed.cloudflare.com/__down?bytes=500000"  # 约 500KB
    proxy = f"http://127.0.0.1:{proxy_port}"
    handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
    opener = urllib.request.build_opener(handler)
    t0 = time.perf_counter()
    try:
        with opener.open(url, timeout=timeout) as resp:
            data = resp.read()
        dt = max(time.perf_counter() - t0, 0.001)
        kbps = len(data) / 1024.0 / dt
        return kbps, f"{kbps:.0f} KB/s ({len(data)/1024:.0f}KB)"
    except Exception as e:
        # 回退：仅测 HTTP 往返
        try:
            t1 = time.perf_counter()
            with opener.open("http://www.gstatic.com/generate_204", timeout=8) as resp:
                resp.read()
            ms = int((time.perf_counter() - t1) * 1000)
            return 0.0, f"可达 {ms}ms（测速文件失败: {e})"
        except Exception as e2:
            return 0.0, f"失败: {e2}"


def batch_test_nodes(nodes: list[dict], workers: int = 20) -> list[dict]:
    """多线程测试所有节点 TCP 延迟，写回 node['latency_ms']。"""
    indexed = [(i, n) for i, n in enumerate(nodes) if n.get("server")]

    def one(item):
        i, n = item
        ms = tcp_latency_ms(n.get("server", ""), int(n.get("port") or 0))
        return i, ms

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(one, it) for it in indexed]
        for fut in concurrent.futures.as_completed(futs):
            try:
                i, ms = fut.result()
                nodes[i]["latency_ms"] = ms
            except Exception:
                pass
    return nodes


def sort_nodes_by_latency(nodes: list[dict]) -> list[dict]:
    """按延迟从低到高排序；超时/失败在后，未测试更后。"""
    def key(n):
        if not n.get("server"):
            return (3, 10**9, "")
        ms = n.get("latency_ms")
        if ms is None:
            return (2, 10**9, n.get("name") or "")
        if not isinstance(ms, int) or ms < 0:
            return (1, 10**9, n.get("name") or "")
        return (0, ms, n.get("name") or "")
    nodes.sort(key=key)
    return nodes


# ===================== GUI =====================
class NetBridgeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"NetBridge {app_version()}")
        self.geometry("440x720")
        self.minsize(400, 640)
        self.configure(bg=BG)

        ensure_dirs()
        self.settings = load_settings()
        self.nodes: list[dict] = load_json(NODES_FILE, [])
        self.current_index = 0
        self.status = "disconnected"
        self.core_var = tk.StringVar(value=self.settings.get("core", "sing-box"))
        self.sysproxy_var = tk.BooleanVar(value=bool(self.settings.get("system_proxy", True)))
        self.tun_var = tk.BooleanVar(value=bool(self.settings.get("tun", False)))
        self.lan_var = tk.BooleanVar(value=bool(self.settings.get("allow_lan", False)))
        self.log_level_var = tk.StringVar(value=self.settings.get("log_level", "info"))
        self.upload = "0 B/s"
        self.download = "0 B/s"

        if not self.nodes:
            self.nodes = [{
                "name": "请添加节点或导入订阅",
                "protocol": "ss",
                "server": "",
                "port": 443,
                "password": "",
                "method": "aes-256-gcm",
                "network": "tcp",
            }]

        self._build_ui()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def current_node(self) -> dict:
        if not self.nodes:
            return {}
        self.current_index = max(0, min(self.current_index, len(self.nodes) - 1))
        return self.nodes[self.current_index]

    def _persist_nodes(self):
        save_json(NODES_FILE, [n for n in self.nodes if n.get("server")])

    def _persist_settings(self):
        self.settings["core"] = self.core_var.get()
        self.settings["system_proxy"] = self.sysproxy_var.get()
        self.settings["tun"] = self.tun_var.get()
        self.settings["allow_lan"] = self.lan_var.get()
        self.settings["log_level"] = self.log_level_var.get()
        save_settings(self.settings)

    def _build_ui(self):
        # core row
        bar = tk.Frame(self, bg=BG)
        bar.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(bar, text="核心", bg=BG, fg=SECONDARY).pack(side="left")
        ttk.Radiobutton(bar, text="sing-box", variable=self.core_var, value="sing-box",
                        command=self._persist_settings).pack(side="left", padx=4)
        ttk.Radiobutton(bar, text="Xray", variable=self.core_var, value="xray",
                        command=self._persist_settings).pack(side="left", padx=4)

        opt = tk.Frame(self, bg=BG)
        opt.pack(fill="x", padx=16, pady=(4, 0))
        ttk.Checkbutton(opt, text="系统代理", variable=self.sysproxy_var,
                        command=self._persist_settings).pack(side="left")
        ttk.Checkbutton(opt, text="TUN(需管理员)", variable=self.tun_var,
                        command=self._persist_settings).pack(side="left", padx=8)

        opt2 = tk.Frame(self, bg=BG)
        opt2.pack(fill="x", padx=16, pady=(2, 0))
        ttk.Checkbutton(opt2, text="允许局域网连接", variable=self.lan_var,
                        command=self._persist_settings).pack(side="left")
        tk.Label(opt2, text="日志", bg=BG, fg=SECONDARY).pack(side="left", padx=(12, 4))
        log_box = ttk.Combobox(
            opt2,
            textvariable=self.log_level_var,
            values=["trace", "debug", "info", "warn", "error"],
            width=8,
            state="readonly",
        )
        log_box.pack(side="left")
        log_box.bind("<<ComboboxSelected>>", lambda e: self._persist_settings())

        # node card
        top = tk.Frame(self, bg=CARD)
        top.pack(fill="x", padx=16, pady=(10, 6))
        self.lbl_node = tk.Label(top, text="", font=("Segoe UI", 14, "bold"), bg=CARD, cursor="hand2")
        self.lbl_node.pack(pady=(14, 2))
        self.lbl_sub = tk.Label(top, text="", font=("Segoe UI", 10), bg=CARD, fg=SECONDARY, cursor="hand2")
        self.lbl_sub.pack(pady=(0, 14))
        for w in (top, self.lbl_node, self.lbl_sub):
            w.bind("<Button-1>", lambda e: self._open_nodes())

        # connect button
        mid = tk.Frame(self, bg=BG)
        mid.pack(expand=True, fill="both")
        self.canvas = tk.Canvas(mid, width=180, height=180, bg=BG, highlightthickness=0)
        self.canvas.pack(expand=True)
        self.btn_id = self.canvas.create_oval(10, 10, 170, 170, fill=BLUE, outline="")
        self.txt_id = self.canvas.create_text(90, 90, text="连接", fill="white", font=("Segoe UI", 18, "bold"))
        self.canvas.bind("<Button-1>", lambda e: self._toggle())

        self.lbl_proxy = tk.Label(
            self, text="",
            font=("Segoe UI", 10), bg=BG, fg=SECONDARY,
        )
        self.lbl_proxy.pack()

        # bottom nav
        bottom = tk.Frame(self, bg=CARD)
        bottom.pack(fill="x", padx=16, pady=(10, 8))
        for text, cmd in [
            ("节点", self._open_nodes),
            ("订阅", self._import_sub_dialog),
            ("测试", self._test_nodes_dialog),
            ("添加", self._add_node_dialog),
            ("日志", self._show_log),
        ]:
            tk.Button(
                bottom, text=text, font=("Segoe UI", 10), bg=CARD, relief="flat",
                cursor="hand2", command=cmd, padx=8, pady=10,
            ).pack(side="left", expand=True)

        self.lbl_status = tk.Label(self, text="", font=("Segoe UI", 9), bg=BG, fg=SECONDARY, wraplength=400)
        self.lbl_status.pack(pady=(0, 10))

    def _refresh(self):
        n = self.current_node()
        name = n.get("name") or f"{n.get('server', '')}:{n.get('port', '')}"
        net = n.get("network") or "tcp"
        extra = net
        if n.get("reality"):
            extra += "+reality"
        elif n.get("tls"):
            extra += "+tls"
        self.lbl_node.config(text=name or "未选择节点")
        lat = n.get("latency_ms")
        lat_s = f" · {lat}ms" if isinstance(lat, int) and lat > 0 else (" · 超时" if lat == -1 else "")
        spd = n.get("speed_kbps")
        spd_s = f" · {spd:.0f}KB/s" if isinstance(spd, (int, float)) and spd > 0 else ""
        self.lbl_sub.config(
            text=f"{n.get('protocol', '?')} · {extra} · {n.get('server', '')}:{n.get('port', '')}{lat_s}{spd_s}"
        )
        colors = {"disconnected": BLUE, "connecting": ORANGE, "connected": GREEN, "error": RED}
        labels = {"disconnected": "连接", "connecting": "连接中", "connected": "已连接", "error": "重试"}
        self.canvas.itemconfig(self.btn_id, fill=colors.get(self.status, BLUE))
        self.canvas.itemconfig(self.txt_id, text=labels.get(self.status, "连接"))
        port = self.settings.get("mixed_port", MIXED_PORT)
        host = "0.0.0.0" if self.lan_var.get() else "127.0.0.1"
        mode = []
        if self.sysproxy_var.get() and not self.tun_var.get():
            mode.append("系统代理")
        if self.tun_var.get():
            mode.append("TUN")
        if self.lan_var.get():
            mode.append("局域网")
        mode_s = "+".join(mode) if mode else "仅本机"
        log_lv = self.log_level_var.get()
        self.lbl_proxy.config(text=f"{host}:{port} · {mode_s} · log={log_lv}")
        if self.status == "connected":
            self.lbl_status.config(text="已连接。若未开系统代理/TUN，请手动设置代理到上述地址。")
        elif self.status == "error":
            self.lbl_status.config(text="失败：点「日志」查看原因")
        else:
            bundled = (BIN_DIR / "sing-box.exe" if is_windows() else BIN_DIR / "sing-box").exists() or (BIN_DIR / "xray.exe" if is_windows() else BIN_DIR / "xray").exists()
            tip = "核心已内置" if bundled else "首次连接将下载核心"
            self.lbl_status.config(text=f"订阅/WS/gRPC/Reality · 系统代理/TUN · {tip}")

    def _toggle(self):
        if self.status == "connected":
            stop_core()
            self.status = "disconnected"
            self._refresh()
            return
        if self.status == "connecting":
            # 允许取消卡住的连接中状态
            try:
                stop_core()
            except Exception:
                pass
            self.status = "disconnected"
            self._refresh()
            return
        node = self.current_node()
        if not node.get("server"):
            messagebox.showwarning("提示", "请先添加节点或导入订阅")
            self._import_sub_dialog()
            return
        self._persist_settings()
        self.status = "connecting"
        self._refresh()

        def work():
            port = int(self.settings.get("mixed_port") or MIXED_PORT)
            try:
                def log(msg):
                    self.after(0, lambda m=msg: self.lbl_status.config(text=m))

                start_core(self.core_var.get(), node, self.settings, log)

                # 端口就绪即显示已连接，外网探测放到后台，避免一直「连接中」
                if wait_port_open("127.0.0.1", port, tries=20, delay=0.25):
                    self.status = "connected"
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"已连接 · 127.0.0.1:{port}"
                    ))
                    self.after(0, self._refresh)

                    def probe():
                        try:
                            ok, msg = test_proxy_connectivity(port, timeout=5.0)
                        except Exception as e:
                            ok, msg = False, str(e)

                        def ui():
                            if self.status != "connected":
                                return
                            if ok:
                                self.lbl_status.config(text=msg)
                            else:
                                self.lbl_status.config(text="已连接。外网探测: " + msg)
                        self.after(0, ui)

                    threading.Thread(target=probe, daemon=True).start()
                else:
                    self.status = "error"
                    self.after(0, lambda: messagebox.showwarning(
                        "无法上网",
                        f"本地端口 127.0.0.1:{port} 未在监听，请查看日志。",
                    ))
                    self.after(0, self._refresh)
            except Exception as e:
                self.status = "error"
                err = str(e)
                self.after(0, lambda m=err: messagebox.showerror("连接失败", m))
                self.after(0, self._refresh)

        threading.Thread(target=work, daemon=True).start()

    def _render_node_rows(self, frame, win):
        for w in frame.winfo_children():
            w.destroy()
        # 列表顺序与 self.nodes 一致（测试后已按延迟从低到高排列）
        for i in range(len(self.nodes)):
            n = self.nodes[i]
            if not n.get("server"):
                continue
            label = n.get("name") or f"{n.get('server')}:{n.get('port')}"
            net = n.get("network") or "tcp"
            lat = n.get("latency_ms")
            if lat is None:
                lat_s = "未测"
            elif lat < 0:
                lat_s = "超时"
            else:
                lat_s = f"{lat}ms"
            spd = n.get("speed_kbps")
            spd_s = f" | {spd:.0f}KB/s" if isinstance(spd, (int, float)) and spd > 0 else ""
            sub = f"{lat_s}{spd_s} · {n.get('protocol')} · {net} · {n.get('server')}:{n.get('port')}"

            def select(idx=i):
                self.current_index = idx
                self._refresh()
                win.destroy()

            row = tk.Frame(frame, bg=CARD)
            row.pack(fill="x", pady=2)
            tk.Button(
                row, text=f"{label}\n{sub}", font=("Segoe UI", 9), bg=CARD,
                relief="flat", anchor="w", justify="left", command=select, padx=8, pady=6,
            ).pack(fill="x")

    def _open_nodes(self):
        win = tk.Toplevel(self)
        win.title("节点列表")
        win.geometry("420x520")
        win.configure(bg=BG)
        head = tk.Frame(win, bg=BG)
        head.pack(fill="x", pady=8, padx=8)
        lbl = tk.Label(head, text=f"共 {len([n for n in self.nodes if n.get('server')])} 个节点",
                       bg=BG, font=("Segoe UI", 11, "bold"))
        lbl.pack(side="left")
        tk.Button(head, text="一键测试", bg=BLUE, fg="white", relief="flat",
                  padx=10, command=lambda: self._run_batch_test(win, frame, lbl)).pack(side="right")

        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg=BG)
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True, padx=8)
        scroll.pack(side="right", fill="y")
        self._render_node_rows(frame, win)

    def _run_batch_test(self, win, frame, lbl):
        valid = [n for n in self.nodes if n.get("server")]
        if not valid:
            messagebox.showwarning("提示", "没有可测试的节点")
            return
        lbl.config(text="测试中（多线程延迟）...")
        self.lbl_status.config(text="正在多线程测试节点延迟...")

        def work():
            batch_test_nodes(self.nodes, workers=20)
            # 记住当前选中节点，排序后恢复索引
            cur_id = id(self.current_node()) if self.nodes else None
            sort_nodes_by_latency(self.nodes)
            if cur_id is not None:
                for i, n in enumerate(self.nodes):
                    if id(n) == cur_id:
                        self.current_index = i
                        break
            else:
                self.current_index = 0
            self._persist_nodes()
            port = int(self.settings.get("mixed_port") or MIXED_PORT)
            if self.status == "connected":
                cur = self.current_node()
                kbps, msg = measure_download_speed(port)
                cur["speed_kbps"] = kbps
                cur["speed_msg"] = msg
            self._persist_nodes()

            def done():
                ok_n = sum(1 for n in self.nodes if isinstance(n.get("latency_ms"), int) and n["latency_ms"] > 0)
                fail_n = sum(1 for n in self.nodes if n.get("latency_ms") == -1)
                lbl.config(text=f"完成：可用 {ok_n} · 超时 {fail_n}")
                self.lbl_status.config(text=f"延迟测试完成：可用 {ok_n}，超时 {fail_n}")
                if frame.winfo_exists():
                    self._render_node_rows(frame, win)
                self._refresh()
            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def _test_nodes_dialog(self):
        """主界面一键测试入口。"""
        valid = [n for n in self.nodes if n.get("server")]
        if not valid:
            messagebox.showwarning("提示", "请先添加或导入节点")
            return
        self.lbl_status.config(text=f"正在测试 {len(valid)} 个节点延迟（多线程）...")
        self.status = self.status  # keep

        def work():
            batch_test_nodes(self.nodes, workers=20)
            sort_nodes_by_latency(self.nodes)
            # 自动选中延迟最低的可用节点（排序后一般为 index 0）
            best_i = None
            best_ms = 10**9
            for i, n in enumerate(self.nodes):
                ms = n.get("latency_ms")
                if isinstance(ms, int) and 0 < ms < best_ms:
                    best_ms = ms
                    best_i = i
            if best_i is not None:
                self.current_index = best_i
            else:
                self.current_index = 0
            msg_spd = ""
            if self.status == "connected":
                port = int(self.settings.get("mixed_port") or MIXED_PORT)
                kbps, msg = measure_download_speed(port)
                cur = self.current_node()
                cur["speed_kbps"] = kbps
                cur["speed_msg"] = msg
                msg_spd = f" · 当前节点 {msg}"
            self._persist_nodes()

            def done():
                ok_n = sum(1 for n in self.nodes if isinstance(n.get("latency_ms"), int) and n["latency_ms"] > 0)
                fail_n = sum(1 for n in self.nodes if n.get("latency_ms") == -1)
                self.lbl_status.config(text=f"测试完成：可用 {ok_n} · 超时 {fail_n}{msg_spd}")
                self._refresh()
                messagebox.showinfo(
                    "测试完成",
                    f"节点总数: {len(valid)}\n"
                    f"TCP 可用: {ok_n}\n"
                    f"超时: {fail_n}\n"
                    + (f"已自动选择最低延迟节点: {best_ms}ms\n" if best_i is not None else "")
                    + (f"当前节点测速: {self.current_node().get('speed_msg', '')}" if msg_spd else "\n测速需先连接成功后再点「测试」"),
                )
            self.after(0, done)

        threading.Thread(target=work, daemon=True).start()


    def _import_sub_dialog(self):
        win = tk.Toplevel(self)
        win.title("导入订阅 / 分享链接")
        win.geometry("460x360")
        win.configure(bg=BG)
        tk.Label(win, text="粘贴订阅 URL，或多行 ss/vmess/vless/trojan 链接", bg=BG).pack(pady=8)
        txt = scrolledtext.ScrolledText(win, height=12, font=("Consolas", 10))
        txt.pack(fill="both", expand=True, padx=12, pady=4)

        def do_import():
            content = txt.get("1.0", "end").strip()
            if not content:
                return
            try:
                if content.startswith("http://") or content.startswith("https://"):
                    self.lbl_status.config(text="正在拉取订阅...")
                    win.update()
                    nodes = fetch_subscription(content.split()[0])
                    # save sub url
                    subs = load_json(SUBS_FILE, [])
                    if content.split()[0] not in subs:
                        subs.append(content.split()[0])
                        save_json(SUBS_FILE, subs)
                else:
                    nodes = parse_subscription_content(content)
                if not nodes:
                    messagebox.showwarning("结果", "未解析到任何节点")
                    return
                # merge by server:port:proto
                existing = {
                    f"{n.get('server')}:{n.get('port')}:{n.get('protocol')}"
                    for n in self.nodes if n.get("server")
                }
                added = 0
                for n in nodes:
                    key = f"{n.get('server')}:{n.get('port')}:{n.get('protocol')}"
                    if key in existing:
                        continue
                    self.nodes.append(n)
                    existing.add(key)
                    added += 1
                self.nodes = [n for n in self.nodes if n.get("server")]
                self._persist_nodes()
                if self.nodes:
                    self.current_index = 0
                self._refresh()
                messagebox.showinfo("完成", f"导入 {len(nodes)} 个，新增 {added} 个")
                win.destroy()
            except Exception as e:
                messagebox.showerror("导入失败", str(e))

        tk.Button(win, text="导入", command=do_import, padx=16, pady=6).pack(pady=10)

    def _add_node_dialog(self):
        win = tk.Toplevel(self)
        win.title("手动添加节点")
        win.geometry("400x520")
        win.configure(bg=BG)
        fields = {}
        specs = [
            ("名称", "name", ""),
            ("协议(ss/vmess/vless/trojan/socks)", "protocol", "vless"),
            ("服务器", "server", ""),
            ("端口", "port", "443"),
            ("密码/UUID", "password", ""),
            ("传输(tcp/ws/grpc)", "network", "tcp"),
            ("路径 path", "path", ""),
            ("Host", "host", ""),
            ("SNI", "sni", ""),
            ("TLS(true/false)", "tls", "true"),
            ("Reality(true/false)", "reality", "false"),
            ("Reality公钥 pbk", "pbk", ""),
            ("Reality短ID sid", "sid", ""),
            ("指纹 fp", "fp", "chrome"),
            ("gRPC serviceName", "service_name", ""),
            ("SS加密 method", "method", "aes-256-gcm"),
            ("flow", "flow", ""),
        ]
        form = tk.Frame(win, bg=BG)
        form.pack(fill="both", expand=True, padx=10, pady=8)
        for i, (lab, key, default) in enumerate(specs):
            tk.Label(form, text=lab, bg=BG, anchor="w", font=("Segoe UI", 9)).grid(row=i, column=0, sticky="w")
            ent = tk.Entry(form, width=28)
            ent.insert(0, default)
            ent.grid(row=i, column=1, pady=2, sticky="e")
            fields[key] = ent

        def save():
            try:
                port = int(fields["port"].get().strip() or "443")
            except ValueError:
                messagebox.showerror("错误", "端口必须是数字")
                return
            tls_s = fields["tls"].get().strip().lower()
            reality_s = fields["reality"].get().strip().lower()
            node = {
                "name": fields["name"].get().strip() or fields["server"].get().strip(),
                "protocol": fields["protocol"].get().strip().lower() or "ss",
                "server": fields["server"].get().strip(),
                "port": port,
                "password": fields["password"].get().strip(),
                "uuid": fields["password"].get().strip(),
                "network": fields["network"].get().strip().lower() or "tcp",
                "path": fields["path"].get().strip(),
                "host": fields["host"].get().strip(),
                "sni": fields["sni"].get().strip(),
                "tls": tls_s in ("1", "true", "yes"),
                "reality": reality_s in ("1", "true", "yes"),
                "pbk": fields["pbk"].get().strip(),
                "sid": fields["sid"].get().strip(),
                "fp": fields["fp"].get().strip() or "chrome",
                "service_name": fields["service_name"].get().strip(),
                "method": fields["method"].get().strip() or "aes-256-gcm",
                "flow": fields["flow"].get().strip(),
            }
            if node["reality"]:
                node["tls"] = True
            if not node["server"]:
                messagebox.showerror("错误", "服务器不能为空")
                return
            self.nodes = [n for n in self.nodes if n.get("server")]
            self.nodes.append(node)
            self._persist_nodes()
            self.current_index = len(self.nodes) - 1
            self._refresh()
            win.destroy()

        tk.Button(win, text="保存", command=save, padx=16, pady=6).pack(pady=8)

    def _show_log(self):
        win = tk.Toplevel(self)
        win.title("日志 / 路径")
        win.geometry("520x420")
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9))
        txt.pack(fill="both", expand=True)
        info = (
            f"核心目录: {BIN_DIR}\n"
            f"配置: {CONFIG_FILE}\n"
            f"日志: {LOG_FILE}\n"
            f"节点: {NODES_FILE}\n\n"
            "--- core.log ---\n"
        )
        txt.insert("end", info)
        if LOG_FILE.exists():
            txt.insert("end", LOG_FILE.read_text(encoding="utf-8", errors="replace")[-5000:])
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
