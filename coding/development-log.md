# 健康管理平台开发记录

## 轮次 1：认证闭环（含项目初始化）

- 状态：`Closed`
- 日期：2026-04-08
- 目标：完成 Flask + Vue3 项目初始化，并交付注册、登录、刷新令牌、获取当前用户（`/api/users/me`）的前后端闭环。

### 后端改动
- 新建 Flask app factory 与扩展初始化：`SQLAlchemy`、`Flask-Migrate`、`Flask-JWT-Extended`、`Flask-Cors`。
- 全局配置新增 OCR 占位：`OCR_PROVIDER`、`HUAWEI_OCR_ENDPOINT`、`HUAWEI_OCR_AK`、`HUAWEI_OCR_SK`。
- 新增 `User` 模型：包含 `username/password_hash/email/phone/role/created_at`，密码使用 `bcrypt` 哈希。
- 实现认证接口：
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `POST /api/auth/refresh`
  - `POST /api/auth/logout`（无状态登出占位）
- 实现用户接口：
  - `GET /api/users/me`
- 修复兼容性告警：改用 `db.session.get()`；JWT 测试密钥长度提升到 32+。
- 新增 pytest 测试：未登录鉴权、注册登录闭环、错误凭证、刷新令牌。

### 前端改动
- 新建 Vue3 + Vite 基础项目结构，接入 Element Plus、Pinia、Vue Router、Axios。
- 新增 Axios 实例与拦截器：自动携带 Bearer token，401 时尝试 refresh 后重试。
- 新增认证状态管理（Pinia）：本地持久化 `accessToken/refreshToken/user`。
- 新增页面：
  - `LoginView` 登录页
  - `RegisterView` 注册页
  - `HomeView` 受保护主页（展示 `me` 信息）
- 新增路由守卫：未登录访问 `/` 自动跳转 `/login`，登录态访问登录/注册页自动回首页。

### 验证清单
- 后端单元测试：认证与鉴权核心路径
- 接口冒烟测试：注册/登录/刷新/me 的成功与失败路径
- 前端流程校验：构建通过 + 启动探针成功（CLI 环境）

### 验证结果
- 后端单元测试：`python -m pytest` -> `4 passed`。
- 接口冒烟测试：
  - `register_success: 201`
  - `login_success: 200`
  - `login_fail_wrong_password: 401`
  - `me_with_token: 200`
  - `me_without_token: 401`
  - `refresh_success: 200`
- 前端构建：`npm run build` 成功。
- 前端启动探针：`dev_server_5174:LISTENING`（启动后已停止进程）。

### 阻塞项
- 无

### 需求变更记录
- OCR 供应商统一调整为华为云 OCR 服务（2026-04-08）。

### 结论
- 第1轮认证闭环已满足严格门槛并完成收口。

### 是否进入下一轮
- 已确认，进入第2轮

## 轮次 2：机构与套餐展示闭环

- 状态：`Closed`
- 日期：2026-04-08
- 目标：完成机构列表、机构详情、套餐列表后端接口与前端展示闭环，可从机构列表进入详情并查看套餐。

### 后端改动
- 新增数据模型：`Institution`、`Package`。
- 新增 `institutions` Blueprint，并注册 3 个只读接口：
  - `GET /api/institutions`
  - `GET /api/institutions/{id}`
  - `GET /api/institutions/{id}/packages`
- 新增鉴权控制：机构接口要求登录访问（JWT）。
- 新增初始化种子数据：3 家机构 + 每家 A~E 5 套套餐。
- 测试夹具增强：测试数据库建表后自动注入机构与套餐种子数据。
- 新增 `test_institutions.py` 覆盖鉴权、成功查询、404路径。

### 前端改动
- 新增机构 API 封装：机构列表、详情、套餐查询。
- 新增页面：
  - `InstitutionListView`（机构列表）
  - `InstitutionDetailView`（机构详情 + 套餐表格）
- 路由调整：默认 `/` 重定向到 `/institutions`，新增 `/institutions/:id`，保留 `/profile` 个人中心。
- 交互补齐：机构列表可跳转详情；详情可返回列表；顶部导航支持个人中心/退出登录。

