# 康康健健 HealthDoc 后端

Flask 后端负责公开认证、三角色授权、个人健康资料、日常测量、体检登记、机构报告生产与匹配、机构运营、系统管理、亲友、评论、OCR 和健康 AI。本地使用 SQLite schema v3；服务器通过 `DATABASE_URL` 连接 GaussDB/openGauss，并支持从已验证 SQLite 快照执行显式全量同步。

## 环境与安装

要求 Python 3.10+。在 `backend` 目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
}
```

开发后端默认监听 <http://127.0.0.1:5050>，健康检查为 `GET /api/health`。

## 数据库与 schema v3

默认数据库为 `instance/health_system.db`。仓库跟踪这一份只含合成数据的演示快照，包含 5 个普通用户的丰富时间线；账号见 [`../项目文档/测试账号与演示数据.md`](../项目文档/测试账号与演示数据.md)。SQLite 连接启用外键；`PRAGMA user_version=3` 标识当前结构。新空库会直接创建 v3，非空旧库版本不匹配时拒绝启动。

```powershell
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py --check-only
.\.venv\Scripts\python.exe .\scripts\upgrade_local_database.py
```

v3 迁移会安全重建本地数据库，保留当前系统管理员账号及密码哈希，并把原数据库完整保存为时间戳备份。当前核心表包括：

- 平台与授权：`users`、`friend_relations`、`institutions`、`packages`、`institution_invites`、`institution_images`、`comments`；
- 指标字典：`indicator_categories`、`indicator_dicts`；
- 当前健康模型：`self_measurements`、`exam_registrations`、`institution_reports`、`report_indicators`。

## 角色与账号规则

- `user`：必须有唯一 `health_id`，不能绑定机构。
- `institution_admin`：必须绑定一个机构，不拥有健康身份码；同一机构可绑定多个账号。
- `admin`：不能绑定机构，也不拥有健康身份码。
- `is_active=false` 后，登录、刷新令牌及所有角色保护接口立即拒绝账号。
- 普通用户注册时健康身份码由服务端生成，前端不能指定或修改。
- 机构工作人员注册必须消费当前有效邀请码；邀请码每机构只有一行，重新生成覆盖当前值并使旧明文失效，数据库仅保存哈希。
- 系统管理员可停用/恢复账号。删除普通用户需显式 `confirm=true` 并级联其健康数据；删除机构账号保留报告及创建者用户名快照，只把创建者外键置空。

## 当前 API 分区

| 前缀 | 主要角色 | 内容 |
|---|---|---|
| `/api/auth` | 公开/登录用户 | 图片验证码、注册、登录、刷新、注销 |
| `/api/users/me` | 登录用户 | 当前账号与实时角色 |
| `/api/profile/me` | 普通用户 | 本人健康身份和个人健康资料 |
| `/api/self-measurements` | 普通用户 | 六类日常测量 CRUD |
| `/api/exam-registrations` | 普通用户 | 体检登记、列表及未匹配登记取消 |
| `/api/exam-reports` | 普通用户 | 已发布匹配报告只读列表与详情 |
| `/api/health/timeline` | 普通用户 | 本人或授权亲友统一时间线 |
| `/api/health/trends/{indicator_id}` | 普通用户 | 本人或授权亲友每日有效趋势 |
| `/api/friends` | 普通用户 | 亲友关系与授权状态 |
| `/api/institutions` | 登录用户 | 启用机构、详情和套餐浏览 |
| `/api/comments` | 用户/管理员 | 公开评论、我的评论和审核 |
| `/api/indicators/dicts` | 登录用户 | 指标字典 |
| `/api/org` | 机构账号 | 本机构资料、套餐、相册和报告生产 |
| `/api/admin` | 系统管理员 | 平台统计、机构、套餐、相册和邀请码 |
| `/api/users` | 系统管理员 | 账号列表、停用、恢复和删除 |
| `/api/ai` | 访客/普通用户 | FAQ、流式对话、报告列表和分析 |

所有受限接口都在服务端逐请求查询账号、角色、启用状态和机构绑定。前端隐藏菜单不是安全边界。

## 机构、套餐、相册和评论

- 机构和套餐采用 `is_active` 软停用，历史报告关系不因停用而物理删除。
- 机构/套餐名称及价格、适用性等字段由系统管理员或所属机构账号按权限维护。
- 每机构最多 8 张 JPEG、PNG 或 WebP 图片，单张最大 5 MB；服务端真实解码、修正方向、重编码并清除 EXIF。
- 相册排序一次提交完整 ID 集合并归一化；第一张作为公开封面。
- `/uploads/<path>` 只服务 `institution_images` 已登记的存储键，`reports/` 和孤儿文件返回 404。
- 用户只有在拥有当前机构的已发布匹配报告时才能发布评论；评论默认等待管理员审核，用户可查看和删除自己的评论。

## 自测、登记、匹配与报告状态机

### 日常测量

仅 `indicator_dicts.allow_self_measurement=true` 的六项可录入：`HEIGHT`、`WEIGHT`、`HR`、`TEMP`、`SPO2`、`FBG`。数值必须非负，同日允许多次记录。只能修改或删除本人自测。

### 体检登记

登记包含用户、机构、可选套餐和体检日期。套餐必须属于所选机构。同一用户同一体检日期只能存在一个未取消登记；已匹配登记不可取消。

### 机构报告

机构报告只属于登录账号当前绑定机构。状态流为：

```text
draft ──lock──> locked ──submit──> published
                          └───────> waiting_match ──later match──> published
