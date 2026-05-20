# CLAUDE.md

帮一名上海高考学生分析错题的 Flask Web 应用。学生上传图片，后端用 OCR + LLM 分析，结果存 SQLite，前端呈现「四步分析 + 追问 + 练习题」闭环。

**这是有用户系统、后台任务、生产部署的 Web 应用，不是脚本工具。** 仓库根目录下的 `数学/ 物理/ 英语/ 语文/` 等目录是用户数据，不是源码。

---

## 不可违反的约束

### 用户数据隔离

每条涉及用户数据的 SELECT / UPDATE / DELETE **必须**带 `WHERE user_id = ?`。忘记加 = 数据泄漏。改动数据访问代码后跑 `tests/test_data_isolation.py`。

### 路径与数据目录

- 所有路径用 `os.path.join`，禁止硬编码斜杠方向，禁止平台特定模块。
- 新增数据目录必须在 `config.py` 定义常量，并在 `tests/conftest.py` 加入 monkeypatch——否则测试会读写真实数据目录。

### 数据库 Schema 变更

只能在 `database/__init__.py` 的 `_run_migrations()` 里加带 `_column_exists` 守卫的 `ALTER TABLE`。不要改 `init_db()` 里的 `CREATE TABLE`——生产库不会被重建。

### 认证

新增路由默认套 `@login_required`；`/admin/*` 用 `@admin_required`。忘记加 = 数据泄漏。

### 教学逻辑

四步分析流程、苏格拉底式提问风格、JSON 输出格式、LaTeX 转义规则全定义在 `prompts/*.txt`。改教学法 → 改 prompt 文件；改调用链/存储 → 改 services。不要把教学语句硬编码进 Python。

### LLM 提供商

按提供商显式命名常量（`DEEPSEEK_*` / `ANTHROPIC_*` / `DOUBAO_*` / `KIMI_*`），不要新增泛型别名。加新提供商：在 `config.py` 加常量，在 `services/analysis_service.py` 加分支。

### 时区

数据库存 UTC，模板显示时间一律走 `localtime` Jinja 过滤器转 Asia/Shanghai，不要在别处转换。

### 跨平台

代码须同时在 Windows 和 macOS 上运行。禁止 `fcntl`、`os.fork`、平台特定信号。Shell 脚本只放 `deploy/`，只在 Linux 服务器运行。

---

## 协作规则

- **新功能必须附带测试**：新增路由或业务逻辑时，同步在 `tests/` 下添加对应测试用例，跑 `pytest tests/` 确认通过。
- **遇到复杂或多选项问题先问**：不确定实现方向、或存在多种合理方案时，先向用户说明选项和权衡，再动手。
- **不自动 commit**：除非用户明确要求，不执行 `git commit`。

---

## 开发工作流

```bash
python -m venv venv && pip install -r requirements.txt
python app.py          # debug 模式，端口 5001，首次自动 init_db()

# paddleocr / volcengine 不需要装（函数内懒加载，测试不触达）
pip install -r requirements-test.txt && pytest tests/
```

API key 写入 `.claude/apikey`（`KEY=VALUE` 格式，已 `chmod 600`，不要提交）：

```
DEEPSEEK_API_KEY=sk-...
DOUBAO_API_KEY=...
MOONSHOT_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

部署见 `deploy/README_DEPLOY.md`，日常运维用 `./deploy/restart.sh`。
