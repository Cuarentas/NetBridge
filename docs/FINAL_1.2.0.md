# NetBridge 1.2.0 最终整合说明

本包合并了本日对话中的全部有效改动，可直接上传 GitHub 并用 Actions 发版。

## 包含内容

- desktop/netbridge_gui.py（全功能 Windows GUI）
- 图标 netbridge.ico / png / tray、背景 bg_gradient.png
- .github/workflows/portable-build.yml（多平台构建、版本注入、图标复制）
- Flutter / Android / iOS / macOS 骨架
- README / LICENSE / CHANGELOG / 文档

## 发版步骤（网页）

1. 上传本包全部文件到仓库 main
2. Actions → Build Portable → Run workflow
3. tag_name: v1.2.0 ， create_release: true
4. Releases 下载 NetBridge-windows-x64.zip

## 使用注意

- 路由默认 bypass_cn，国内直连、国外代理
- 不要与其它客户端同时占用 7890
- 节点显示「超时」时请换节点；客户端已连接仅表示本地端口就绪
