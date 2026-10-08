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
try:
    import winsound
except Exception:
    winsound = None
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

try:
    import pystray
    from PIL import Image, ImageDraw, ImageTk
    HAS_TRAY = True
    HAS_PIL = True
except Exception:
    pystray = None
    HAS_TRAY = False

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
APP_VERSION = "1.1.8"

def app_version() -> str:
    """界面/UA 版本；与下方 APP_VERSION、README 徽章保持一致即可。"""
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
SKINS = {
    "羽毛渐变": {"bg": "#C9B8F0", "card": "#FFFFFF", "accent": "#7C3AED", "text": "#1E1B4B", "secondary": "#5B5675", "btn": "#7C3AED", "btn_fg": "#FFFFFF", "gradient": True},
    "清新蓝": {"bg": "#E8F1FF", "card": "#FFFFFF", "accent": "#007AFF", "text": "#0A1628", "secondary": "#5B6B7C", "btn": "#007AFF", "btn_fg": "#FFFFFF"},
    "暗夜灰": {"bg": "#1C1C1E", "card": "#2C2C2E", "accent": "#0A84FF", "text": "#F5F5F7", "secondary": "#8E8E93", "btn": "#0A84FF", "btn_fg": "#FFFFFF"},
    "薄荷绿": {"bg": "#E8F8F0", "card": "#FFFFFF", "accent": "#34C759", "text": "#0A2818", "secondary": "#5A7A68", "btn": "#34C759", "btn_fg": "#FFFFFF"},
    "暮橙": {"bg": "#FFF1E6", "card": "#FFFFFF", "accent": "#FF9F0A", "text": "#2A1A0A", "secondary": "#8A7040", "btn": "#FF9F0A", "btn_fg": "#FFFFFF"},
    "紫霞": {"bg": "#F3E8FF", "card": "#FFFFFF", "accent": "#BF5AF2", "text": "#1A0A28", "secondary": "#7A6A8A", "btn": "#BF5AF2", "btn_fg": "#FFFFFF"},
}

DEFAULT_SETTINGS = {
    "core": "sing-box",
    "system_proxy": True,
    "tun": False,
    "mixed_port": MIXED_PORT,
    "allow_lan": False,
    "log_level": "info",
    "skin": "羽毛渐变",
    "font_size": 10,
    "auto_update_check": True,
    "group_filter": "全部",
    "route_mode": "bypass_cn",  # bypass_cn | global | direct
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


def alert_error():
    """错误提示音。"""
    try:
        if is_windows() and winsound is not None:
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        else:
            print("\a", end="", flush=True)
    except Exception:
        pass


RELEASES_PAGE = "https://github.com/Cuarentas/NetBridge/releases"
RELEASES_API = "https://api.github.com/repos/Cuarentas/NetBridge/releases/latest"
RELEASES_API_MIRRORS = [
    RELEASES_API,
    "https://ghproxy.net/https://api.github.com/repos/Cuarentas/NetBridge/releases/latest",
    "https://mirror.ghproxy.com/https://api.github.com/repos/Cuarentas/NetBridge/releases/latest",
    "https://gh.ddlc.top/https://api.github.com/repos/Cuarentas/NetBridge/releases/latest",
]


def _norm_ver(v: str) -> list:
    parts = []
    for x in re.split(r"[^0-9]+", (v or "").lstrip("vV")):
        if x.isdigit():
            parts.append(int(x))
    return parts or [0]


def _http_get_json(url: str, timeout: float = 12.0) -> dict:
    """GET JSON：先直连，失败再走本地混合代理。"""
    headers = {
        "User-Agent": f"NetBridge/{APP_VERSION}",
        "Accept": "application/vnd.github+json",
    }
    port = MIXED_PORT
    try:
        if SETTINGS_FILE.exists():
            s = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            port = int(s.get("mixed_port") or MIXED_PORT)
    except Exception:
        pass
    proxy_url = f"http://127.0.0.1:{port}"
    errors = []
    for mode in ("direct", "proxy"):
        try:
            if mode == "direct":
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            else:
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
                )
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            errors.append(f"{mode}:{e}")
    raise RuntimeError("; ".join(errors[-4:]))


def check_github_update(timeout: float = 12.0):
    """返回 (有更新, 消息, release或None)。"""
    last_err = ""
    data = None
    for url in RELEASES_API_MIRRORS:
        try:
            data = _http_get_json(url, timeout=timeout)
            if data and data.get("tag_name"):
                break
        except Exception as e:
            last_err = str(e)
            data = None
    if not data:
        return False, f"无法连接 GitHub 检查更新。\n{last_err}\n\n可手动打开:\n{RELEASES_PAGE}", None
    tag = (data.get("tag_name") or "").lstrip("vV")
    if not tag:
        return False, "无法解析最新版本号", data
    if _norm_ver(tag) > _norm_ver(APP_VERSION):
        return True, f"发现新版本 v{tag}（当前 v{APP_VERSION}）", data
    return False, f"已是最新版本（v{APP_VERSION}）", data


def find_windows_asset(release) -> str | None:
    if not release:
        return None
    for a in release.get("assets") or []:
        name = (a.get("name") or "").lower()
        if "windows" in name and name.endswith(".zip") and a.get("browser_download_url"):
            return a["browser_download_url"]
    for a in release.get("assets") or []:
        if (a.get("name") or "").endswith(".zip") and a.get("browser_download_url"):
            return a["browser_download_url"]
    return release.get("html_url") or RELEASES_PAGE


def open_in_browser(url: str):
    try:
        import webbrowser
        webbrowser.open(url)
        return
    except Exception:
        pass
    try:
        if is_windows():
            os.startfile(url)  # type: ignore
    except Exception:
        pass


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



def asset_path(*names: str) -> Path | None:
    """查找资源：优先 assets/ 子目录，再程序目录。"""
    bases = []
    if getattr(sys, "frozen", False):
        bases.append(Path(sys.executable).resolve().parent)
        bases.append(Path(sys.executable).resolve().parent / "assets")
    bases.append(Path(__file__).resolve().parent)
    bases.append(Path(__file__).resolve().parent / "assets")
    bases.append(ROOT)
    bases.append(ROOT / "assets")
    for b in bases:
        for n in names:
            c = b / n
            if c.is_file():
                return c
    return None

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



