# 使用说明

## 普通用户

1. 打开 https://github.com/Cuarentas/NetBridge/releases
2. Windows：下载 `NetBridge-windows-portable.zip`，解压，运行 `NetBridge.exe`
3. Linux：下载 `NetBridge-linux-x64.tar.gz`，解压后执行：
   ```bash
   chmod +x netbridge
   ./netbridge
   ```

当前版本界面可正常使用，连接按钮为演示（不改变系统代理、不转发流量）。

## 从 Actions 取包

若 Release 附件不全，可到对应 workflow 运行页底部 **Artifacts** 下载（保留约 90 天）。

## 开发者重新发版

Actions → Build Portable → Run workflow → 填写新 tag → 发布。
