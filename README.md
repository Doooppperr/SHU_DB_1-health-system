# 体检评价与健康档案系统

这是一个基于 Flask、Vue 3 和 SQLite 的本地健康档案管理系统，支持用户认证、体检机构浏览、健康档案录入、OCR 报告识别、亲友授权、趋势分析、AI 健康科普和评论审核。

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3、Vite、Vue Router、Pinia、Element Plus、Axios、ECharts |
| 后端 | Flask、Flask-SQLAlchemy、Flask-JWT-Extended、Flask-Cors |
| 数据库 | SQLite |
| OCR | 本地 Mock；可选接入华为云 OCR API |
| AI | DeepSeek V4 Flash；本地 FAQ 与测试 Mock |
| 本机演示服务 | Waitress、Vite Preview |
| 测试 | Pytest |

## 主要功能

- 注册、登录、图片验证码和 JWT 鉴权。
- 体检机构及套餐浏览。
- 手动创建健康档案和维护体检指标。
- 上传图片或 PDF，通过 OCR 解析并人工确认入档。
- 添加亲友、管理授权、代传亲友档案。
- 按用户和指标查看历史趋势。
- 登录前使用悬浮 AI 助手咨询注册、登录和系统功能。
- 登录后选择同一人的最多 5 份档案，获取指标科普和一般生活建议。
- 用户评论、管理员审核和用户管理。

## 项目结构

```text
health system/
├─ backend/
│  ├─ app/                         # Flask 应用
│  │  └─ ai/                       # AI 路由、DeepSeek 适配与安全策略
│  ├─ instance/health_system.db    # 本地 SQLite 数据库
│  ├─ tests/                       # 后端测试
│  ├─ .env.example                 # 可选环境变量模板
│  ├─ run.py                       # 开发入口
│  └─ wsgi.py                      # Waitress 入口
├─ frontend/                       # Vue 3 前端
├─ scripts/                        # Windows 一键启动脚本
└─ 项目文档/                       # 设计、测试和运行文档
```

## 环境要求

- Windows 10/11 和 PowerShell 5.1+
- Python 3.10+
- Node.js 18+
- npm 9+

## 首次安装

在项目根目录执行：

```powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Set-Location ..\frontend
npm install

Set-Location ..
```

如需配置真实 OCR 或修改默认账号：

```powershell
Copy-Item .\backend\.env.example .\backend\.env
```

数据库无需配置。系统固定使用本地文件：

```text
backend/instance/health_system.db
```

如果确实需要换用另一个本地 SQLite 文件，可在 `backend/.env` 设置：

```env
LOCAL_DATABASE_URL=sqlite:///another-local.db
```

数据库仍保留规范化和完整性优化：

- 表结构达到 3NF，核心候选键通过唯一约束落实。
- 22 个命名 CHECK 约束限制角色、状态、评分、价格等字段。
- 3 个命名联合唯一约束防止机构、套餐和指标字典重复。
- 每个 SQLite 连接自动启用外键检查。

模型变化后需要把新约束同步到已有本地数据库时执行：

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py
```

脚本会先备份原数据库，再重建表、复制数据并执行完整性验证。

## 本地开发

在项目根目录执行：

```powershell
.\scripts\start-full-dev.ps1
```

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:5050`
- 健康检查：`http://127.0.0.1:5050/api/health`

也可以单独启动：

```powershell
.\scripts\start-backend-dev.ps1
.\scripts\start-frontend-dev.ps1
```

## 本机生产演示

需要在本机验证构建产物或使用 Waitress 时执行：

```powershell
.\scripts\start-full-prod.ps1
```

- 前端：`http://127.0.0.1:4173`
- 后端：`http://127.0.0.1:5050`

该模式仍然读取同一个本地 SQLite 数据库，不需要任何远程服务。

## 默认账号

```text
用户名：admin
密码：admin123
```

该账号仅适合本地开发和演示。可在 `backend/.env` 中通过 `DEFAULT_ADMIN_*` 修改。

## OCR 配置

默认建议使用本地 Mock：

```env
OCR_PROVIDER=huawei
OCR_USE_MOCK=1
```

需要验证真实 OCR 时，将 `OCR_USE_MOCK` 改为 `0`，并填写 `.env.example` 中的 OCR Endpoint、AK、SK 和 Project ID。

## AI 助手配置

复制 `.env.example` 后，在被 Git 忽略的 `backend/.env` 中填写：

```env
AI_PROVIDER=deepseek
AI_USE_MOCK=0
DEEPSEEK_API_KEY=替换为新建的密钥
DEEPSEEK_MODEL=deepseek-v4-flash
AI_SUPPORT_PHONE=替换为人工客服电话
```

不要把真实 API Key 写入 `.env.example`、源码或提交记录。开发时可设置 `AI_USE_MOCK=1`，无需外部 API 即可验证界面和接口。

AI 对话不写入 SQLite；浏览器仅在当前标签页的 `sessionStorage` 中暂存最近 10 轮和更早摘要，用于刷新恢复。结束对话或退出登录会清空本次会话。选择体检档案后，前端会要求用户确认指标将发送至 DeepSeek API 处理。

使用方式：

- 未登录：点击可拖动的 AI 悬浮球，询问注册、登录、验证码、OCR 和其他公开系统功能。
- 已登录：可选择同一归属人的最多 5 份已确认档案；档案详情页会默认带入当前档案。
- 普通健康问题：解释指标和提供一般生活建议，不诊断疾病、不推荐处方药。
- 复杂问题：转人工客服；胸痛、呼吸困难、意识异常等疑似急症直接提示拨打 120。
- 桌面端：右侧栏默认约占页面三分之一，可拖动分隔条调整宽度；移动端使用全屏对话栏。

## 测试

```powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m pytest -q

Set-Location ..\frontend
npm run build
```

当前完整回归结果为后端 `54 passed`，前端生产构建通过。真实 API 验证使用本地 `.env`，密钥不会出现在测试输出或 Git 中。

## 数据备份

停止后端后，复制以下文件即可完成完整数据库备份：

```text
backend/instance/health_system.db
```

上传的报告文件保存在 `backend/uploads/`，如需保留也应一起备份。

AI 聊天不属于数据库备份内容；对话只存在于当前浏览器标签页会话中。

数据库结构升级脚本生成的
`health_system.before-normalization-*.db` 是自动备份，可在确认升级后按需保留。

## 文档

- [项目需求与技术方案](项目文档/项目需求与技术方案.md)
- [本地运行与演示指南](项目文档/本地运行与演示指南.md)
- [数据库设计说明](项目文档/数据库设计说明.md)
- [数据库规范化说明](项目文档/数据库规范化说明.md)
- [测试报告](项目文档/测试报告.md)
- [开发记录与上下文归档](项目文档/开发记录与上下文归档.md)