def ensure_xray_geo(log=None, timeout: float = 8.0):
    """可选下载 geo 数据。失败/超时不阻塞连接（已有域名分流回退）。"""
    files = {
        "geoip.dat": "https://github.com/v2fly/geoip/releases/latest/download/geoip.dat",
        "geosite.dat": "https://github.com/v2fly/domain-list-community/releases/latest/download/dlc.dat",
    }
    ok = False
    for name, url in files.items():
        dest = BIN_DIR / name
        if dest.exists() and dest.stat().st_size > 10000:
            ok = True
            continue
        try:
            if log:
                log(f"可选下载 {name}（最多 {int(timeout)}s，失败可跳过）...")
            req = urllib.request.Request(url, headers={"User-Agent": f"NetBridge/{APP_VERSION}"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
            if len(data) > 10000:
                dest.write_bytes(data)
                ok = True
        except Exception as e:
            if log:
                log(f"{name} 跳过: {e}")
    return ok


def ensure_xray_geo_async(log=None):
    """后台下载 geo，不阻塞 start_core。"""
    def work():
        try:
            ensure_xray_geo(log, timeout=15.0)
        except Exception:
            pass
    threading.Thread(target=work, daemon=True).start()


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
        net = (q.get("type") or q.get("network") or ["tcp"])[0].lower()
        path = urllib.parse.unquote((q.get("path") or ["/"])[0] or "/")
        host = (q.get("host") or [""])[0]
        sni = (q.get("sni") or q.get("peer") or [""])[0]
        # 与 v2rayN 一致：ws 时 host 缺省用 sni
        if net in ("ws", "websocket") and not host and sni:
            host = sni
        if not sni:
            sni = host or (p.hostname or "")
        allow = (q.get("allowInsecure") or q.get("allow_insecure") or q.get("insecure") or ["1"])[0]
        node = {
            "name": name,
            "protocol": "trojan",
            "server": p.hostname or "",
            "port": p.port or 443,
            "password": urllib.parse.unquote(p.username or ""),
            "network": net,
            "tls": True,
            "sni": sni,
            "path": path if path.startswith("/") else ("/" + path),
            "host": host,
            "service_name": (q.get("serviceName") or q.get("service_name") or [""])[0],
            "fp": (q.get("fp") or ["chrome"])[0],
            "alpn": (q.get("alpn") or [""])[0],
            "allow_insecure": str(allow).lower() in ("1", "true", "yes"),
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
        # Clash Meta 扁平字段 / ws-opts
        if (d.get("network") or "").lower() in ("ws", "websocket"):
            node["network"] = "ws"
        if d.get("path"):
            node["path"] = d.get("path") or ""
        if d.get("host") or d.get("ws-host"):
            node["host"] = d.get("host") or d.get("ws-host") or ""
        # 简单解析 ws-opts: { path: /xx, headers: { Host: yy } }
        wo = d.get("ws-opts") or ""
        if "path" in d and not node.get("path"):
            node["path"] = d.get("path") or ""
        if isinstance(wo, str) and wo:
            pm = re.search(r"path:\s*['\"]?([^'\"\s}]+)", wo)
            if pm:
                node["path"] = pm.group(1)
            hm = re.search(r"Host:\s*['\"]?([^'\"\s}]+)", wo)
            if hm:
                node["host"] = hm.group(1)
        if (d.get("type") or "").lower() == "trojan":
            node["tls"] = True
            node["allow_insecure"] = True
            if not node.get("sni"):
                node["sni"] = d.get("sni") or d.get("servername") or node.get("host") or ""
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



# 精简版国内域名后缀（无 geo 文件时的回退规则，对齐常见客户端「绕过大陆」）
CN_DOMAIN_SUFFIX = [
    "cn", "baidu.com", "qq.com", "weixin.qq.com", "gtimg.com", "qcloud.com",
    "aliyun.com", "alicdn.com", "taobao.com", "tmall.com", "alipay.com",
    "jd.com", "360buyimg.com", "163.com", "126.com", "yeah.net",
    "sina.com.cn", "weibo.com", "bilibili.com", "hdslb.com", "zhihu.com",
    "douyin.com", "bytedance.com", "byteimg.com", "iqiyi.com", "youku.com",
    "microsoft.com", "windows.net", "live.com", "office.com", "msftconnecttest.com",
    "apple.com", "icloud.com", "cdn-apple.com", "mzstatic.com",
    "huawei.com", "honor.com", "mi.com", "xiaomi.com", "miui.com",
    "360.cn", "360.com", "qy.net", "hao123.com", "so.com", "csdn.net", "oschina.net", "gitee.com",
    "douban.com", "acfun.cn", "iqiyi.com", "pptv.com", "mgtv.com",
    "cctv.com", "gov.cn", "edu.cn", "org.cn", "com.cn", "net.cn",
]


def windows_proxy_override(route_mode: str = "bypass_cn") -> str:
    """系统代理绕过列表：绕过大陆时国内域名不进本地代理。"""
    base = ["localhost", "127.*", "10.*", "192.168.*", "172.16.*", "172.17.*", "172.18.*", "172.19.*", "172.2*", "172.3*", "<local>"]
    if route_mode == "bypass_cn":
        # 浏览器侧直连国内，不经过 7890
        extra = ["*.cn", "*.baidu.com", "*.qq.com", "*.tencent.com", "*.aliyun.com", "*.taobao.com",
                 "*.aliyuncs.com", "*.163.com", "*.126.com", "*.bilibili.com", "*.hdslb.com",
                 "*.zhihu.com", "*.jd.com", "*.360.com", "*.360.cn", "*.mi.com", "*.xiaomi.com",
                 "*.msftconnecttest.com", "*.microsoft.com", "*.windowsupdate.com",
                 "*.apple.com", "*.icloud.com", "*.gov.cn", "*.edu.cn"]
        base.extend(extra)
    return ";".join(base)


def _route_mode(settings: dict) -> str:

    m = (settings.get("route_mode") or "bypass_cn").lower()
    if m in ("bypass_cn", "global", "direct"):
        return m
    return "bypass_cn"


# ===================== config builders (WS/gRPC/Reality) =====================

def normalize_node(node: dict) -> dict:
    """补齐与 v2rayN 一致的默认字段，修复订阅导入缺项。"""
    n = dict(node)
    proto = (n.get("protocol") or "").lower()
    net = (n.get("network") or "tcp").lower()
    if net in ("websocket",):
        net = "ws"
        n["network"] = "ws"
    if proto == "trojan":
        n["tls"] = True
        if n.get("allow_insecure") is None:
            n["allow_insecure"] = True
    if net == "ws":
        if not n.get("path"):
            n["path"] = "/"
        if not n.get("host") and n.get("sni"):
            n["host"] = n["sni"]
        if not n.get("sni") and n.get("host"):
            n["sni"] = n["host"]
    if not n.get("sni") and n.get("tls"):
        n["sni"] = n.get("host") or n.get("server") or ""
    if not n.get("fp") and (n.get("tls") or proto == "trojan"):
        n["fp"] = "chrome"
    return n


def _sb_tls(node: dict) -> dict | None:
    proto = (node.get("protocol") or "").lower()
    # trojan 本身就是 TLS；ws/grpc 的 vless/vmess 常开 TLS
    if not (node.get("tls") or node.get("reality") or proto == "trojan"):
        return None
    tls: dict = {
        "enabled": True,
        "server_name": node.get("sni") or node.get("host") or node.get("server") or "",
        # 多数机场节点证书与 IP 不一致，默认允许不安全（与 v2rayN 常见设置一致）
        "insecure": True if node.get("allow_insecure", True) else False,
    }
    if node.get("fp"):
        tls["utls"] = {"enabled": True, "fingerprint": node["fp"]}
    if node.get("alpn"):
        alpn = node["alpn"]
        tls["alpn"] = [a.strip() for a in str(alpn).split(",") if a.strip()]
    if node.get("reality"):
        tls["reality"] = {
            "enabled": True,
            "public_key": node.get("pbk") or "",
            "short_id": node.get("sid") or "",
        }
        tls["insecure"] = False
    return tls


def _sb_transport(node: dict) -> dict | None:
    net = (node.get("network") or "tcp").lower()
    if net in ("ws", "websocket"):
        t = {"type": "ws", "path": node.get("path") or "/"}
        host = node.get("host") or node.get("sni") or ""
        if host:
            t["headers"] = {"Host": host}
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
    node = normalize_node(node)
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

    # HTTPS CONNECT 依赖 DNS；避免 DNS 全走代理导致解析卡死
    outbound.setdefault("domain_strategy", "prefer_ipv4")
    cfg = {
        "log": {"level": log_level, "timestamp": True},
        "dns": {
            "servers": [
                {"tag": "local", "address": "local", "detour": "direct"},
                {"tag": "google", "address": "8.8.8.8", "detour": "proxy"},
                {"tag": "cf", "address": "1.1.1.1", "detour": "proxy"},
            ],
            "rules": [
                {"domain_suffix": ["google.com", "googleapis.com", "gstatic.com", "youtube.com", "googlevideo.com", "cloudflare.com", "ytimg.com"], "server": "google"},
            ],
            "final": "local",
            "strategy": "prefer_ipv4",
            "independent_cache": True,
        },
        "inbounds": inbounds,
        "outbounds": [
            outbound,
            {"type": "direct", "tag": "direct"},
        ],
        "route": _singbox_route(_route_mode(settings)),
    }
    # mixed 入站开启嗅探，利于 HTTPS
    for ib in cfg["inbounds"]:
        if ib.get("type") in ("mixed", "socks", "http"):
            ib["sniff"] = True
            ib["sniff_override_destination"] = True
    return cfg


def _singbox_route(mode: str) -> dict:
    """sing-box 路由：绕过大陆 / 全局 / 全直连。"""
    if mode == "direct":
        return {"auto_detect_interface": True, "final": "direct"}
    if mode == "global":
        return {
            "auto_detect_interface": True,
            "final": "proxy",
            "rules": [
                {"ip_is_private": True, "outbound": "direct"},
            ],
        }
    # bypass_cn：局域网与国内域名直连，其余走代理
    return {
        "auto_detect_interface": True,
        "final": "proxy",
        "rules": [
            {"ip_is_private": True, "outbound": "direct"},
            {"domain_suffix": CN_DOMAIN_SUFFIX, "outbound": "direct"},
            {"domain_keyword": ["baidu", "alipay", "weixin", "qq.com"], "outbound": "direct"},
        ],
    }


def _xray_stream(node: dict) -> dict:
    net = (node.get("network") or "tcp").lower()
    proto = (node.get("protocol") or "").lower()
    stream: dict = {"network": "tcp"}

    if net in ("ws", "websocket"):
        stream["network"] = "ws"
        ws: dict = {"path": node.get("path") or "/"}
        # Xray 25+：使用独立 host，避免 headers.Host 弃用警告
        host = node.get("host") or node.get("sni") or ""
        if host:
            ws["host"] = host
        stream["wsSettings"] = ws
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

    # trojan / vless + ws/grpc 默认开 TLS
    need_tls = bool(node.get("tls") or node.get("reality"))
    if not need_tls and net in ("ws", "websocket", "grpc") and proto in ("trojan", "vless", "vmess"):
        need_tls = True

    if node.get("reality"):
        stream["security"] = "reality"
        stream["realitySettings"] = {
            "serverName": node.get("sni") or node.get("host") or node.get("server") or "",
            "fingerprint": node.get("fp") or "chrome",
            "publicKey": node.get("pbk") or "",
            "shortId": node.get("sid") or "",
            "spiderX": node.get("spx") or "",
        }
    elif need_tls:
        stream["security"] = "tls"
        # 默认 allowInsecure=True，对齐 v2rayN 常见可用配置
        allow = node.get("allow_insecure")
        if allow is None:
            allow = True
        tls: dict = {
            "serverName": node.get("sni") or node.get("host") or node.get("server") or "",
            "allowInsecure": bool(allow),
        }
        if node.get("fp"):
            tls["fingerprint"] = node["fp"]
        # 不强制 ALPN http/1.1，减少 Xray 25 弃用警告；由核心自行协商
        if node.get("alpn"):
            tls["alpn"] = [a.strip() for a in str(node["alpn"]).split(",") if a.strip()]
        stream["tlsSettings"] = tls

    return stream


def build_xray_config(node: dict, settings: dict) -> dict:
    node = normalize_node(node)
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
        "routing": _xray_routing(_route_mode(settings)),
    }


def _xray_routing(mode: str) -> dict:
    if mode == "direct":
        return {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "network": "tcp,udp", "outboundTag": "direct"}],
        }
    rules = [
        {"type": "field", "ip": ["geoip:private"], "outboundTag": "direct"},
    ]
    if mode == "bypass_cn":
        # 有 geo 数据时用官方规则；无则用域名后缀回退
        rules.append({"type": "field", "ip": ["geoip:cn"], "outboundTag": "direct"})
        rules.append({"type": "field", "domain": ["geosite:cn"], "outboundTag": "direct"})
        rules.append({
            "type": "field",
            "domain": [("domain:" + d) for d in CN_DOMAIN_SUFFIX if "." in d or d == "cn"],
            "outboundTag": "direct",
        })
    if mode == "global":
        pass
    return {"domainStrategy": "IPIfNonMatch", "rules": rules}


