# 康迹 HealthHub：健康档案管理系统

康迹 HealthHub 是一个基于 Flask、Vue 3 和 SQLite 的本地 Web 应用。系统以个人健康档案和指标趋势为核心，提供公开门户、独立登录/注册页，以及普通用户、机构管理员、系统管理员三套隔离工作台。

## 当前实现

- 公开门户：根路由 / 展示项目介绍、核心功能、使用流程、隐私提示和关于我们；登录、注册使用独立品牌化页面。
- 普通用户：进入 /dashboard，可管理健康档案、OCR 报告、指标趋势、亲友授权、机构服务、评论和健康 AI。
- 机构管理员：进入 /org/dashboard，只管理所属机构资料、相册和套餐，并只读查看来源于本机构且已确认的脱敏健康数据。
- 系统管理员：进入 /admin/dashboard，管理机构、套餐、邀请码、用户角色、机构管理员、全局档案和评论审核。
- 档案来源可选：手工录入和 OCR 入档均可选择“暂不选取”机构与套餐；未关联机构不影响指标、趋势和健康 AI。
- SQLite schema v2：继续使用现有 SQLite，不依赖 MySQL、PostgreSQL 或云数据库。

## 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3、Vite 6、Vue Router、Pinia、Element Plus、Axios、ECharts 6 |
| 后端 | Flask 3、Flask-SQLAlchemy、Flask-JWT-Extended、Flask-Cors |
| 数据库 | SQLite，PRAGMA user_version=2 |
| 图片处理 | Pillow，服务端解码、重编码并清除 EXIF |
| OCR | 本地 Mock；可选华为云 OCR API |
| AI | DeepSeek V4 Flash；本地 FAQ 与测试 Mock |
| 本机演示服务 | Waitress、Vite Preview |
| 测试 | Pytest、Vitest、Vue Test Utils、jsdom |

## 项目结构

~~~text
health system/
├─ backend/
│  ├─ app/
│  │  ├─ admin/                    # 系统管理员接口
│  │  ├─ org/                      # 机构管理员运营接口
│  │  ├─ institution_health/       # 机构健康数据只读接口
│  │  └─ ...
│  ├─ instance/health_system.db    # 本地 SQLite 正式数据库
│  ├─ scripts/upgrade_local_database.py
│  └─ tests/
├─ frontend/
│  └─ src/
│     ├─ layouts/                  # 三角色工作台布局
│     ├─ views/admin/
│     ├─ views/org/
│     └─ ...
├─ scripts/                        # Windows 本地启动脚本
└─ 项目文档/
~~~

## 环境要求

- Windows 10/11 和 PowerShell 5.1+
- Python 3.10+
- Node.js 20+
- npm 10+

## 首次安装

在项目根目录执行：

~~~powershell
Set-Location .\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Set-Location ..\frontend
npm install

Set-Location ..
~~~

如需配置真实 OCR、AI 或修改默认管理员，复制环境变量模板：

~~~powershell
Copy-Item .\backend\.env.example .\backend\.env
~~~

真实密钥只允许写入被 Git 忽略的 backend/.env。

## SQLite schema v2

正式数据库仍是：

~~~text
backend/instance/health_system.db
~~~

当前已完成 v2 迁移并验证：

| 项目 | 当前值 |
|---|---:|
| PRAGMA user_version | 2 |
| users | 2 |
| institutions | 3 |
| packages | 15 |
| health_records | 12 |

v2 增加三角色约束、机构管理员绑定、机构与套餐停用状态、邀请码和机构相册。新安装会直接创建 v2 空库并执行种子初始化；旧版非空数据库不会被 create_all 半升级，而会提示先执行迁移脚本。

检查或迁移已有数据库：

~~~powershell
Set-Location .\backend
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py --check-only
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py
~~~

迁移会先创建 health_system.before-schema-v2-时间戳.db 备份，在临时库重建并复制数据，验证主键、行数、外键、唯一约束、角色约束和 integrity_check 后再原子替换正式文件。重复运行对已是 v2 的数据库不会再次迁移。

如需改用另一个本地 SQLite 文件，可在 backend/.env 设置：

~~~env
LOCAL_DATABASE_URL=sqlite:///another-local.db
~~~

## 本地启动

开发模式：

~~~powershell
.\scripts\start-full-dev.ps1
~~~

- 前端：http://127.0.0.1:5173
- 后端：http://127.0.0.1:5050
- 健康检查：http://127.0.0.1:5050/api/health

本机生产演示：

~~~powershell
.\scripts\start-full-prod.ps1
~~~

