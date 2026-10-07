#!/usr/bin/env python3
"""
简单示例：把 Shadowrocket 风格 .conf 转成基础 sing-box JSON。
仅作演示，生产环境请完善解析与错误处理。
"""

import json
import re
import sys
from pathlib import Path


def parse_conf(text: str) -> dict:
    sections = {"General": [], "Proxy": [], "Proxy Group": [], "Rule": []}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1]
            current = name if name in sections else None
            continue
        if current:
            sections[current].append(line)
    return sections


def parse_proxy_line(line: str) -> dict | None:
    # 极简解析: name = type, host, port, key=value, ...
    m = re.match(r"^(.+?)\s*=\s*(\w+)\s*,\s*(.+)$", line)
    if not m:
        return None
    name, ptype, rest = m.group(1).strip(), m.group(2).lower(), m.group(3)
    parts = [p.strip() for p in rest.split(",")]
    host = parts[0] if parts else ""
    port = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    opts = {}
    for p in parts[2:]:
        if "=" in p:
            k, v = p.split("=", 1)
            opts[k.strip()] = v.strip()

    if ptype == "ss":
        return {
            "type": "shadowsocks",
            "tag": name,
            "server": host,
            "server_port": port,
            "method": opts.get("method", "aes-256-gcm"),
            "password": opts.get("password", ""),
        }
    if ptype == "vmess":
        return {
            "type": "vmess",
            "tag": name,
            "server": host,
            "server_port": port,
            "uuid": opts.get("username") or opts.get("uuid") or opts.get("password", ""),
            "security": opts.get("method", "auto"),
            "alter_id": int(opts.get("alterId", 0)),
        }
    if ptype == "trojan":
        return {
            "type": "trojan",
            "tag": name,
            "server": host,
            "server_port": port,
            "password": opts.get("password", ""),
        }
    # 其他类型可继续扩展
    return None


def build_singbox(sections: dict) -> dict:
    outbounds = [
        {"type": "direct", "tag": "direct"},
        {"type": "block", "tag": "block"},
        {"type": "dns", "tag": "dns-out"},
    ]
    proxy_tags = []

    for line in sections.get("Proxy", []):
        ob = parse_proxy_line(line)
        if ob:
            outbounds.append(ob)
            proxy_tags.append(ob["tag"])

    # 简单 select 组
    if proxy_tags:
        outbounds.append({
            "type": "selector",
            "tag": "PROXY",
            "outbounds": proxy_tags + ["direct"],
            "default": proxy_tags[0],
        })
    else:
        outbounds.append({
            "type": "selector",
            "tag": "PROXY",
            "outbounds": ["direct"],
            "default": "direct",
        })

    rules = [
        {"protocol": "dns", "outbound": "dns-out"},
        {"ip_is_private": True, "outbound": "direct"},
    ]

    for line in sections.get("Rule", []):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        rtype = parts[0].upper()
        payload = parts[1] if len(parts) > 1 else ""
        target = parts[2].upper() if len(parts) > 2 else "PROXY"
        outbound = "block" if target == "REJECT" else ("direct" if target == "DIRECT" else "PROXY")

        if rtype == "DOMAIN-SUFFIX":
            rules.append({"domain_suffix": [payload], "outbound": outbound})
        elif rtype == "DOMAIN-KEYWORD":
            rules.append({"domain_keyword": [payload], "outbound": outbound})
        elif rtype == "DOMAIN":
            rules.append({"domain": [payload], "outbound": outbound})
        elif rtype == "IP-CIDR":
            rules.append({"ip_cidr": [payload], "outbound": outbound})
        elif rtype == "GEOIP":
            rules.append({"geoip": payload.lower(), "outbound": outbound})
        elif rtype == "FINAL":
            # 最后处理
            pass

    final = "PROXY"
    for line in sections.get("Rule", []):
        if line.upper().startswith("FINAL,"):
            final = line.split(",")[1].strip().upper()
            final = "block" if final == "REJECT" else ("direct" if final == "DIRECT" else "PROXY")

    config = {
        "log": {"level": "info", "timestamp": True},
        "dns": {
            "servers": [
                {"tag": "local", "address": "local"},
                {"tag": "google", "address": "8.8.8.8"},
            ],
            "final": "google",
        },
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": 7890,
                "sniff": True,
            }
        ],
        "outbounds": outbounds,
        "route": {
            "rules": rules,
            "final": final,
            "auto_detect_interface": True,
        },
    }
    return config


def main():
    if len(sys.argv) < 2:
        print("Usage: conf_to_singbox.py <input.conf> [output.json]")
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_suffix(".json")
    text = src.read_text(encoding="utf-8")
    sections = parse_conf(text)
    config = build_singbox(sections)
    dst.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Written: {dst}")


if __name__ == "__main__":
    main()