# ===================== system proxy =====================
class SystemProxy:
    """Best-effort system HTTP(S) proxy. TUN is handled by core config."""

    def __init__(self):
        self._enabled = False
        self._port = MIXED_PORT

    def enable(self, port: int = MIXED_PORT, route_mode: str = "bypass_cn"):
        self._port = port
        self._route_mode = route_mode or "bypass_cn"
        host = "127.0.0.1"
        try:
            if is_windows():
                self._win_set(host, port, True, getattr(self, "_route_mode", "bypass_cn"))
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
                self._win_set("127.0.0.1", self._port, False, "global")
            elif is_mac():
                self._mac_set("127.0.0.1", self._port, False)
            else:
                self._linux_set("127.0.0.1", self._port, False)
        except Exception:
            pass
        self._enabled = False

    def _win_set(self, host: str, port: int, enable: bool, route_mode: str = "bypass_cn"):
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
                winreg.SetValueEx(key, "ProxyOverride", 0, winreg.REG_SZ, windows_proxy_override(route_mode))
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
        # WinHTTP 较慢，放到后台，避免拖慢「连接」
        def _wh():
            try:
                if enable:
                    subprocess.run(
                        ["netsh", "winhttp", "set", "proxy", f"{host}:{port}"],
                        capture_output=True, timeout=3, **no_window_kwargs(),
                    )
                else:
                    subprocess.run(
                        ["netsh", "winhttp", "reset", "proxy"],
                        capture_output=True, timeout=3, **no_window_kwargs(),
                    )
            except Exception:
                pass
        try:
            threading.Thread(target=_wh, daemon=True).start()
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