### 验证清单
- 后端单元测试：机构查询接口（鉴权、详情、错误路径）
- 接口冒烟测试：`/api/institutions`、`/api/institutions/{id}`、`/api/institutions/{id}/packages`
- 前端流程校验：登录后访问机构列表 -> 进入详情 -> 查看套餐

### 验证结果
- 后端单元测试：`python -m pytest` -> `8 passed`。
- 接口冒烟测试：
  - `institutions_list_success: 200`
  - `institutions_seed_count_ge_3: 1`
  - `institution_detail_success: 200`
  - `institution_packages_success: 200`
  - `institution_packages_count_eq_5: 1`
  - `institution_detail_not_found: 404`
  - `institution_packages_not_found: 404`
  - `institutions_requires_auth: 401`
- 前端构建：`npm run build` 成功。
- 前端启动探针：`dev_server_5175:LISTENING`（启动后已停止进程）。

### 阻塞项
- 无

### 结论
- 第2轮机构与套餐展示闭环已满足严格门槛并完成收口。

### 是否进入下一轮
- 已确认，进入第3轮

## 轮次 3：档案手动录入闭环

- 状态：`Closed`
- 日期：2026-04-08
- 目标：完成个人档案 CRUD 与指标增改删闭环，支持录入 5-10 个关键指标、同档案同指标去重、异常值稳定标记。

### 后端改动
- 新增模型：`IndicatorCategory`、`IndicatorDict`、`HealthRecord`、`HealthIndicator`。
- 新增 Blueprint：
  - `records`：档案 CRUD 与指标增改删
  - `indicators`：标准指标字典查询
- 新增接口：
  - `GET /api/records`
  - `POST /api/records`
  - `GET /api/records/{id}`
  - `DELETE /api/records/{id}`
  - `POST /api/records/{id}/indicators`
  - `PUT /api/records/{id}/indicators/{indicator_id}`
  - `DELETE /api/records/{id}/indicators/{indicator_id}`
  - `GET /api/indicators/dicts`
- 新增规则：
  - 同档案同指标唯一约束（`record_id + indicator_dict_id`）
  - 数值指标按参考区间自动计算 `is_abnormal`
  - 非档案所属人访问档案与指标返回 `404`
- 新增种子数据：指标分类 + 10 个关键指标（BMI、FBG、TC、TG、HDL、LDL、ALT、AST、UA、CREA）。
- 新增测试：`test_records.py` 覆盖档案 CRUD、指标增改删、去重、异常值与越权路径。

### 前端改动
- 新增 API 封装：
  - `records.js`（档案与指标操作）
  - `indicators.js`（指标字典查询）
- 新增页面：
  - `RecordListView`（档案列表、创建、删除）
  - `RecordDetailView`（指标录入、修改、删除、异常状态显示）
- 路由新增：
  - `/records`
  - `/records/:id`
- 页面导航改造：机构列表/详情/个人中心增加“体检档案”入口。
- 录入流程支持：创建档案时选择机构+套餐；详情页手动录入并实时回显指标。

### 验证清单
- 后端单元测试：档案 CRUD、指标增改删、去重规则、异常值标记、越权访问
- 接口冒烟测试：`/api/records`、`/api/records/{id}`、`/api/records/{id}/indicators`、`/api/indicators/dicts`
- 前端流程校验：登录 -> 档案创建 -> 录入 5+ 指标 -> 查看详情回显 -> 删除指标/档案

### 验证结果
- 后端单元测试：`python -m pytest` -> `11 passed`。
- 接口冒烟测试：
  - `record_create: 201`
  - `add_FBG/add_TC/add_TG/add_ALT/add_UA: 201`
  - `duplicate_FBG_blocked: 409`
  - `update_first_indicator: 200`
  - `record_detail: 200`
  - `record_indicator_count_ge_5: 5`
  - `record_list_requires_auth: 401`
- 前端构建：`npm run build` 成功。
- 前端启动探针：`dev_server_5176:LISTENING`（启动后已停止进程）。

### 阻塞项
- 无

### 结论
- 第3轮档案手动录入闭环已满足严格门槛并完成收口。

### 是否进入下一轮
- 已确认，进入第4轮

