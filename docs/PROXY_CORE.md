# NetBridge 0.4 核心功能说明

## 已实现

### 1. 核心
- **sing-box** / **Xray** 切换
- 首次连接自动下载二进制到 `core/bin/`

### 2. 复杂传输
| 能力 | sing-box | Xray |
|------|----------|------|
| TCP | ✅ | ✅ |
| WebSocket (ws) | ✅ | ✅ |
| gRPC | ✅ | ✅ |
| TLS | ✅ | ✅ |
| Reality (pbk/sid/fp/sni) | ✅ | ✅ |
| flow (xtls-rprx-vision 等) | ✅ | ✅ |

手动添加时可填：network / path / host / sni / reality / pbk / sid / fp / serviceName / flow  
订阅链接（vless/vmess/trojan 参数）会尽量自动解析。

### 3. 订阅一键导入
- 支持订阅 **URL**（http/https）
- 支持粘贴多行分享链接：`ss://` `vmess://` `vless://` `trojan://`
- 支持常见 base64 订阅正文
- 轻度解析 Clash `proxies:` 片段（无完整 YAML 库）

界面底部点 **「订阅」** → 粘贴 → 导入。

### 4. 系统代理
- 勾选 **系统代理** 后，连接时自动设置：
  - **Windows**：当前用户 Internet Settings 代理
  - **macOS**：networksetup（Wi-Fi/Ethernet）
  - **Linux**：gsettings（GNOME）
- 断开连接时自动关闭系统代理

### 5. TUN
- 勾选 **TUN(需管理员)** 时，使用 **sing-box** 的 tun 入站（`auto_route`）
- **需要管理员/root 权限**；Windows 建议右键「以管理员身份运行」
- Xray 路径下 TUN 会提示忽略（请用系统代理或 sing-box）

## 使用流程

1. 订阅导入或手动添加节点  
2. 选择核心；按需勾选系统代理 / TUN  
3. 点击连接  
4. 系统代理开启时一般无需再改浏览器；仅本地端口时设置 `127.0.0.1:7890`

## 目录

```
程序目录/
├── NetBridge.exe
├── core/bin/          # sing-box / xray
└── runtime/
    ├── nodes.json
    ├── subscriptions.json
    ├── settings.json
    ├── config.json
    └── core.log
```

## 限制说明

- Clash 完整 YAML / 策略组未完整支持
- TUN 依赖系统权限与网卡驱动环境，失败请看日志并改用系统代理
- Reality 字段以分享链接常见参数为准；特殊定制需改 `runtime/config.json`

## 内置核心（1.0.0+）

正式 Release 的 Windows / Linux 包在构建时会下载并打入：

- `core/bin/sing-box`（或 `sing-box.exe`）
- `core/bin/xray`（或 `xray.exe`）

用户解压即可用，**无需再访问 GitHub 下载核心**。  
若删除了 `core/bin` 下文件，程序仍会尝试在线下载作为后备。