def _pids_on_port(port: int) -> list[int]:
    """查找占用指定本地端口的 PID（Windows netstat）。"""
    pids = []
    try:
        if is_windows():
            r = subprocess.run(
                ["netstat", "-ano", "-p", "tcp"],
                capture_output=True, text=True, **no_window_kwargs(),
            )
            for line in (r.stdout or "").splitlines():
                line = line.strip()
                if f":{port}" not in line:
                    continue
                if "LISTENING" not in line.upper() and "监听" not in line:
                    # 仍匹配 LISTENING
                    if "LISTEN" not in line.upper():
                        continue
                parts = line.split()
                if not parts:
                    continue
                try:
                    pid = int(parts[-1])
                    if pid > 0 and pid not in pids:
                        pids.append(pid)
                except ValueError:
                    pass
        else:
            r = subprocess.run(
                ["ss", "-lptn", f"sport = :{port}"],
                capture_output=True, text=True,
            )
            for m in re.finditer(r"pid=(\d+)", r.stdout or ""):
                pids.append(int(m.group(1)))
    except Exception:
        pass
    return pids


def _kill_pid(pid: int):
    try:
        if is_windows():
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True, **no_window_kwargs(),
            )
        else:
            os.kill(pid, signal.SIGKILL)
    except Exception:
        pass


def free_listen_port(port: int, log_cb=None):
    """释放端口占用（旧核心残留是 7890 bind 失败的主因）。"""
    for pid in _pids_on_port(port):
        if log_cb:
            log_cb(f"释放端口 {port}，结束 PID={pid}")
        _kill_pid(pid)
    # 再清一次常见核心进程名（防止 PID 文件丢失）
    if is_windows():
        for name in ("xray.exe", "sing-box.exe", "singbox.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/IM", name, "/F", "/T"],
                    capture_output=True, **no_window_kwargs(),
                )
            except Exception:
                pass
    time.sleep(0.35)


