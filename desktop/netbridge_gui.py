#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NetBridge - Shadowrocket-style portable GUI (tkinter, no extra deps)."""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time

# Colors
BLUE = "#007AFF"
GREEN = "#34C759"
ORANGE = "#FF9500"
RED = "#FF3B30"
BG = "#F2F2F7"
CARD = "#FFFFFF"
TEXT = "#000000"
SECONDARY = "#8E8E93"


class NetBridgeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NetBridge")
        self.geometry("400x640")
        self.minsize(360, 560)
        self.configure(bg=BG)

        self.status = "disconnected"  # disconnected / connecting / connected / error
        self.node_name = "示例节点（请替换）"
        self.group_name = "手动添加"
        self.upload = "0 B/s"
        self.download = "0 B/s"
        self.nodes = [
            {"name": "示例节点（请替换）", "group": "手动添加", "proto": "ss"},
            {"name": "节点 A", "group": "订阅", "proto": "vless"},
            {"name": "节点 B", "group": "订阅", "proto": "trojan"},
        ]

        self._build_ui()
        self._refresh_button()

    def _build_ui(self):
        # Top node card
        top = tk.Frame(self, bg=CARD, highlightthickness=0)
        top.pack(fill="x", padx=20, pady=(20, 8))
        top.bind("<Button-1>", lambda e: self._open_nodes())
        self.lbl_node = tk.Label(
            top, text=self.node_name, font=("Segoe UI", 14, "bold"),
            bg=CARD, fg=TEXT, cursor="hand2"
        )
        self.lbl_node.pack(pady=(16, 4))
        self.lbl_node.bind("<Button-1>", lambda e: self._open_nodes())
        self.lbl_sub = tk.Label(
            top, text=f"{self.group_name} · --", font=("Segoe UI", 11),
            bg=CARD, fg=SECONDARY, cursor="hand2"
        )
        self.lbl_sub.pack(pady=(0, 16))
        self.lbl_sub.bind("<Button-1>", lambda e: self._open_nodes())

        # Center connect button (Canvas circle)
        mid = tk.Frame(self, bg=BG)
        mid.pack(expand=True, fill="both")
        self.canvas = tk.Canvas(mid, width=180, height=180, bg=BG, highlightthickness=0)
        self.canvas.pack(expand=True)
        self.btn_id = self.canvas.create_oval(10, 10, 170, 170, fill=BLUE, outline="")
        self.txt_id = self.canvas.create_text(
            90, 90, text="连接", fill="white", font=("Segoe UI", 18, "bold")
        )
        self.canvas.bind("<Button-1>", lambda e: self._toggle())

        # Speeds
        speed = tk.Frame(self, bg=BG)
        speed.pack(fill="x", padx=32, pady=8)
        self.lbl_up = tk.Label(speed, text="↑ 0 B/s", font=("Segoe UI", 12), bg=BG, fg=SECONDARY)
        self.lbl_up.pack(side="left", expand=True)
        self.lbl_down = tk.Label(speed, text="↓ 0 B/s", font=("Segoe UI", 12), bg=BG, fg=SECONDARY)
        self.lbl_down.pack(side="right", expand=True)

        # Bottom nav
        bottom = tk.Frame(self, bg=CARD)
        bottom.pack(fill="x", padx=20, pady=(8, 20))
        for text, cmd in [("节点", self._open_nodes), ("配置", self._cfg), ("设置", self._settings)]:
            b = tk.Button(
                bottom, text=text, font=("Segoe UI", 11), bg=CARD, fg=TEXT,
                relief="flat", cursor="hand2", command=cmd, padx=16, pady=12
            )
            b.pack(side="left", expand=True)

        # Footer tip
        tip = tk.Label(
            self,
            text="演示版：连接状态为模拟。后续将接入 sing-box。",
            font=("Segoe UI", 9), bg=BG, fg=SECONDARY
        )
        tip.pack(pady=(0, 12))

    def _refresh_button(self):
        colors = {
            "disconnected": BLUE,
            "connecting": ORANGE,
            "connected": GREEN,
            "error": RED,
        }
        labels = {
            "disconnected": "连接",
            "connecting": "连接中",
            "connected": "已连接",
            "error": "重试",
        }
        c = colors.get(self.status, BLUE)
        t = labels.get(self.status, "连接")
        self.canvas.itemconfig(self.btn_id, fill=c)
        self.canvas.itemconfig(self.txt_id, text=t)
        self.lbl_up.config(text=f"↑ {self.upload}")
        self.lbl_down.config(text=f"↓ {self.download}")

    def _toggle(self):
        if self.status == "connected":
            self.status = "disconnected"
            self.upload = "0 B/s"
            self.download = "0 B/s"
            self._refresh_button()
            return
        if self.status == "connecting":
            return
        self.status = "connecting"
        self._refresh_button()

        def work():
            time.sleep(0.9)
            self.status = "connected"
            self.upload = "128 KB/s"
            self.download = "1.2 MB/s"
            self.after(0, self._refresh_button)

        threading.Thread(target=work, daemon=True).start()

    def _open_nodes(self):
        win = tk.Toplevel(self)
        win.title("节点")
        win.geometry("360x420")
        win.configure(bg=BG)

        tk.Label(win, text="选择节点", font=("Segoe UI", 13, "bold"), bg=BG).pack(pady=12)

        frame = tk.Frame(win, bg=BG)
        frame.pack(fill="both", expand=True, padx=12)

        for i, n in enumerate(self.nodes):
            def make_cmd(idx=i):
                def cmd():
                    node = self.nodes[idx]
                    self.node_name = node["name"]
                    self.group_name = node["group"]
                    self.lbl_node.config(text=self.node_name)
                    self.lbl_sub.config(text=f"{self.group_name} · {node['proto']}")
                    win.destroy()
                return cmd

            row = tk.Frame(frame, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Button(
                row,
                text=f"{n['name']}  ({n['proto']})",
                font=("Segoe UI", 11),
                bg=CARD, fg=TEXT, relief="flat", anchor="w",
                command=make_cmd(), padx=12, pady=10
            ).pack(fill="x")

        tk.Button(win, text="添加示例节点", command=lambda: self._add_node(win)).pack(pady=10)

    def _add_node(self, parent):
        self.nodes.append({
            "name": f"新节点 {len(self.nodes) + 1}",
            "group": "手动添加",
            "proto": "ss",
        })
        parent.destroy()
        self._open_nodes()

    def _cfg(self):
        messagebox.showinfo("配置", "配置页开发中。\n后续支持规则模式 / 全局代理切换。")

    def _settings(self):
        messagebox.showinfo(
            "设置",
            "NetBridge 便携版 0.2.0\n\n"
            "当前为 GUI 演示模式。\n"
            "真实代理将接入 sing-box 核心。\n\n"
            "github.com/Cuarentas/NetBridge"
        )


def main():
    app = NetBridgeApp()
    app.mainloop()


if __name__ == "__main__":
    main()
