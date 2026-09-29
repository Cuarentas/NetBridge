# NetBridge

**开源规则分流代理客户端** · UI 参考 Shadowrocket（小火箭）

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Release](https://img.shields.io/github/v/release/Cuarentas/NetBridge?include_prereleases)](https://github.com/Cuarentas/NetBridge/releases)

> **当前版本 0.2.1**：已提供 Windows 便携版与 Linux 桌面包。界面可运行；**代理连接仍为演示模式**（未接入真实核心）。

---

## 下载使用（推荐）

前往 [Releases](https://github.com/Cuarentas/NetBridge/releases) 下载：

| 平台 | 文件 | 用法 |
|------|------|------|
| **Windows** | `NetBridge-windows-portable.zip` | 解压 → 双击 `NetBridge.exe` |
| **Linux** | `NetBridge-linux-x64.tar.gz` | 解压 → `chmod +x netbridge && ./netbridge` |

不需要安装 Python、Flutter 或其它运行时。

### 界面说明

1. 首页中央大按钮：连接 / 断开（蓝=未连接，橙=连接中，绿=已连接）
2. 顶部节点卡片 / 「节点」：选择或添加节点
3. 配置 / 设置：占位，后续扩展

**注意**：当前点击连接只切换界面状态，**不会真正代理网络流量**。真实代理需后续接入 sing-box。

---

## 功能规划

| 功能 | 状态 |
|------|------|
| 小火箭风格 GUI | ✅ 已有 |
| Windows 便携包 | ✅ 已有 |
| Linux 桌面包 | ✅ 已有 |
| 多核心（sing-box / mihomo / Xray） | ⏳ 规划中 |
| 订阅导入 | ⏳ 规划中 |
| 规则分流 / 系统代理 / TUN | ⏳ 规划中 |
| Android / iOS / 鸿蒙 / macOS | ⏳ 规划中 |

---

## 仓库结构

```
NetBridge/
├── README.md                 # 本说明
├── LICENSE                   # MIT
├── VERSION
├── CHANGELOG.md
├── desktop/                  # Windows 便携版源码（Tkinter）
│   ├── netbridge_gui.py
│   └── requirements.txt
├── flutter/                  # Linux GUI 源码（Flutter）
│   ├── lib/main.dart
│   └── pubspec.yaml
├── configs/                  # 示例规则与配置
├── scripts/                  # 核心下载、配置转换（可选）
├── docs/                     # 补充文档
└── .github/workflows/
    └── portable-build.yml    # 自动构建 Windows + Linux 并发布
```

---

## 自动构建（GitHub Actions）

本机**不必**安装开发环境。在仓库页面：

1. **Actions** → **Build Portable** → **Run workflow**
2. 填写 tag（如 `v0.2.2-portable`），create_release 选 `true`
3. 完成后在 [Releases](https://github.com/Cuarentas/NetBridge/releases) 下载产物

工作流会：

- 用 PyInstaller 打 Windows 便携 zip  
- 用 Flutter 打 Linux 包  
- **等两边都结束后**再写入同一个 Release  

---

## 本地开发（可选）

### Windows 界面源码

```bash
cd desktop
python netbridge_gui.py
```

打包：

```bash
pip install pyinstaller
pyinstaller --windowed --name NetBridge --onedir netbridge_gui.py
```

### Linux Flutter 界面

需本机安装 Flutter：

```bash
cd flutter
flutter create . --platforms=linux --project-name netbridge
flutter pub get
flutter run -d linux
```

### 示例配置

`configs/` 下的 `.conf` / `.json` 可导入到 Shadowrocket、Clash、sing-box 等已有客户端使用。

---

## 免责声明

本项目仅供学习、研究与合法网络调试。  
请遵守所在地法律法规。开发者不对任何滥用行为负责。

## License

MIT License