published ──withdraw──> withdrawn
waiting_match ──60 days──> expired / physical cleanup
```

- `draft`：可修改受检者快照、体检日期、套餐和指标；可手工创建或 OCR 创建。
- `locked`：复核完成后锁定，删除草稿临时原文件；内容写接口从此返回 409。
- `published`：四项精确匹配成功并向用户可见。
- `waiting_match`：提交时暂未找到匹配登记/用户，设置 60 天到期时间。
- `withdrawn`：机构撤下，报告正文不再提供；时间线保留撤下状态事件，趋势和 AI 排除报告指标。

精确匹配使用：受检者真实姓名、健康身份码、体检日期、当前机构。服务只返回 `matched` 或 `not_found`，不会模糊搜索或泄露候选用户。匹配支持两个方向：用户先登记后提交，或机构先提交后用户登记。关键更新使用事务和条件更新防止重复占用。

应用启动会执行一次过期清理；相关查询也会惰性清理。独立命令：

```powershell
.\.venv\Scripts\python.exe .\scripts\cleanup_expired_reports.py
# 或 Flask CLI
flask --app wsgi:app cleanup-expired-reports
```

## 时间线、趋势与亲友隐私

- 时间线合并自测、体检登记和已发布机构报告，使用专用只读 DTO。
- 趋势按日期生成一个“每日有效值”：同日存在已发布机构指标时优先；否则使用当日时间最后的自测。
- 机构报告不含某指标时，该指标仍可从当天自测取值；报告撤下后趋势自动回退。
- 亲友访问每次重新验证当前授权状态。
- 亲友 DTO 只保留选择对象所需的账号 ID/用户名，并从健康事件中排除 `user_id`、`matched_user_id`、受检者姓名快照、健康身份码、真实姓名、生日、性别、邮箱、手机号、过敏史和既往史。
- 不存在与无权访问尽量统一为 404，减少对象存在性泄露。

## AI 助手

- 匿名用户只能访问公开 FAQ/导览，不能附带健康上下文。
- `GET /api/ai/records` 按需返回本人或授权亲友的可分析已发布报告元数据。
- `POST /api/ai/chat/stream` 使用 SSE；普通问题不读取报告，需要个人上下文但未选择时返回 `select_records` 动作。
- `POST /api/ai/analyze/stream` 支持同一归属人的单/多报告分析。
- `POST /api/ai/chat` 是非流式兼容接口。
- 每次附带报告必须显式 `consent: true`；报告、权限和状态逐请求重新校验。
- 事件仍为 `meta`、`status`、`delta`、`action`、`done`、`error`；不发送 Waitress 禁止的 `Connection` 头。
- 历史最多 20 条并做确定性裁剪；聊天和分析结果不写数据库，日志不记录消息正文、指标值或密钥。
- 当前上下文使用 `institution_reports` 与 `report_indicators`，趋势事实来自服务端每日有效序列；个人资料和健康身份码不会发送给模型。

真实模式配置见 `.env.example`。默认连接、读取、总截止为 5/30/60 秒；访客和登录用户默认每分钟 10/30 次进程内限流。

## OCR

- 当前入口：`POST /api/org/reports/ocr`，仅机构账号。
- 上传 PDF、PNG、JPEG 或 WebP；总请求上限 20 MiB，PDF 默认最多 8 页。
- `region-v2` 按表格区域独立解析，同时保留表格外文本；不依赖固定报告坐标。
- 指标仅映射当前字典中的代码、名称和别名。英文短代码必须精确命中；未知项目进入未匹配列表。
- 重复冲突、低置信度、非法数值和不安全单位必须人工复核，不能自动写成其他指标。
- OCR 产生一个 `draft` 报告、`input_source=ocr` 指标和诊断信息；之后使用普通草稿接口修订。
- 草稿可保留临时原文件用于复核；`lock` 时物理删除，数据库清空 `temporary_file_url`。

## 文件清理

本地孤儿文件脚本默认 dry-run，只读取 SQLite 引用并限制在 `backend/uploads`：

```powershell
.\.venv\Scripts\python.exe .\scripts\cleanup_local_runtime.py
.\.venv\Scripts\python.exe .\scripts\cleanup_local_runtime.py --apply
```

它不会修改数据库、虚拟环境、生产 openGauss 或上传根目录外文件。

## 启动

开发：

```powershell
.\.venv\Scripts\python.exe run.py
```

Waitress 本机演示推荐从项目根目录运行：

```powershell
.\scripts\start-backend-prod.ps1
```

脚本默认监听 `127.0.0.1:5050`，缺少 JWT 密钥时写入随机安全值。直接调用 Waitress 或对外监听时必须手工提供至少 32 字符的 `JWT_SECRET_KEY` 和至少 12 字符的 `DEFAULT_ADMIN_PASSWORD`。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

当前 v3 聚焦回归为 13 项，覆盖：schema 形状和迁移管理员哈希、丰富演示时间线与角色矩阵、全量快照迁移双向引用恢复、多机构账号、健康身份、两个方向精确匹配、锁定不可变、跨机构隔离、登记唯一性、过期清理、趋势优先/回退、亲友隐私、角色隔离、AI 同意/隐私、OCR Mock 与文件删除、普通用户级联删除及机构账号快照保留。

完整验收结论见 [`../项目文档/测试报告.md`](../项目文档/测试报告.md)。

## 生产数据库同步

`DATABASE_URL` 的优先级高于 `LOCAL_DATABASE_URL`。`initialize_or_validate_schema()` 对非 SQLite 的 `create_all()` 只负责空库初始化，不用于修改已有表。显式全量同步使用：

```powershell
.\.venv\Scripts\python.exe .\scripts\migrate_sqlite_to_gaussdb.py `
  --source .\instance\health_system.db --target-url $env:TARGET_DATABASE_URL --replace
```

脚本验证源库完整性与外键，创建完整目标 schema，处理登记/报告双向引用，复制全部表、重置生成序列并逐表核对行数。`--replace` 会清空目标应用表，只能在已备份且明确允许覆盖的演示环境使用；服务器发布入口见 `scripts/deploy-server.ps1 -SyncDemoDatabase`。
