<p align="center">
  <img src="https://img.shields.io/github/v/release/Cuarentas/NetBridge?style=for-the-badge&label=NetBridge&color=007AFF" alt="NetBridge" />
</p>

<h1 align="center">NetBridge</h1>

<p align="center">
  <b>简洁高效的跨平台网络代理客户端</b><br/>
  界面灵感来自 Shadowrocket · 支持 sing-box / Xray
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Windows-✓-34C759?style=flat-square" alt="Windows" />
  <img src="https://img.shields.io/badge/macOS-✓-34C759?style=flat-square" alt="macOS" />
  <img src="https://img.shields.io/badge/Linux-✓-34C759?style=flat-square" alt="Linux" />
  <img src="https://img.shields.io/badge/Android-✓-34C759?style=flat-square" alt="Android" />
  <img src="https://img.shields.io/badge/iOS-签名后可用-FF9500?style=flat-square" alt="iOS" />
  <img src="https://img.shields.io/badge/License-Proprietary-8E8E93?style=flat-square" alt="License" />
</p>

---

## ✨ 特性（1.2.0 整合版）

| | |
|:--|:--|
| **精致界面** | 大圆形连接按钮、羽毛渐变底色、多皮肤 |
| **双核心** | sing-box / Xray（发布包内置） |
| **协议** | Shadowsocks · VMess · VLESS · Trojan |
| **传输** | TCP · WebSocket · gRPC · Reality |
| **订阅** | 一键导入，支持分组 |
| **分流** | 绕过大陆 / 全局 / 直连（国内直连、国外代理） |
| **系统集成** | 系统代理 · TUN（需管理员） |
| **局域网** | 可选允许局域网共用代理 |
| **测速** | 多线程延迟测试，按延迟排序 |
| **托盘** | 最小化到托盘、断开连接 |
| **更新** | 检查更新（镜像 + 本地代理回退） |
| **字号/日志** | 用户可调 |

---

## 📥 下载

请从 **[Releases](../../releases)** 获取：

| 平台 | 文件 |
|:-----|:-----|
| Windows | `NetBridge-windows-x64.zip` → 运行 `NetBridge.exe` |
| Linux | `NetBridge-linux-x64.tar.gz` |
| macOS | `NetBridge-macos.zip` |
| Android | `NetBridge-android.apk` |
| iOS | `NetBridge-ios.zip`（需自行签名） |

默认本地端口：**7890**

---

## 🚀 Windows 快速开始

1. 解压并运行 **NetBridge.exe**
2. 导入订阅（可填分组名）
3. 路由选择 **bypass_cn**（绕过大陆）
4. 勾选 **系统代理** → 连接
5. 系统代理地址：`127.0.0.1` / `7890`

**勿与 v2rayN 等同时占用 7890。** 连接前会自动尝试释放端口。

---

## 📌 版本号自动一致

| 位置 | 规则 |
|------|------|
| README 徽章 | shields 读取 GitHub Latest Release |
| Release / tag | Actions 填写的 `tag_name` |
| 软件标题 | 构建时写入 `APP_VERSION` |

发版只需在 Actions 填 tag（如 `v1.2.0`）。

---

## 🔒 授权

本软件为 **专有软件（Proprietary）**，详见 [`LICENSE`](LICENSE)。

```
Copyright (c) 2026 NetBridge Authors. All Rights Reserved.
```

---

## 🛠 维护者构建

**Actions → Build Portable → Run workflow**  
`tag_name` = `v1.2.0`，`create_release` = true

详见 [`docs/GITHUB_WEB_PUBLISH.md`](docs/GITHUB_WEB_PUBLISH.md)

---

## ⚠️ 免责声明

仅供学习、研究与合法网络调试。请遵守当地法律法规。

---

<p align="center"><sub>NetBridge · All Rights Reserved</sub></p>
