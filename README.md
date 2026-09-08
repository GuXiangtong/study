# study

Gao Kao boost project — 上海高考错题分析 Flask Web 应用。

学生上传错题图片，后端用 OCR + LLM 做「四步分析 + 追问 + 练习题」，结果存 SQLite。

> 本地开发说明见 [CLAUDE.md](CLAUDE.md)，完整部署说明见 [deploy/README_DEPLOY.md](deploy/README_DEPLOY.md)。

---

## 生产运维

生产环境部署在服务器 `/opt/tong-study`，用 `systemd`（服务名 `tong-study`）+ gunicorn + nginx 运行。日常运维用 `deploy/` 下的脚本。

### 更新程序（拉取最新代码并重启）

在服务器上执行：

```bash
cd /opt/tong-study
./deploy/update.sh
```

`update.sh` 会自动：
1. 从 GitHub 拉取 `main` 分支最新代码（已是最新则直接退出）
2. 若 `requirements.txt` 有变化则安装新依赖
3. `systemctl restart tong-study` 并检查启动状态

**常见问题：拉取被本地改动挡住**

如果看到：

```
error: Your local changes to the following files would be overwritten by merge:
	.claude/apikey
Aborting
```

这是因为服务器上的 `.claude/apikey`（生产密钥）与仓库里的版本不同。先备份密钥再更新：

```bash
cd /opt/tong-study
cp .claude/apikey /tmp/apikey.server.bak     # 1. 备份真实密钥
git checkout -- .claude/apikey               # 2. 放弃本地改动，让合并通过
./deploy/update.sh                           # 3. 更新（此后 .claude/apikey 已不再被跟踪）
cp /tmp/apikey.server.bak .claude/apikey      # 4. 恢复真实密钥
chmod 600 .claude/apikey                      # 5. 收紧权限
```

> `.claude/` 已在 `.gitignore` 中，密钥不随代码同步 —— 各环境的 `.claude/apikey` 各自独立维护。

### 重启服务

```bash
cd /opt/tong-study
./deploy/restart.sh            # 重启应用（默认）
./deploy/restart.sh all        # 重启应用 + Nginx
./deploy/restart.sh status     # 查看状态与最近日志
./deploy/restart.sh logs       # 实时查看日志（Ctrl+C 退出）
./deploy/restart.sh stop       # 停止服务
./deploy/restart.sh start      # 启动服务
```

### 更换 API Key

密钥存在 `/opt/tong-study/.claude/apikey`，`KEY=VALUE` 一行一个，权限 `600`，**不提交到 git**。支持的键：

```
DEEPSEEK_API_KEY=sk-...
DOUBAO_API_KEY=...
MOONSHOT_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

更换步骤：

```bash
cd /opt/tong-study
cp .claude/apikey .claude/apikey.bak    # 先备份，便于回滚
vi .claude/apikey                       # 修改对应的 KEY=VALUE 行
chmod 600 .claude/apikey                # 确认权限
./deploy/restart.sh                     # 重启使新密钥生效
```

> 密钥在进程启动时读取（`config.py`），改完**必须重启**才生效。
> 若同名环境变量已设置，`.claude/apikey` 文件中的值优先。

**保持开发机与生产密钥一致**：不要把密钥提交进 git（本仓库为公开仓库，会泄漏）。需要同步时，从可信一方直接拷贝文件：

```bash
# 在开发机执行，把本地密钥推送到服务器
scp /Users/I032060/my-project/tong-study/.claude/apikey deploy@47.116.69.25:/opt/tong-study/.claude/apikey
```