def stop_core():
    try:
        SYS_PROXY.disable()
    except Exception:
        pass
    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
        except Exception:
            pass
    if pid:
        _kill_pid(pid)
    # 默认混合口 + socks 口
    try:
        port = MIXED_PORT
        if SETTINGS_FILE.exists():
            port = int(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")).get("mixed_port") or MIXED_PORT)
    except Exception:
        port = MIXED_PORT
    free_listen_port(port)
    free_listen_port(port + 1)
    PID_FILE.unlink(missing_ok=True)


def start_core(core: str, node: dict, settings: dict, log_cb=None):
    ensure_dirs()
    stop_core()
    port = int(settings.get("mixed_port") or MIXED_PORT)
    # 启动前再确保端口空闲
    free_listen_port(port, log_cb)
    free_listen_port(port + 1, log_cb)

    # 核心日志至少 info，否则界面选 error 时看不到 started，会误判失败
    settings = dict(settings)
    lv = (settings.get("log_level") or "info").lower()
    if lv in ("warn", "error", "fatal", "panic"):
        settings["log_level"] = "info"

    if core == "xray":
        if settings.get("tun") and log_cb:
            log_cb("TUN 目前仅 sing-box 支持，已忽略 TUN")
        binary = download_xray(log_cb)
        # geo 不阻塞连接；已有 domain 规则回退
        try:
            ensure_xray_geo_async(log_cb)
        except Exception:
            pass
        cfg = build_xray_config(node, settings)
    else:
        binary = download_singbox(log_cb)
        cfg = build_singbox_config(node, settings)

    binary = Path(binary)
    if not binary.is_file() or binary.stat().st_size < 1000:
        raise RuntimeError(f"核心文件无效或不存在:\n{binary}\n请重新下载发布包或检查网络后重试连接。")

    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    cmd = [str(binary.resolve()), "run", "-c", str(CONFIG_FILE.resolve())]

    log_f = open(LOG_FILE, "w", encoding="utf-8", buffering=1)
    log_f.write(f"NetBridge {app_version()} starting\n")
    log_f.write(f"cmd: {' '.join(cmd)}\n")
    log_f.write(f"bin exists: {binary.is_file()} size={binary.stat().st_size}\n")
    log_f.flush()

    env = os.environ.copy()
    env.setdefault("ENABLE_DEPRECATED_TUN_ADDRESS_X", "true")
    env.setdefault("ENABLE_DEPRECATED_SPECIAL_OUTBOUNDS", "true")
    kwargs = {
        "stdout": log_f,
        "stderr": subprocess.STDOUT,
        "env": env,
        "cwd": str(binary.parent),
        **no_window_kwargs(),
    }
    try:
        proc = subprocess.Popen(cmd, **kwargs)
    except Exception as e:
        log_f.write(f"Popen failed: {e}\n")
        log_f.close()
        raise RuntimeError(f"无法启动核心进程: {e}")

    PID_FILE.write_text(str(proc.pid), encoding="utf-8")

    # 等待启动：进程存活即可（约 0.8s 内判断）
    for _ in range(8):
        time.sleep(0.1)
        if proc.poll() is not None:
            break
        if wait_port_open("127.0.0.1", int(settings.get("mixed_port") or MIXED_PORT), tries=1, delay=0):
            break

    port = int(settings.get("mixed_port") or MIXED_PORT)

    if proc.poll() is not None:
        log_f.flush()
        try:
            log_f.close()
        except Exception:
            pass
        err = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-3000:]
        PID_FILE.unlink(missing_ok=True)
        hint = ""
        if "Only one usage" in err or "address already in use" in err.lower():
            hint = "\n\n【原因】端口被占用。请关闭其它代理软件，或在任务管理器结束 xray.exe / sing-box.exe 后重试。"
        raise RuntimeError(f"核心启动失败（进程已退出）:\n{err}{hint}")

    # 进程仍在 → 视为启动成功（不依赖日志里的 started 字样）
    if log_cb:
        log_cb(f"核心进程已运行 PID={proc.pid}")

    want_proxy = settings.get("system_proxy") or not settings.get("tun")
    if want_proxy:
        try:
            SYS_PROXY.enable(port, route_mode=str(settings.get("route_mode") or "bypass_cn"))
            if log_cb:
                log_cb(f"系统代理已设为 127.0.0.1:{port}")
        except Exception as e:
            if log_cb:
                log_cb(f"系统代理设置失败: {e}（请手动设 127.0.0.1:{port}）")




def log_says_core_started() -> bool:
    """core.log 是否已出现 started（比 TCP 探测更可靠）。"""
    try:
        if not LOG_FILE.exists():
            return False
        tail = LOG_FILE.read_text(encoding="utf-8", errors="replace")[-3000:]
        return ("started" in tail) or ("tcp server started" in tail)
    except Exception:
        return False


def wait_port_open(host: str, port: int, tries: int = 8, delay: float = 0.12) -> bool:
    """等待本地端口开始监听。"""
    import socket
    for _ in range(tries):
        try:
            with socket.create_connection((host, int(port)), timeout=0.6):
                return True
        except OSError:
            time.sleep(delay)
    return False


def test_proxy_connectivity(port: int = MIXED_PORT, timeout: float = 3.0) -> tuple[bool, str]:
    """先检测本地端口，再经代理访问外网。"""
    import socket
    import urllib.request

    # 1) 端口探测；失败时若日志已 started 则继续（避免 Windows 误报）
    port_ok = wait_port_open("127.0.0.1", port, tries=6, delay=0.15)
    if not port_ok and not log_says_core_started():
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



def make_tray_image():
    """托盘图标：优先使用应用图标文件。"""
    for name in ("netbridge_tray.png", "netbridge.png"):
        c = asset_path(name)
        if c:
            try:
                return Image.open(c).convert("RGBA").resize((64, 64))
            except Exception:
                pass
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, size - 4, size - 4), fill=(0, 122, 255, 255))
    d.ellipse((18, 14, size - 18, size - 18), fill=(255, 255, 255, 235))
    return img


