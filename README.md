<p align="center">
  <img src="https://img.shields.io/badge/NetBridge-1.0.0-007AFF?style=for-the-badge" alt="NetBridge" />
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

## ✨ 特性

| | |
|:--|:--|
| **精致界面** | 大圆形连接按钮、节点卡片，操作路径清晰 |
| **双核心** | sing-box / Xray，正式包内置，无需再下核心 |
| **协议丰富** | Shadowsocks · VMess · VLESS · Trojan |
| **现代传输** | WebSocket · gRPC · Reality |
| **一键订阅** | 支持订阅链接与分享链接导入 |
| **系统集成** | 系统代理 / TUN（需管理员） |
| **局域网** | 可选允许局域网设备共用本机代理 |
| **测速优选** | 多线程延迟测试，自动标记可用节点 |
| **可调日志** | trace / debug / info / warn / error |

---

## 📥 下载安装

请仅从本仓库 **[Releases](../../releases)** 获取官方构建包：

| 平台 | 安装包 | 说明 |
|:-----|:-------|:-----|
| Windows | `NetBridge-windows-x64.zip` | 解压后运行 `NetBridge.exe` |
| Linux | `NetBridge-linux-x64.tar.gz` | 解压后运行 |
| macOS | `NetBridge-macos.zip` | 打开 `.app`（若拦截请右键打开） |
| Android | `NetBridge-android.apk` | 允许未知来源后安装 |
| iOS | `NetBridge-ios.zip` | 未签名，需自行用开发者证书签名 |

> 默认本地混合代理端口：**1314**

---

## 🚀 快速开始（Windows）

1. 下载并解压 `NetBridge-windows-x64.zip`
2. 双击运行 **NetBridge.exe**
3. 导入订阅或手动添加节点
4. 勾选 **系统代理**（推荐）
5. 点击中央按钮连接

可选：

- **允许局域网连接** → 其它设备可使用 `本机IP:1314`
- **测试** → 多线程测延迟并优选节点
- **日志** → 调整等级并查看 `core.log`

---

## 🔒 授权与源码政策

本软件为 **专有软件（Proprietary）**，**并非开源项目**。

- 源码与工程文件保留所有权利，未经授权不得公开再分发或二次开发  
- 正式用户请通过官方 Release 获取二进制安装包  
- 详细条款见仓库根目录 [`LICENSE`](LICENSE)  

```
Copyright (c) 2026 NetBridge Authors. All Rights Reserved.
```

若 GitHub 仓库需对外隐藏源码，请在仓库 **Settings → General → Danger Zone** 中将可见性设为 **Private**，或仅发布 Release 附件、不公开完整源码树。

---

## 🛠 构建说明（维护者）

维护者可在 GitHub **Actions → Build Portable → Run workflow** 生成各平台安装包并自动创建 Release。  
发版前会清理同一 tag 下的旧附件。

详见 [`docs/GITHUB_WEB_PUBLISH.md`](docs/GITHUB_WEB_PUBLISH.md)。

---

## ⚠️ 免责声明

本软件仅供学习、研究与合法网络调试。  
请遵守所在地法律法规。开发者不对任何滥用行为承担责任。

---

<p align="center">
  <sub>NetBridge 1.0.0 · All Rights Reserved</sub>
</p>
