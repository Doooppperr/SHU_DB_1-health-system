# Health System Frontend

Vue 3 + Vite 前端，使用 Vue Router、Pinia、Element Plus、Axios 和 ECharts。除健康档案、OCR、趋势和评论页面外，应用根组件还挂载了全局 AI 智能助手。

## 安装

```bash
npm install
```

## 启动

```bash
npm run dev
```

## 构建与预览

```bash
npm run build
npm run preview
```

项目根目录也提供脚本：

```powershell
.\scripts\start-frontend-dev.ps1
.\scripts\start-frontend-prod.ps1
```

开发服务器默认访问 `http://127.0.0.1:5173`，并把 `/api` 与 `/uploads` 代理到 Flask 后端 `http://127.0.0.1:5050`。

## AI 智能助手界面

- `src/components/AiAssistant.vue`：可拖动悬浮球、可调宽右侧栏、消息列表、档案多选和隐私确认。
- `src/stores/aiChat.js`：会话、摘要、最近 10 轮、选择档案、侧栏宽度和发送状态。
- `src/api/ai.js`：调用 `POST /api/ai/chat`，超时单独设置为 75 秒。
- `src/utils/aiSession.js`：统一清理浏览器会话。

行为约定：

- 登录前也显示悬浮球，仅提供公开系统功能导览。
- 登录后可选择同一人的最多 5 份已确认档案；选择档案后必须确认指标将发送至 DeepSeek API。
- 对话正文和摘要写入 `sessionStorage`，因此刷新页面仍可恢复；关闭标签页、结束对话或退出登录后不再保留。
- 悬浮球位置和侧栏宽度属于界面偏好，保存在 `localStorage`，不包含聊天内容或健康指标。
- 登录、注册成功会清除匿名对话；退出登录会清除当前身份的 AI 会话，避免不同身份混用上下文。
- 桌面端打开侧栏后主页面缩小，移动端侧栏覆盖全屏。

DeepSeek API Key 只由后端环境变量读取，前端代码和浏览器存储中都不应出现密钥。

## 构建验证

```powershell
npm run build
```

当前生产构建通过；浏览器已验证匿名 FAQ、刷新恢复、侧栏开合及宽度拖动，控制台无错误。