# ===================== GUI =====================
class NetBridgeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"NetBridge {APP_VERSION}")
        self.geometry("460x760")
        self.minsize(420, 680)
        self.configure(bg=BG)
        self._set_window_icon()

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
        self.skin_var = tk.StringVar(value=self.settings.get("skin", "羽毛渐变"))
        self.font_size_var = tk.IntVar(value=int(self.settings.get("font_size") or 10))
        self.group_var = tk.StringVar(value=self.settings.get("group_filter", "全部"))
        self.route_mode_var = tk.StringVar(value=self.settings.get("route_mode", "bypass_cn"))
        self.upload = "0 B/s"
        self.download = "0 B/s"
        self._anim_job = None
        self._anim_phase = 0

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
        self._tray = None
        self._tray_thread = None
        self._setup_tray()
        self.after(1500, self._maybe_auto_update_check)

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
        self.settings["skin"] = self.skin_var.get()
        self.settings["font_size"] = int(self.font_size_var.get())
        self.settings["group_filter"] = self.group_var.get()
        self.settings["route_mode"] = self.route_mode_var.get()
        save_settings(self.settings)


    def _set_window_icon(self):
        ico = asset_path("netbridge.ico")
        if ico:
            try:
                self.iconbitmap(default=str(ico))
                return
            except Exception:
                pass
        png = asset_path("netbridge.png")
        if png:
            try:
                img = tk.PhotoImage(file=str(png))
                self.iconphoto(True, img)
                self._icon_img = img
            except Exception:
                pass

    def _fs(self, base=10):
        try:
            return max(8, min(18, int(self.font_size_var.get()) + (base - 10)))
        except Exception:
            return base

    def _skin(self) -> dict:
        return SKINS.get(self.skin_var.get(), SKINS.get("羽毛渐变", SKINS["清新蓝"]))


    def _make_gradient_image(self, w=480, h=800):
        if Image is None:
            try:
                from PIL import Image as _Image
            except Exception:
                return None
        else:
            _Image = Image
        img = _Image.new("RGB", (max(w, 2), max(h, 2)))
        px = img.load()
        H, W = img.size[1], img.size[0]
        for y in range(H):
            for x in range(W):
                t = (y / max(H - 1, 1)) * 0.7 + (x / max(W - 1, 1)) * 0.3
                if t < 0.4:
                    u = t / 0.4
                    r = int(236 + (140 - 236) * u)
                    g = int(140 + (80 - 140) * u)
                    b = int(250 + (230 - 250) * u)
                else:
                    u = (t - 0.4) / 0.6
                    r = int(140 + (80 - 140) * u)
                    g = int(80 + (190 - 80) * u)
                    b = int(230 + (250 - 230) * u)
                # lighten for UI readability
                r = int(r * 0.5 + 255 * 0.5)
                g = int(g * 0.5 + 255 * 0.5)
                b = int(b * 0.5 + 255 * 0.5)
                px[x, y] = (r, g, b)
        return img

    def _on_resize_gradient(self, event):
        if event.widget is not self:
            return
        if getattr(self, "_resize_job", None):
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(200, self._apply_gradient_bg)

    def _apply_gradient_bg(self):
        """粉紫蓝渐变：窗口底图 + 同步控件底色（Tk 控件不透明，必须一起改色）。"""
        sk = self._skin()
        if not sk.get("gradient"):
            try:
                if getattr(self, "_bg_label", None):
                    self._bg_label.place_forget()
            except Exception:
                pass
            try:
                self.configure(bg=sk["bg"])
            except Exception:
                pass
            return
        # 渐变主色（与羽毛图一致的浅粉紫蓝）
        base_bg = "#E8D5F5"
        card_bg = "#F5EEFF"
        try:
            from PIL import Image as _Image, ImageTk as _ImageTk
            self.update_idletasks()
            w = max(int(self.winfo_width() or 460), 400)
            h = max(int(self.winfo_height() or 760), 600)
            path = asset_path("bg_gradient.png")
            if path and path.is_file():
                img = _Image.open(path).convert("RGB").resize((w, h))
            else:
                img = self._make_gradient_image(w, h)
            if img is not None:
                self._bg_photo = _ImageTk.PhotoImage(img)
                if not getattr(self, "_bg_label", None):
                    self._bg_label = tk.Label(self, image=self._bg_photo, borderwidth=0)
                else:
                    self._bg_label.configure(image=self._bg_photo)
                self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                self._bg_label.lower()
        except Exception:
            pass
        try:
            self.configure(bg=base_bg)
        except Exception:
            pass
        # 递归把仍用旧 BG 的 Frame/Label 刷成渐变底色
        def walk(w):
            try:
                cls = w.winfo_class()
                if cls in ("Frame", "Label", "Toplevel"):
                    cur = str(w.cget("bg") or "").lower()
                    if cur in (str(BG).lower(), "#e8f1ff", "#f2f2f7", base_bg.lower(), "#c9b8f0"):
                        w.configure(bg=base_bg)
                if cls == "Frame":
                    # 卡片略浅
                    pass
            except Exception:
                pass
            try:
                for c in w.winfo_children():
                    walk(c)
            except Exception:
                pass
        try:
            walk(self)
        except Exception:
            pass
        try:
            if hasattr(self, "canvas"):
                self.canvas.configure(bg=card_bg)
        except Exception:
            pass

    def _rebuild_colors(self):
        sk = self._skin()
        try:
            self._apply_gradient_bg()
            # 半透明卡片感：主画布用浅色
            cbg = "#FFFFFF" if sk.get("gradient") else sk["bg"]
            if hasattr(self, "canvas"):
                self.canvas.configure(bg=cbg)
        except Exception:
            try:
                self.configure(bg=sk["bg"])
            except Exception:
                pass

    def _apply_skin(self):
        sk = self._skin()
        global BG, CARD, TEXT, SECONDARY, BLUE, GREEN
        BG, CARD = sk["bg"], sk["card"]
        TEXT, SECONDARY = sk["text"], sk["secondary"]
        BLUE = sk["accent"]
        self.configure(bg=BG)
        try:
            self._rebuild_colors()
        except Exception:
            pass
        self._persist_settings()
        self._refresh()

    def _glass_btn(self, parent, text, command, primary=False, padx=12, pady=8):
        sk = self._skin()
        bg = sk["btn"] if primary else sk["card"]
        fg = sk["btn_fg"] if primary else sk["text"]
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            font=("Segoe UI", self._fs(10)),
            bg=bg,
            fg=fg,
            activebackground=sk["accent"],
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            padx=padx,
            pady=pady,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=sk["accent"] if primary else "#D0D5DD",
            highlightcolor=sk["accent"],
        )
        return btn

    def _err(self, title, msg):
        alert_error()
        messagebox.showerror(title, msg)

    def _warn(self, title, msg):
        alert_error()
        messagebox.showwarning(title, msg)

    def _start_connect_anim(self):
        self._stop_connect_anim()
        self._anim_phase = 0

        def tick():
            if self.status != "connecting":
                self._anim_job = None
                return
            self._anim_phase = (self._anim_phase + 1) % 6
            sk = self._skin()
            # pulse radius / color
            colors = [sk["accent"], "#5AC8FA", sk["accent"], "#FFD60A", sk["accent"], "#64D2FF"]
            c = colors[self._anim_phase]
            try:
                pad = 10 + (self._anim_phase % 3) * 2
                self.canvas.coords(self.btn_id, pad, pad, 180 - pad, 180 - pad)
                self.canvas.itemconfig(self.btn_id, fill=c)
                dots = "." * (self._anim_phase % 4)
                self.canvas.itemconfig(self.txt_id, text=f"连接中{dots}")
            except Exception:
                pass
            self._anim_job = self.after(120, tick)

        tick()

    def _stop_connect_anim(self):
        if self._anim_job:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None
        try:
            self.canvas.coords(self.btn_id, 10, 10, 170, 170)
        except Exception:
            pass

    def _node_groups(self):
        groups = sorted({(n.get("group") or "默认") for n in self.nodes if n.get("server")})
        return ["全部"] + groups

    def _filtered_nodes_indices(self):
        gf = self.group_var.get() or "全部"
        out = []
        for i, n in enumerate(self.nodes):
            if not n.get("server"):
                continue
            g = n.get("group") or "默认"
            if gf == "全部" or g == gf:
                out.append(i)
        return out

    def _check_update_manual(self):
        self.lbl_status.config(text="正在检查更新…")

        def work():
            try:
                ok, msg, release = check_github_update()
            except Exception as e:
                ok, msg, release = False, str(e), None

            def ui():
                self.lbl_status.config(text=(msg or "").split("\n")[0][:80])
                if ok:
                    url = find_windows_asset(release) or RELEASES_PAGE
                    if messagebox.askyesno(
                        "发现更新",
                        msg + "\n\n是否打开下载页面？\n（下载后请解压覆盖安装）",
                    ):
                        open_in_browser(url)
                else:
                    if "无法连接" in (msg or ""):
                        if messagebox.askyesno(
                            "检查更新失败",
                            msg + "\n\n是否在浏览器中打开 Releases 页面？",
                        ):
                            open_in_browser(RELEASES_PAGE)
                    else:
                        messagebox.showinfo("检查更新", msg)

            self.after(0, ui)

        threading.Thread(target=work, daemon=True).start()

    def _maybe_auto_update_check(self):
        if not self.settings.get("auto_update_check", True):
            return

        def work():
            try:
                has, msg, release = check_github_update()
            except Exception:
                return
            if not has:
                return

            def ui():
                url = find_windows_asset(release) or RELEASES_PAGE
                if messagebox.askyesno("发现更新", msg + "\n\n是否打开下载页面？"):
                    open_in_browser(url)

            self.after(0, ui)

        threading.Thread(target=work, daemon=True).start()


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
        tk.Label(opt2, text="路由", bg=BG, fg=SECONDARY).pack(side="left", padx=(10, 2))
        route_box = ttk.Combobox(
            opt2,
            textvariable=self.route_mode_var,
            values=["bypass_cn", "global", "direct"],
            width=10,
            state="readonly",
        )
        route_box.pack(side="left")
        route_box.bind("<<ComboboxSelected>>", lambda e: self._persist_settings())

        opt3 = tk.Frame(self, bg=BG)
        opt3.pack(fill="x", padx=16, pady=(4, 0))
        tk.Label(opt3, text="皮肤", bg=BG, fg=SECONDARY).pack(side="left")
        skin_box = ttk.Combobox(opt3, textvariable=self.skin_var, values=list(SKINS.keys()), width=8, state="readonly")
        skin_box.pack(side="left", padx=4)
        skin_box.bind("<<ComboboxSelected>>", lambda e: self._apply_skin())
        tk.Label(opt3, text="字号", bg=BG, fg=SECONDARY).pack(side="left", padx=(8, 2))
        font_box = ttk.Combobox(opt3, textvariable=self.font_size_var, values=[9, 10, 11, 12, 14, 16], width=4, state="readonly")
        font_box.pack(side="left")
        font_box.bind("<<ComboboxSelected>>", lambda e: (self._persist_settings(), self._refresh()))
        tk.Label(opt3, text="分组", bg=BG, fg=SECONDARY).pack(side="left", padx=(8, 2))
        self.group_box = ttk.Combobox(opt3, textvariable=self.group_var, values=self._node_groups(), width=8, state="readonly")
        self.group_box.pack(side="left")
        self.group_box.bind("<<ComboboxSelected>>", lambda e: (self._persist_settings(), self._refresh()))
        self._glass_btn(opt3, "检查更新", self._check_update_manual, primary=False, padx=8, pady=2).pack(side="right")

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
        self.btn_disconnect = self._glass_btn(
            self, "断开连接", self._disconnect, primary=False, padx=18, pady=6
        )
        self.btn_disconnect.pack(pady=(4, 0))


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
            ("断开", self._disconnect),
            ("添加", self._add_node_dialog),
            ("托盘", self._hide_to_tray),
            ("日志", self._show_log),
        ]:
            b = self._glass_btn(bottom, text, cmd, primary=False, padx=6, pady=10)
            b.pack(side="left", expand=True, padx=2, pady=4)

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
        sk = self._skin()
        colors = {"disconnected": sk["accent"], "connecting": ORANGE, "connected": GREEN, "error": RED}
        labels = {"disconnected": "连接", "connecting": "连接中", "connected": "已连接", "error": "重试"}
        if self.status == "connecting":
            self._start_connect_anim()
        else:
            self._stop_connect_anim()
            try:
                self.canvas.itemconfig(self.btn_id, fill=colors.get(self.status, sk["accent"]))
                self.canvas.itemconfig(self.txt_id, text=labels.get(self.status, "连接"))
                self.canvas.coords(self.btn_id, 10, 10, 170, 170)
            except Exception:
                pass
        try:
            if hasattr(self, "group_box"):
                self.group_box["values"] = self._node_groups()
        except Exception:
            pass
        try:
            if hasattr(self, "btn_disconnect"):
                # 连接中/已连接都可断开
                st = "normal" if self.status in ("connected", "connecting", "error") else "normal"
                self.btn_disconnect.configure(state="normal")
        except Exception:
            pass
        port = self.settings.get("mixed_port", MIXED_PORT)
        host = "0.0.0.0" if self.lan_var.get() else "127.0.0.1"
        mode = []
        if self.sysproxy_var.get() and not self.tun_var.get():
            mode.append("系统代理")
        if self.tun_var.get():
            mode.append("TUN")
        if self.lan_var.get():
            mode.append("局域网")
        rm = {"bypass_cn": "绕过大陆", "global": "全局", "direct": "直连"}.get(self.route_mode_var.get(), "")
        if rm:
            mode.append(rm)
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

    def _disconnect(self):
        """断开连接并关闭系统代理（随时可点，含连接中）。"""
        try:
            stop_core()
        except Exception as e:
            try:
                self.lbl_status.config(text=f"断开时: {e}")
            except Exception:
                pass
        self.status = "disconnected"
        try:
            self._stop_connect_anim()
        except Exception:
            pass
        try:
            self.lbl_status.config(text="已断开连接")
        except Exception:
            pass
        try:
            if hasattr(self, "btn_disconnect"):
                self.btn_disconnect.configure(state="normal")
        except Exception:
            pass
        self._refresh()

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
            self._warn("提示", "请先添加节点或导入订阅")
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
                if True:  # start_core 未抛错即成功
                    self.status = "connected"
                    self.after(0, lambda: self.lbl_status.config(
                        text=f"已连接 · 请设系统代理 127.0.0.1:{port}"
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
                    # 二次确认：日志里已 started 则仍算连接成功
                    if log_says_core_started():
                        self.status = "connected"
                        self.after(0, lambda: self.lbl_status.config(
                            text=f"已连接 · 系统代理请设 127.0.0.1:{port}"
                        ))
                        self.after(0, self._refresh)
                    else:
                        self.status = "error"
                        self.after(0, lambda: messagebox.showwarning(
                            "无法上网",
                            f"未能确认核心在监听 {port}。\n请打开「日志」查看是否有 error。",
                        ))
                        self.after(0, self._refresh)
            except Exception as e:
                self.status = "error"
                err = str(e)
                self.after(0, lambda m=err: self._err("连接失败", m))
                self.after(0, self._refresh)

        threading.Thread(target=work, daemon=True).start()

    def _render_node_rows(self, frame, win):
        for w in frame.winfo_children():
            w.destroy()
        # 列表顺序与 self.nodes 一致（测试后已按延迟从低到高排列）
        gf = self.group_var.get() or "全部"
        for i in range(len(self.nodes)):
            n = self.nodes[i]
            if not n.get("server"):
                continue
            if gf != "全部" and (n.get("group") or "默认") != gf:
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
            grp = n.get("group") or "默认"
            sub = f"[{grp}] {lat_s}{spd_s} · {n.get('protocol')} · {net} · {n.get('server')}:{n.get('port')}"

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
            self._warn("提示", "没有可测试的节点")
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
            self._warn("提示", "请先添加或导入节点")
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
        gf = tk.Frame(win, bg=BG)
        gf.pack(fill="x", padx=10)
        tk.Label(gf, text="分组名称", bg=BG).pack(side="left")
        group_ent = tk.Entry(gf, width=16)
        group_ent.insert(0, "默认")
        group_ent.pack(side="left", padx=6)
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
                gname = group_ent.get().strip() or "默认"
                for n in nodes:
                    key = f"{n.get('server')}:{n.get('port')}:{n.get('protocol')}"
                    if key in existing:
                        continue
                    n["group"] = gname
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
            ("分组", "group", "默认"),
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
                "group": (fields["group"].get().strip() if "group" in fields else "") or "默认",
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
        # 单例：已打开则前置刷新，不重复开窗
        w = getattr(self, "_log_win", None)
        if w is not None:
            try:
                if w.winfo_exists():
                    w.deiconify()
                    w.lift()
                    w.focus_force()
                    self._fill_log_text()
                    return
            except Exception:
                pass
        win = tk.Toplevel(self)
        self._log_win = win
        win.title("日志 / 路径")
        win.geometry("560x460")
        try:
            win.configure(bg=BG)
        except Exception:
            pass
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9))
        txt.pack(fill="both", expand=True)
        self._log_text = txt
        self._fill_log_text()

        def on_close():
            self._log_win = None
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", on_close)

    def _fill_log_text(self):
        txt = getattr(self, "_log_text", None)
        if txt is None:
            return
        try:
            txt.config(state="normal")
            txt.delete("1.0", "end")
            info = (
                f"核心目录: {BIN_DIR}\n"
                f"配置: {CONFIG_FILE}\n"
                f"日志: {LOG_FILE}\n"
                f"节点: {NODES_FILE}\n\n"
                "--- core.log ---\n"
            )
            txt.insert("end", info)
            if LOG_FILE.exists():
                txt.insert("end", LOG_FILE.read_text(encoding="utf-8", errors="replace")[-8000:])
            txt.config(state="disabled")
        except Exception:
            pass


    def _setup_tray(self):
        """初始化系统托盘（右下角图标）。"""
        self._tray = None
        if not HAS_TRAY:
            return
        try:
            image = make_tray_image()

            def on_show(icon=None, item=None):
                self.after(0, self._show_from_tray)

            def on_hide(icon=None, item=None):
                self.after(0, self._hide_to_tray)

            def on_toggle(icon=None, item=None):
                self.after(0, self._toggle)

            def on_quit(icon=None, item=None):
                self.after(0, self._quit_app)

            menu = pystray.Menu(
                pystray.MenuItem("显示主窗口", on_show, default=True),
                pystray.MenuItem("隐藏到托盘", on_hide),
                pystray.MenuItem("连接 / 断开", on_toggle),
                pystray.MenuItem("断开连接", lambda icon, item: self.after(0, self._disconnect)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("退出", on_quit),
            )
            self._tray = pystray.Icon("NetBridge", image, f"NetBridge {app_version()}", menu)

            def run_tray():
                try:
                    self._tray.run()
                except Exception:
                    pass

            self._tray_thread = threading.Thread(target=run_tray, daemon=True)
            self._tray_thread.start()
        except Exception:
            self._tray = None

    def _show_from_tray(self):
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self.attributes("-topmost", True)
            self.after(200, lambda: self.attributes("-topmost", False))
        except Exception:
            pass

    def _hide_to_tray(self):
        try:
            self.withdraw()
            if self._tray is not None:
                try:
                    self._tray.notify("NetBridge 仍在运行", "已最小化到托盘，双击图标可恢复窗口")
                except Exception:
                    pass
        except Exception:
            pass

    def _quit_app(self):
        try:
            if self._tray is not None:
                try:
                    self._tray.stop()
                except Exception:
                    pass
                self._tray = None
        except Exception:
            pass
        try:
            stop_core()
        except Exception:
            pass
        try:
            SYS_PROXY.disable()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _on_close(self):
        # 点关闭：隐藏到托盘而不是退出（无托盘则真正退出）
        if HAS_TRAY and self._tray is not None:
            self._hide_to_tray()
            return
        self._quit_app()


def main():
    ensure_dirs()
    app = NetBridgeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