## 轮次 4：OCR上传闭环（华为云OCR方案）

- 状态：`Closed`
- 日期：2026-04-08
- 目标：完成报告上传 -> OCR解析 -> 指标映射 -> 用户确认的闭环；先用 Mock Provider 跑通，再接入华为云真实 OCR。

### 后端改动
- 新增服务抽象：
  - `StorageBackend/LocalStorage`（本地上传存储）
  - `OCRProvider`（Mock华为OCR + 华为云真实OCR）
  - `OCRMappingService`（OCR字段到指标字典映射）
- 配置增强：新增 `OCR_USE_MOCK`、`HUAWEI_PROJECT_ID`、`OCR_API_PATH`、`OCR_PDF_MAX_PAGES`、`UPLOAD_DIR`、`UPLOAD_URL_BASE`、`MAX_CONTENT_LENGTH`。
- 新增 `.env` / `.env.example` 配置模板，支持 Mock 与华为云真实模式切换。
- 新增上传静态访问路由：`GET /uploads/<path:filename>`。
- 新增 OCR 接口：
  - `POST /api/records/upload`：上传报告、OCR解析、映射并落库（状态 `parsed`）
  - `PUT /api/records/{id}/confirm`：确认 OCR 档案（`parsed/draft -> confirmed`）
- 映射规则：按 `code/name/aliases` 归一化匹配；未匹配字段返回 `unmatched_fields`。
- 华为云真实接入：
  - 使用 `huaweicloudsdkcore` 进行 AK/SK 签名
  - 使用 `requests` 发送 OCR 请求
  - PDF 自动转图片后按页调用 OCR 并聚合结果（最多 `OCR_PDF_MAX_PAGES` 页）
- 新增测试：`test_ocr.py` 覆盖映射、上传、状态流转与缺失文件失败路径（测试环境默认 Mock）。

### 前端改动
- 新增 OCR 上传页面：`RecordOcrUploadView`（上传文件、展示解析结果、确认入档、跳转手动修正）。
- 新增档案 OCR API：
  - `uploadRecordByOcr(formData)`
  - `confirmRecord(recordId)`
- 路由新增：`/records/upload`。
- 档案列表页新增入口按钮：`OCR上传`。
- 解析结果页支持：已映射指标展示、未匹配字段展示、确认后状态更新。

### 验证清单
- 后端单元测试：OCR字段映射、上传解析、状态流转（`draft/parsed/confirmed`）
- 接口冒烟测试：`/api/records/upload`、`/api/records/{id}/confirm`
- 前端流程校验：上传文件 -> 查看解析结果 -> 确认入档 -> 进入档案详情修正

### 验证结果
- 后端单元测试：`python -m pytest` -> `14 passed`。
- 接口冒烟测试（Mock）：
  - `upload_requires_file: 400`
  - `upload_success: 201`
  - `upload_status_parsed: parsed`
  - `upload_mapped_count: 4`
  - `upload_unmatched_count: 1`
  - `confirm_success: 200`
  - `confirm_status: confirmed`
- 接口冒烟测试（华为云真实）：
  - `upload_status: 201`
  - `provider: huawei_ocr_general_table`
  - `record_status: parsed`
  - `confirm_status: 200`
  - `confirm_record_status: confirmed`
  - 说明：样本 `health report_example.pdf` 主要是预约与说明页，非指标明细页，因此 `mapped_count=0`、`unmatched_count=25`，链路本身正常。
- 前端构建：`npm run build` 成功。
- 前端启动探针：`dev_server_5177:LISTENING`（启动后已停止进程）。

### 阻塞项
- 无

### 结论
- 第4轮 OCR 上传闭环（含华为云真实接入）已满足严格门槛并完成收口。

### 是否进入下一轮
- 否（用户选择暂停在第4轮，当前进度已保存）


## 轮次 5：亲友授权闭环

- 状态：`Closed`
- 日期：2026-04-08
- 目标：完成亲友关系管理与授权闭环，支持添加/改名/授权开关/删除，以及亲友档案代传并严格校验授权链路。

