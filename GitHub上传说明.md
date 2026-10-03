# GitHub 上传说明（先用这份文档）

本文件夹是**专门用于上传到 GitHub 的干净副本**，与本机工作目录互相独立，
删除它不会影响本机运行，本机的一切改动也不会自动同步到这里。

---

## 一、本文件夹包含什么

| 类别 | 内容 | 为什么上传 |
| --- | --- | --- |
| 前端源码 | `src/`、`index.html`、`vite.config.js` | 项目本体 |
| 后端源码 | `server/`、`run_scan.py` | 项目本体 |
| 依赖清单 | `package.json`、`package-lock.json`、`requirements.txt` | 别人据此还原依赖 |
| 业务数据 | `data/notices.json`（22.9 MB）、`data/community_posts.json` | **保证下载即可看到与本机相同的通知内容** |
| 配置模板 | `.env.example` | 告诉使用者该配什么，但不给密码 |
| 文档 | `README.md`、`docs/ARCHITECTURE.md`、本文件、`修改说明与已知限制.md`、`对比报告_当前文件夹_vs_v0.5zip.txt` | 说明义务 |
| 工具脚本 | `tools/`、`smoke/`、`start.ps1`、`tools/start-safe.ps1` | 运行与自检 |
| 启动脚本 | `启动一键山大.bat`、`停止一键山大.bat` | 双击即用 |
| 新增 | `安装依赖.bat` | 给下载者的一键装依赖入口（本机不需要） |

## 二、本文件夹**没有**什么（已排除，约 190 MB）

| 排除项 | 体积 | 原因 |
| --- | --- | --- |
| `node_modules/` | 76 MB | `npm install` 可还原 |
| `data/backups/` | 75 MB | 抓取备份快照 |
| `data/history.json` | 20 MB | 与 notices 重复的归档 |
| `dist/` | 317 KB | 构建产物，`npm run build` 可还原 |
| `.venv/`、`.git/`、`.pytest_cache/`、`__pycache__/` | — | 虚拟环境与缓存 |
| `server.log*`、`nul` | — | 运行残留 |
| `.env` | — | **含管理员密码，绝不能公开** |

---

## 三、别人下载后如何复现本机效果

1. 安装 **Python 3.10+** 与 **Node.js 18+**；
2. 双击 **`安装依赖.bat`** —— 依次完成：
   创建 `.venv` → 安装后端依赖 → `npm install` → `npm run build` 生成 `dist/`；
3. 双击 **`启动一键山大.bat`** —— 自动探测空闲端口、拉起后端、打开浏览器；
4. 界面内容与本机一致：`data/notices.json` 已随仓库提供，打开即有通知数据。

> 若对方网络不佳，可手动换源：
> `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`
> `npm config set registry https://registry.npmmirror.com`

---

## 四、密码已移出源码（本次改动）

公开仓库会把代码里的一切暴露给全世界，因此社区管理密码做了外置：

| 位置 | 改动 |
| --- | --- |
| `server/main.py` | 删除管理员密码硬编码；改为读取**环境变量** `COMMUNITY_ADMIN_PASSWORD`，其次读取仓库根 `.env`；新增 `verify_admin_password()`，四处置管理端接口统一调用。**未配置密码时一律拒绝访问**，避免公开后变成无人把关的开放审核台。 |
| `src/pages/CommunityPage.jsx` | 删除前端硬编码的管理员密码常量；密码校验改为完全由后端裁决。**页面结构、文案、DOM 一行未动。** |
| `.gitignore` | 新增 `.env`、`.env.*`（保留 `!.env.example`） |
| `.env.example` | 新增模板，仅含空的键名 |

**你本机怎么继续用原来的功能：** 工作目录已生成 `.env`（内容就是原来的密码），
一行未改地保留了原有行为；重启后端即生效。`.env` 已被 `.gitignore` 排除，不会被上传。

**下载者怎么用：** 复制 `.env.example` 为 `.env`，填入自己设的密码即可。不填则审核台进不去。

---

## 五、上传前的三条硬性检查

1. **不要直接推送原仓库的 Git 历史。** 本机那次提交的作者是山大邮箱，且历史里含明文密码，
   推送等于公开放学邮箱学号。本文件夹是全新历史，请上传**这一个**。
2. **确认 `.env` 不在上传列表里。** 网页拖拽时勿手动选中它（它默认隐藏，正常不会选中）。
3. **`data/notices.json` 是 22.9 MB。** GitHub 网页端单文件上限约 25 MB，勉强能过但容易超时；
   若拖拽失败，改用 **GitHub Desktop**（推荐）或命令行 `git push`。

---

## 六、上传步骤（网页版）

1. 浏览器打开 `https://github.com/new`，仓库名填 `yijian-sdu`；
2. **不要勾选** Add a README file / Add .gitignore / Choose a license（保持完全空仓库）；
3. 创建后进入空仓库页，点击 **uploading an existing file**；
4. 把本文件夹内的**全部文件和文件夹**拖进上传框（注意别拖 `.env`，它没有也不会出现）；
5. 底部填 Commit message，例如 `feat: 一键山大 v0.5 全官方来源版`，点 **Commit changes**；
6. 若之后会用本机 git 提交，先到 https://github.com/settings/emails
   勾选 **Keep my email addresses private**，避免私人邮箱出现在公开提交历史里。

> 若 5 分钟仍未上传完，多半是 22.9 MB 的那份数据卡住了，直接换 GitHub Desktop 更省时间。
