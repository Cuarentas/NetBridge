# Changelog

## [1.0.0] - 2026-10-07

首个正式整合版。

### 功能
- 小火箭风格 Windows GUI（Tkinter 便携）
- sing-box / Xray 双核心，发布包内置
- 订阅导入、WS/gRPC/Reality
- 系统代理 / TUN
- 允许局域网连接（0.0.0.0）
- 日志等级可选
- 一键多线程节点延迟测试 + 当前节点测速
- 默认端口 1314
- 去除 legacy special outbounds 告警

### 构建
- GitHub Actions：Windows / Linux / macOS / Android / iOS
- 发版前清理同 tag 旧附件
- 产物短文件名（无 portable 后缀）

### 移除
- HarmonyOS 自动构建