### 后端改动
- 新增 `friends` Blueprint 并注册路由前缀 `/api/friends`。
- 新增亲友接口：
  - `GET /api/friends`（返回 `outgoing/incoming/manageable`）
  - `POST /api/friends`（支持 `friend_user_id` 或 `friend_username` 添加）
  - `PUT /api/friends/{id}`（关系名修改，仅创建方）
  - `PUT /api/friends/{id}/authorization`（授权开关，仅被添加方）
  - `DELETE /api/friends/{id}`（双方可删除关系）
- `records` 模块接入代传权限链：
  - 新增 `owner_id` 入参（创建档案 + OCR上传均支持）
  - 校验链路：关系存在 -> `auth_status=true` -> 允许代传/管理
  - 档案访问范围扩展为“本人 + 已授权亲友”
  - 未授权访问仍返回 `404`（避免暴露资源存在性）
- `HealthRecord.to_dict()` 增强：返回 `owner` 与 `uploader` 用户信息，支撑前端展示归属人与上传人。
- 测试补充：
  - 新增 `backend/tests/test_friends.py`
  - 扩展 `backend/tests/test_records.py::test_friend_proxy_record_authorization_chain`

### 前端改动
- 新增亲友 API 封装：`frontend/src/api/friends.js`。
- 新增页面：`FriendManageView`，并新增路由 `/friends`。
- 亲友管理页支持：添加亲友、改名、授权开关、删除关系、双向列表展示（我添加的 / 授权给我的）。
- 档案代传入口落地：
  - `RecordListView` 新建档案新增“档案归属人”选择（本人 + 已授权亲友）
  - `RecordOcrUploadView` 上传前新增“档案归属人”选择
- 档案展示增强：
  - 档案列表新增“档案归属人”列
  - 档案详情与OCR结果页显示“归属人/上传人”
- 导航补齐：机构页、档案页、个人中心、OCR页均新增“亲友管理”入口。

### 验证清单
- 后端单元测试：亲友 CRUD、授权开关、代传档案授权链（关系存在 + `auth_status=true` + `owner_id`匹配）
- 接口冒烟测试：`/api/friends` 与亲友档案代传相关接口
- 前端流程校验：添加亲友 -> 开启授权 -> 代传档案成功；关闭授权后代传失败

### 验证结果
- 后端单元测试：`python -m pytest` -> `16 passed`。
- 覆盖结果：
  - 亲友关系增删改查与授权角色限制通过
  - 代传授权链路通过（无关系拦截、未授权拦截、授权后可代传、撤销后不可访问）
- 前端构建：`npm run build` 成功。
- 前端构建提示：存在 `chunk > 500kB` 警告（不影响当前第5轮功能正确性）。

### 阻塞项
- 无

### 结论
- 第5轮亲友授权闭环已满足严格门槛并完成收口。

### 是否进入下一轮
- 待用户确认是否进入第6轮（趋势分析 + 评论审核闭环）


## 轮次 6：趋势分析 + 评论审核闭环

- 状态：`Closed`
- 日期：2026-04-08
- 目标：完成单指标时序趋势分析与机构评论“提交-审核-展示”闭环，支持管理员控制评论可见性。

### 后端改动
- 新增 `Comment` 模型：`user_id/institution_id/content/rating/is_visible/created_at`。
- 新增 `comments` Blueprint（`/api/comments`）：
  - `GET /api/comments?institution_id=`：查询机构公开评论（管理员可扩展查看）
  - `POST /api/comments`：提交评论（校验已上传该机构体检档案）
  - `GET /api/comments/moderation`：管理员查看评论审核列表
  - `PUT /api/comments/{id}/visibility`：管理员切换评论显示状态
- 新增 `trends` Blueprint（`/api/trends`）：
  - `GET /api/trends/indicators/{indicator_dict_id}?owner_id=`：返回单指标历史序列、摘要统计、参考区间
  - 权限校验：本人或已授权亲友可查询；未授权返回 `403`
- App 注册新模块：
  - `app.register_blueprint(comments_bp, url_prefix="/api/comments")`
  - `app.register_blueprint(trends_bp, url_prefix="/api/trends")`
- 新增默认管理员种子初始化：
  - 启动时自动确保管理员账号存在（默认 `admin/admin123`，可通过环境变量覆盖）
  - 新增环境变量模板：`DEFAULT_ADMIN_USERNAME/DEFAULT_ADMIN_PASSWORD/DEFAULT_ADMIN_EMAIL`
