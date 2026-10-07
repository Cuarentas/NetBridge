# NetBridge 项目整合说明（对话成果汇总）

## 目标

以 Shadowrocket（小火箭）为交互参考，做可在 GitHub 发布的跨平台代理客户端。

## 已实现

1. **Windows 便携版**（主推）：解压即用，内置核心，功能最全  
2. **多平台 CI**：Linux / macOS / Android APK / iOS 未签名包  
3. **协议与传输**：SS/VMess/VLESS/Trojan，WS/gRPC/Reality  
4. **订阅导入**、系统代理、TUN、局域网、日志等级、延迟/测速  
5. **网页发布流程**：不依赖本机 git 命令行  

## 使用注意

- 日常推荐：系统代理 + 端口 1314  
- TUN 需管理员，失败率相对高  
- iOS 需开发者签名；鸿蒙需 DevEco 本机构建（已从 CI 移除）  
- 代理连通可用：`curl.exe --noproxy "*" -x http://127.0.0.1:1314 -I http://www.gstatic.com/generate_204`（期望 204）

## 免责

仅供合法学习研究。
