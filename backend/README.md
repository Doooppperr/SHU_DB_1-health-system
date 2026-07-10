# Health System Backend

## 安装

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 数据库

后端使用本地 SQLite：

```text
instance/health_system.db
```

开发入口和 Waitress 入口使用同一个数据库。首次使用空数据库时，应用会自动建表并写入机构、套餐、指标字典和默认管理员等种子数据。

SQLite 连接会自动执行：

```sql
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

数据库模型包含候选键唯一约束和 22 个命名 CHECK 约束。

如需切换到另一个本地数据库，可在 `.env` 设置：

```env
LOCAL_DATABASE_URL=sqlite:///another-local.db
```

## 升级已有数据库结构

SQLite 无法通过普通 `ALTER TABLE` 添加大部分表级约束。模型约束发生变化后执行：

```powershell
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py
```

只检查当前数据库是否缺少约束：

```powershell
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py --check-only
```

升级过程会：

1. 按当前 SQLAlchemy 模型创建临时数据库。
2. 按外键依赖顺序复制所有数据。
3. 校验行数、外键、约束和 SQLite 完整性。
4. 生成 `instance/health_system.before-normalization-*.db` 备份。
5. 原子替换正式数据库文件。

## 开发启动

```powershell
.\.venv\Scripts\python.exe run.py
```

默认地址：`http://127.0.0.1:5050`

## Waitress 演示启动

```powershell
.\.venv\Scripts\python.exe -m waitress --listen=0.0.0.0:5050 --threads=8 wsgi:app
```

项目根目录也提供：

```powershell
.\scripts\start-backend-dev.ps1
.\scripts\start-backend-prod.ps1
```

## AI 助手

AI 接口为 `POST /api/ai/chat`，支持匿名系统导览和登录后的健康科普。默认模型为非思考模式的 `deepseek-v4-flash`：

```env
AI_PROVIDER=deepseek
AI_USE_MOCK=0
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
AI_SUPPORT_PHONE=
```

后端不会保存聊天记录。请求最多接收 10 轮完整历史和 5 份同一归属人的已确认档案；超出 10 轮时先把最早一轮合并进摘要。未登录用户只能使用 FAQ 和公开系统说明，不能附加健康档案。

自动化测试或离线演示可设置：

```env
AI_USE_MOCK=1
```

真实 API Key 只能保存在被 Git 忽略的 `.env` 中。

请求示例：

```json
{
  "message": "请解释空腹血糖指标",
  "history": [],
  "summary": "",
  "selected_record_ids": [1, 2]
}
```

响应包含 `reply`、`decision`、`source`、`summary` 和 `compacted_count`。`decision` 可能为：

- `answer`：允许返回的系统说明或健康科普。
- `support`：复杂问题，后端丢弃模型生成的诊疗内容并替换成人工客服模板。
- `emergency`：疑似急症，固定提示拨打 120。

安全与隐私规则：

- 匿名请求不能附加档案；登录请求由 JWT 确定当前用户。
- 档案 ID 在后端重新检查本人、管理员或已授权亲友权限，不能依赖前端选择结果。
- 只允许同一归属人的最多 5 份已确认档案。
- DeepSeek 使用 `deepseek-v4-flash` 非思考模式和 JSON Output；API Key 不下发前端。
- 匿名与登录用户分别限流；提示词、对话和指标不写入日志或数据库。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试使用独立的内存 SQLite，不会修改 `instance/health_system.db`。

当前完整测试结果：`54 passed`。测试使用 AI Mock 和伪造 HTTP 响应验证模型契约，不消耗真实 API 额度。

## OCR

本地开发建议：

```env
OCR_USE_MOCK=1
```

如需真实 OCR，在 `.env` 中配置 `HUAWEI_OCR_ENDPOINT`、`HUAWEI_OCR_AK`、`HUAWEI_OCR_SK` 和 `HUAWEI_PROJECT_ID`。