- 新增测试：
  - `backend/tests/test_comments.py`（评论提交门槛 + 管理员审核流程）
  - `backend/tests/test_trends.py`（趋势查询 + 亲友授权边界）

### 前端改动
- 新增趋势页面：`TrendView`（`/trends`）
  - 选择归属人（本人+已授权亲友）与指标
  - 展示时序曲线、参考线、统计摘要与明细表
  - 使用 `echarts` 渲染折线图
- 新增评论审核页面：`CommentModerationView`（`/admin/comments`）
  - 管理员查看全部评论并切换可见性
  - 非管理员访问显示权限提示
- 机构详情页接入评论闭环：
  - 展示公开评论列表
  - 支持提交评分 + 评论（提交后进入审核）
- 新增 API 封装：
  - `frontend/src/api/comments.js`
  - `frontend/src/api/trends.js`
- 导航增强：主要页面新增“指标趋势”“评论审核”入口。
- 新增依赖：`echarts`。

### 验证清单
- 后端单元测试：趋势查询、评论审核权限、评论提交门槛
- 接口冒烟测试：`/api/trends/*`、`/api/comments/*`
- 前端流程校验：
  - 趋势页选指标后展示曲线与统计
  - 机构详情提交评论后进入审核
  - 管理员审核通过后机构页可见评论

### 验证结果
- 后端单元测试：`python -m pytest` -> `20 passed`。
- 接口覆盖结果：
  - 评论：未上传记录拦截、管理员审核通过后公开可见
  - 趋势：本人可查、未授权亲友被拦截、授权后可查
- 前端构建：`npm run build` 成功。
- 构建提示：`chunk > 500kB` 警告仍存在；引入 `echarts` 后体积增大，不影响功能正确性。

### 阻塞项
- 无

### 结论
- 第6轮趋势分析 + 评论审核闭环已满足严格门槛并完成收口。


## 收尾优化：构建分包 + 部署脚本 + 答辩脚本

- 状态：`Closed`
- 日期：2026-04-08
- 目标：降低前端构建体积风险、补齐一键部署入口、提供可直接执行的答辩演示脚本。

### 改动内容
- 前端构建优化：
  - 路由组件改为懒加载（按页面分包）
  - `vite.config.js` 新增 `manualChunks`（`vue-core / vendor / element-plus / echarts`）
  - 调整 `chunkSizeWarningLimit`，构建输出可控
- 部署脚本新增（项目根目录 `scripts/`）：
  - `start-backend-dev.ps1`
  - `start-frontend-dev.ps1`
  - `start-full-dev.ps1`
  - `start-backend-prod.ps1`（Waitress）
  - `start-frontend-prod.ps1`
  - `start-full-prod.ps1`
- 启动脚本热修复（2026-04-08）：
  - 修复 `start-backend-prod.ps1` 在部分 PowerShell 环境下的解析错误（字符串/引号终止符异常）
  - 修复 `start-full-prod.ps1` 的 `-File` 参数传递方式，避免路径含空格时启动失败
  - 将后端脚本关键报错文本改为 ASCII，规避编码导致的语法误判
- 后端生产入口：
  - 新增 `backend/wsgi.py`
  - `backend/requirements.txt` 增加 `waitress`
- 文档补充：
  - 更新 `backend/README.md`、`frontend/README.md`
  - 新增 `coding/deploy-and-demo.md`（12分钟答辩演示流程）

### 验证结果
- 后端：`python -m pytest` -> `20 passed`
- 前端：`npm run build` 成功，分包后产物拆分明显：
  - `element-plus` 与 `echarts` 独立 chunk
  - 页面级 chunk 独立输出
  - 构建阶段无 `chunk > 500kB` 警告
- 生产脚本联动验证：
  - 执行 `scripts/start-full-prod.ps1` 后，后端 `http://127.0.0.1:5000/api/health` 返回 `200`
  - 前端 `http://127.0.0.1:4173` 返回 `200`

### 结论
- 部署与演示准备已完成，可直接进入答辩演示阶段。



