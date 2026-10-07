# Android / macOS / iOS 真实 VPN 核心接入说明

## 架构

Flutter UI → MethodChannel `com.netbridge/vpn` → 各平台原生层 → sing-box / Xray

## Android

- `NetBridgeVpnService`：系统 `VpnService` + 前台服务
- 从 `assets/core/` 释放 `sing-box` / `xray` 可执行文件
- 写入配置并启动核心进程
- CI 构建 APK 时下载 **android-arm64** 核心并打入 assets

**限制**：完整 TUN 转发在 Android 上更稳妥的方式是 libbox（Go 移动绑定）。当前实现已打通权限、前台服务与核心进程；若路由异常，可再升级为 libbox。

## macOS

- `VpnPlugin.swift`：启动 App 内 `Resources/core/bin` 中的核心
- 自动设置系统 HTTP/HTTPS/SOCKS 代理到 `127.0.0.1:7890`
- 断开时关闭代理并结束进程

## iOS

- App：`NETunnelProviderManager` 拉起 Network Extension
- Extension：`PacketTunnelProvider` 建立隧道
- **必须**使用 Apple 开发者证书签名；未签名 IPA 无法在常规设备常驻
- 正式流量转发需在 Extension 内链入 libbox / 静态核心（Apple 禁止随意 exec 外部二进制）

## 构建

见 `.github/workflows/portable-build.yml`：

- Android：APK + 内置 arm64 核心
- macOS：.app + Resources 内核心
- iOS：unsigned IPA + 说明（签名需本机 Xcode）

## 已移除

- HarmonyOS 自动构建与占位包
