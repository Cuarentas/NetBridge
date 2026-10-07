# GitHub 网页版发布流程（不使用本地 git 命令）

适用于仓库：https://github.com/你的用户名/NetBridge

---

## 一、上传 / 更新源码（网页）

### 新建仓库（若还没有）

1. 打开 https://github.com/new  
2. Repository name：`NetBridge`  
3. 选 Public，可勾选 Add README  
4. Create repository  

### 上传最终版文件

1. 打开仓库首页  
2. 若需整包覆盖：可先删除旧文件，或逐个进入目录上传  
3. 点击 **Add file** → **Upload files**  
4. 将本最终版解压后的**全部内容**拖入（保持目录结构）  
5. 底部 Commit changes → 提交到 `main`  

或：对单个文件点编辑（铅笔图标）粘贴后保存。

**必须包含：**

- `.github/workflows/portable-build.yml`  
- `desktop/netbridge_gui.py`  
- `flutter/`、`android_native/`、`README.md` 等  

---

## 二、用 Actions 打包并发布 Release

1. 仓库顶部点 **Actions**  
2. 左侧点 **Build Portable**（即 `portable-build.yml`）  
3. 右侧 **Run workflow**  
4. 填写：  
   - **tag_name**：`v1.0.0`（或 `v1.0.1`）  
   - **create_release**：`true`  
5. 点绿色 **Run workflow**  
6. 等待 15–40 分钟（多平台构建）  
7. 全部结束后打开 **Releases**  

应看到类似附件：

- `NetBridge-windows-x64.zip`  
- `NetBridge-linux-x64.tar.gz`  
- `NetBridge-macos.zip`  
- `NetBridge-android.apk`  
- `NetBridge-ios.zip`  

> Windows 成功即可发版；其它平台失败不一定阻断 Release。

---

## 三、仅用网页手动发 Release（可选）

若不想跑 Actions，可本机打好包后：

1. 仓库右侧 **Releases** → **Create a new release**  
2. Choose a tag：输入 `v1.0.0` → Create new tag  
3. Release title：`NetBridge 1.0.0`  
4. 描述里写更新说明  
5. 将 zip/apk 拖到 **Attach binaries**  
6. **Publish release**  

---

## 四、用户下载使用

1. 打开 Releases 最新版  
2. 下载对应系统文件  
3. Windows：解压 → 运行 `NetBridge.exe`  
4. 勾选系统代理 → 导入节点 → 连接  

默认代理端口：**1314**

---

## 五、常见问题

| 问题 | 处理 |
|------|------|
| Actions 失败 | 点进红色 job 看日志；Windows 优先保证成功 |
| Release 里有两个 Windows 包 | 编辑 Release 删掉带 `portable` 的旧文件；新工作流会自动清同 tag 旧附件 |
| 连接后上不了网 | 勾选系统代理；用 curl 测 `127.0.0.1:1314` |
| 改端口/功能不生效 | 需重新 Run workflow 打新包，不要只用旧 exe |

---

## 六、版本与端口（1.0.0）

- 产品版本：`1.0.0`  
- 默认混合端口：`1314`  
- SOCKS：`1315`  
- 核心：sing-box / Xray（构建时打入 Windows/Linux/macOS/Android 包）  