项目生产脚本默认只监听 `127.0.0.1`。本机首次运行时，脚本会自动在被 Git 忽略的 `backend/.env` 生成随机 JWT 密钥，并启用回环地址专用演示模式，因此无需手工配置即可继续使用本地演示账号。若改为 `0.0.0.0` 或其他对外地址，则必须设置至少 12 字符的 `DEFAULT_ADMIN_PASSWORD`；JWT 密钥可由脚本生成，也可显式提供至少 32 字符的安全值。

- 前端：http://127.0.0.1:4173
- 后端：http://127.0.0.1:5050

两个模式均读取同一个本地 SQLite 文件，不需要远程数据库。

如果终端出现 `Production startup requires an explicit JWT_SECRET_KEY`，说明使用的是旧启动脚本或直接调用了 Waitress。关闭失败进程后，从项目根目录重新运行 `.\scripts\start-full-prod.ps1`；新版脚本会在本机回环模式下自动初始化随机密钥。直接调用 Waitress 时则必须手工配置 `.env`。

## 三角色入口与账号

| 角色 | 登录后入口 | 说明 |
|---|---|---|
| 普通用户 user | /dashboard | 可直接注册，不需要邀请码 |
| 机构管理员 institution_admin | /org/dashboard | 由系统管理员签发所属机构邀请码后，在注册页选择工作人员注册并填写邀请码 |
| 系统管理员 admin | /admin/dashboard | 管理全局机构、邀请码、角色、档案和评论 |

开发模式默认本地管理员：

~~~text
用户名：admin
密码：admin123
~~~

该密码只允许用于开发或仅监听回环地址的本机演示，不能用于局域网或公网监听。机构邀请码单次使用、永不过期，数据库只保存哈希，明文仅在签发时显示一次。每个机构最多一个机构管理员；撤销后账号降级为普通用户，个人数据保留。

## 关键业务与隐私规则

- 健康档案的机构和套餐均可为空；选择套餐时会推导所属机构，清空机构时同步清空套餐。
- 只有来源机构明确且状态为 confirmed 的标准化数据，才会向该机构管理员只读开放。
- 机构管理员接口不返回邮箱、手机号、上传人或原始报告，也不能修改、补录或删除用户档案。
- 原始报告通过鉴权接口 /api/records/{id}/file 访问；公共 /uploads 只允许数据库登记的机构图片，孤儿文件和 reports/ 路径均返回 404。
- 机构和套餐采用软停用，保留历史档案来源。
- 每家机构最多上传 8 张 JPEG、PNG 或 WebP 图片；单张不超过 5 MB，排序第一张为封面。
- 只有普通用户可以向健康 AI 提交档案 ID；两类管理员工作台不显示健康 AI。
- AI 对话不写入 SQLite；浏览器只在当前标签页 sessionStorage 中保存会话上下文。

## OCR 与 AI

离线演示建议：

~~~env
OCR_USE_MOCK=1
AI_USE_MOCK=1
~~~

真实 OCR 需配置华为云 Endpoint、AK、SK 和 Project ID。真实 AI 需在 backend/.env 中配置 DEEPSEEK_API_KEY；系统只提供指标科普和一般生活建议，不做诊断、处方或急症替代处理。

## 验证

~~~powershell
Set-Location .\backend
.\.venv\Scripts\python.exe -m pytest -q

Set-Location ..\frontend
npm test
npm run build
npm audit --omit=dev
~~~

当前验证结果：

- 后端：81 passed。
- 前端：3 个测试文件、12 个测试通过。
- 前端生产构建：通过。
- 生产依赖审计：0 vulnerabilities。
- SQLite：user_version=2，外键检查无违规，integrity_check=ok。

## 备份

停止后端后，至少备份：

- backend/instance/health_system.db
- backend/uploads/ 整个目录（机构相册、兼容旧 logo 与原始报告）

迁移脚本产生的 health_system.before-schema-v2-*.db 是升级前自动备份。恢复时应先停止后端，核对目标文件后再替换正式数据库。

## 文档

- [项目需求与技术方案](项目文档/项目需求与技术方案.md)
- [本地运行与演示指南](项目文档/本地运行与演示指南.md)
- [数据库设计说明](项目文档/数据库设计说明.md)
- [数据库规范化说明](项目文档/数据库规范化说明.md)
- [测试报告](项目文档/测试报告.md)
- [开发记录与上下文归档](项目文档/开发记录与上下文归档.md)
- [PDF 交付物待更新清单](项目文档/PDF交付物待更新清单.md)
