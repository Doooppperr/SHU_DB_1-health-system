<template>
  <button
    v-if="!aiStore.isOpen"
    class="ai-floating-ball"
    :style="ballStyle"
    type="button"
    aria-label="打开 AI 智能助手"
    title="AI 智能助手（可拖动）"
    @pointerdown="startBallDrag"
    @keydown.enter.prevent="aiStore.setOpen(true)"
  >
    <span>AI</span>
  </button>

  <transition name="ai-panel-slide">
    <aside v-if="aiStore.isOpen" class="ai-chat-panel" aria-label="AI 智能助手对话栏">
      <div class="ai-resize-handle" title="拖动调整宽度" @pointerdown="startResize" />

      <header class="ai-chat-header">
        <div>
          <div class="ai-chat-title">AI 智能助手</div>
          <div class="ai-chat-subtitle">
            {{ authenticated ? "健康科普与系统帮助" : "访客系统导览" }}
          </div>
        </div>
        <div class="ai-header-actions">
          <el-button size="small" plain @click="confirmEndConversation">结束对话</el-button>
          <el-button size="small" circle aria-label="收起对话栏" @click="aiStore.setOpen(false)">×</el-button>
        </div>
      </header>

      <section v-if="authenticated" class="ai-record-context">
        <div class="ai-section-heading">
          <span>本次参考档案</span>
          <span class="ai-selection-count">{{ aiStore.selectedRecordIds.length }}/5</span>
        </div>

        <el-select
          :model-value="aiStore.selectedRecordIds"
          multiple
          collapse-tags
          :max-collapse-tags="2"
          clearable
          filterable
          placeholder="可选择同一人的最多 5 份已确认档案"
          style="width: 100%"
          :loading="recordsLoading"
          @change="changeRecordSelection"
        >
          <el-option-group
            v-for="group in recordGroups"
            :key="group.ownerId"
            :label="group.label"
          >
            <el-option
              v-for="record in group.records"
              :key="record.id"
              :label="recordOptionLabel(record)"
              :value="record.id"
              :disabled="isRecordDisabled(record)"
            />
          </el-option-group>
        </el-select>

        <p v-if="recordsError" class="ai-context-error">{{ recordsError }}</p>
        <p v-else-if="!recordsLoading && availableRecords.length === 0" class="ai-context-tip">
          暂无带指标的已确认档案，仍可咨询一般健康和系统问题。
        </p>

        <el-checkbox
          v-if="aiStore.selectedRecordIds.length"
          :model-value="aiStore.consentGiven"
          class="ai-consent"
          @change="aiStore.setConsentGiven"
        >
          我知晓所选指标将发送至 DeepSeek API 处理
        </el-checkbox>
      </section>

      <section ref="messageArea" class="ai-message-area">
        <div v-if="aiStore.messages.length === 0" class="ai-welcome-card">
          <div class="ai-welcome-icon">AI</div>
          <h2>{{ authenticated ? "你好，我是健康科普助手" : "你好，我可以介绍本系统" }}</h2>
          <p v-if="authenticated">
            我可以解释指标含义和一般生活建议，但不能诊断疾病、推荐处方药或替代医生。
          </p>
          <p v-else>
            登录前可以询问注册、登录、OCR 上传和其他公开功能。个人指标分析需要先登录。
          </p>

          <div class="ai-suggestions">
            <button
              v-for="question in suggestions"
              :key="question"
              type="button"
              @click="inputMessage = question"
            >
              {{ question }}
            </button>
          </div>
        </div>

        <div
          v-for="(message, index) in aiStore.messages"
          :key="`${index}-${message.role}`"
          class="ai-message-row"
          :class="message.role"
        >
          <div class="ai-message-bubble">
            <div v-if="message.role === 'assistant'" class="ai-message-label">
              AI 助手
              <el-tag v-if="message.decision === 'support'" size="small" type="warning">转人工</el-tag>
              <el-tag v-else-if="message.decision === 'emergency'" size="small" type="danger">紧急提醒</el-tag>
            </div>
            <div class="ai-message-content">{{ message.content }}</div>
            <a
              v-if="message.supportPhone"
              class="ai-phone-link"
              :href="phoneHref(message.supportPhone)"
            >
              拨打 {{ message.supportPhone }}
            </a>
          </div>
        </div>

        <div v-if="aiStore.pendingMessage" class="ai-message-row user pending">
          <div class="ai-message-bubble">
            <div class="ai-message-content">{{ aiStore.pendingMessage }}</div>
          </div>
        </div>

        <div v-if="aiStore.isSending" class="ai-message-row assistant">
          <div class="ai-message-bubble ai-thinking">
            <span />
            <span />
            <span />
          </div>
        </div>
      </section>

      <footer class="ai-composer">
        <el-alert
          v-if="errorMessage"
          class="ai-error-alert"
          :title="errorMessage"
          type="error"
          show-icon
          closable
          @close="errorMessage = ''"
        />
        <el-input
          v-model="inputMessage"
          type="textarea"
          :rows="3"
          resize="none"
          maxlength="2000"
          show-word-limit
          :disabled="aiStore.isSending"
          :placeholder="authenticated ? '询问指标含义、健康常识或系统功能…' : '询问如何注册、登录或使用系统…'"
          @keydown.enter.exact.prevent="submitMessage"
        />
        <div class="ai-composer-actions">
          <span>Enter 发送，Shift + Enter 换行</span>
          <el-button
            type="primary"
            :loading="aiStore.isSending"
            :disabled="!inputMessage.trim()"
            @click="submitMessage"
          >
            发送
          </el-button>
        </div>
        <p class="ai-disclaimer">
          AI 内容仅供健康科普参考。出现急症请拨打 120；请勿输入身份证号等无关敏感信息。
        </p>
      </footer>
    </aside>
  </transition>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRoute } from "vue-router";

import { fetchRecords } from "../api/records";
import { useAiChatStore } from "../stores/aiChat";
import { useAuthStore } from "../stores/auth";

const BALL_SIZE = 60;
const BALL_MARGIN = 14;

const aiStore = useAiChatStore();
const authStore = useAuthStore();
const route = useRoute();

const inputMessage = ref("");
const errorMessage = ref("");
const messageArea = ref(null);
const recordsLoading = ref(false);
const recordsError = ref("");
const availableRecords = ref([]);
const ballPosition = ref({ x: 0, y: 0 });

const authenticated = computed(() => Boolean(authStore.accessToken && authStore.user));

const suggestions = computed(() =>
  authenticated.value
    ? ["这份报告里的异常指标是什么意思？", "如何理解指标参考范围？", "OCR 上传后怎样确认指标？"]
    : ["如何注册账号？", "体检报告怎样上传？", "亲友授权有什么作用？"]
);

const selectedOwnerId = computed(() => {
  const selected = availableRecords.value.find((record) =>
    aiStore.selectedRecordIds.includes(record.id)
  );
  return selected?.owner_id || null;
});

const recordGroups = computed(() => {
  const groups = new Map();
  availableRecords.value.forEach((record) => {
    if (!groups.has(record.owner_id)) {
      const isSelf = record.owner_id === authStore.user?.id;
      groups.set(record.owner_id, {
        ownerId: record.owner_id,
        label: isSelf ? `本人 · ${record.owner?.username || "当前用户"}` : `已授权亲友 · ${record.owner?.username || record.owner_id}`,
        records: [],
      });
    }
    groups.get(record.owner_id).records.push(record);
  });
  return [...groups.values()];
});

const ballStyle = computed(() => ({
  left: `${ballPosition.value.x}px`,
  top: `${ballPosition.value.y}px`,
}));

function clampBall(position) {
  return {
    x: Math.min(
      Math.max(BALL_MARGIN, position.x),
      Math.max(BALL_MARGIN, window.innerWidth - BALL_SIZE - BALL_MARGIN)
    ),
    y: Math.min(
      Math.max(BALL_MARGIN, position.y),
      Math.max(BALL_MARGIN, window.innerHeight - BALL_SIZE - BALL_MARGIN)
    ),
  };
}

function initializeBallPosition() {
  const saved = aiStore.ballPosition;
  const initial =
    saved && Number.isFinite(saved.x) && Number.isFinite(saved.y)
      ? saved
      : {
          x: window.innerWidth - BALL_SIZE - 28,
          y: window.innerHeight - BALL_SIZE - 100,
        };
  ballPosition.value = clampBall(initial);
  aiStore.setBallPosition(ballPosition.value);
}

function startBallDrag(event) {
  if (event.button !== 0) {
    return;
  }
  event.preventDefault();
  const start = { x: event.clientX, y: event.clientY };
  const origin = { ...ballPosition.value };
  let moved = false;

  const move = (moveEvent) => {
    const deltaX = moveEvent.clientX - start.x;
    const deltaY = moveEvent.clientY - start.y;
    if (Math.hypot(deltaX, deltaY) > 5) {
      moved = true;
    }
    ballPosition.value = clampBall({ x: origin.x + deltaX, y: origin.y + deltaY });
  };

  const finish = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", finish);
    window.removeEventListener("pointercancel", finish);
    aiStore.setBallPosition(ballPosition.value);
    if (!moved) {
      aiStore.setOpen(true);
    }
  };

  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", finish);
  window.addEventListener("pointercancel", finish);
}

function startResize(event) {
  if (event.button !== 0 || window.innerWidth <= 860) {
    return;
  }
  event.preventDefault();
  const move = (moveEvent) => {
    const maxWidth = Math.min(760, window.innerWidth * 0.55);
    const width = Math.min(Math.max(360, window.innerWidth - moveEvent.clientX), maxWidth);
    aiStore.setPanelWidth(width);
  };
  const finish = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", finish);
    window.removeEventListener("pointercancel", finish);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", finish);
  window.addEventListener("pointercancel", finish);
}

function recordOptionLabel(record) {
  const institution = record.institution?.name || "未填写机构";
  return `${record.exam_date} · ${institution} · ${record.indicator_count || 0} 项指标`;
}

function isRecordDisabled(record) {
  const alreadySelected = aiStore.selectedRecordIds.includes(record.id);
  if (alreadySelected) {
    return false;
  }
  if (aiStore.selectedRecordIds.length >= 5) {
    return true;
  }
  return selectedOwnerId.value !== null && selectedOwnerId.value !== record.owner_id;
}

function changeRecordSelection(ids) {
  const selectedRecords = ids
    .map((id) => availableRecords.value.find((record) => record.id === id))
    .filter(Boolean);
  const ownerIds = new Set(selectedRecords.map((record) => record.owner_id));
  if (ownerIds.size > 1) {
    ElMessage.warning("一次对话只能选择同一归属人的档案");
    return;
  }
  if (ids.length > 5) {
    ElMessage.warning("一次最多选择 5 份档案");
    return;
  }
  aiStore.setSelectedRecordIds(ids);
}

function applyRouteRecordDefault() {
  if (route.name !== "record-detail" || availableRecords.value.length === 0) {
    return;
  }
  const recordId = Number(route.params.id);
  const current = availableRecords.value.find((record) => record.id === recordId);
  if (!current || aiStore.selectedRecordIds.includes(recordId)) {
    return;
  }
  const sameOwner = aiStore.selectedRecordIds.filter((id) => {
    const record = availableRecords.value.find((item) => item.id === id);
    return record?.owner_id === current.owner_id;
  });
  aiStore.setSelectedRecordIds([recordId, ...sameOwner].slice(0, 5));
}

async function loadAvailableRecords() {
  if (!authenticated.value || recordsLoading.value) {
    return;
  }
  recordsLoading.value = true;
  recordsError.value = "";
  try {
    const { data } = await fetchRecords();
    availableRecords.value = (data.items || []).filter(
      (record) => record.status === "confirmed" && Number(record.indicator_count) > 0
    );
    const validIds = new Set(availableRecords.value.map((record) => record.id));
    const sanitized = aiStore.selectedRecordIds.filter((id) => validIds.has(id));
    if (sanitized.length !== aiStore.selectedRecordIds.length) {
      aiStore.setSelectedRecordIds(sanitized);
    }
    applyRouteRecordDefault();
  } catch (error) {
    recordsError.value = error?.response?.data?.message || "档案列表加载失败";
  } finally {
    recordsLoading.value = false;
  }
}

function phoneHref(phone) {
  return `tel:${String(phone).replace(/[^\d+]/g, "")}`;
}

async function scrollToBottom() {
  await nextTick();
  if (messageArea.value) {
    messageArea.value.scrollTop = messageArea.value.scrollHeight;
  }
}

async function submitMessage() {
  const message = inputMessage.value.trim();
  if (!message || aiStore.isSending) {
    return;
  }
  if (
    authenticated.value &&
    aiStore.selectedRecordIds.length > 0 &&
    !aiStore.consentGiven
  ) {
    ElMessage.warning("请先确认所选指标将发送至 DeepSeek API 处理");
    return;
  }

  errorMessage.value = "";
  try {
    await aiStore.sendMessage(message, authenticated.value);
    inputMessage.value = "";
    await scrollToBottom();
  } catch (error) {
    const status = error?.response?.status;
    if (status === 503) {
      errorMessage.value = "AI 服务尚未配置，请联系管理员设置 DeepSeek API Key。";
    } else if (status === 429) {
      errorMessage.value = "发送过于频繁，请稍后再试。";
    } else {
      errorMessage.value = error?.response?.data?.message || "AI 暂时无法回复，请稍后再试。";
    }
  }
}

async function confirmEndConversation() {
  try {
    await ElMessageBox.confirm(
      "结束后将清空本次对话、摘要和所选档案，且无法恢复。",
      "结束对话",
      {
        type: "warning",
        confirmButtonText: "确认结束",
        cancelButtonText: "继续对话",
      }
    );
    aiStore.clearConversation({ close: true });
    inputMessage.value = "";
    errorMessage.value = "";
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      throw error;
    }
  }
}

function handleViewportResize() {
  ballPosition.value = clampBall(ballPosition.value);
  aiStore.setBallPosition(ballPosition.value);
  if (window.innerWidth > 860) {
    const maxWidth = Math.min(760, window.innerWidth * 0.55);
    aiStore.setPanelWidth(Math.min(Math.max(360, aiStore.panelWidth), maxWidth));
  }
}

watch(
  () => aiStore.isOpen,
  (isOpen) => {
    if (isOpen) {
      loadAvailableRecords();
      scrollToBottom();
    }
  }
);

watch(
  () => authStore.user?.id || null,
  () => {
    availableRecords.value = [];
    recordsError.value = "";
    if (authenticated.value && aiStore.isOpen) {
      loadAvailableRecords();
    }
  }
);

watch(
  () => route.fullPath,
  () => {
    if (authenticated.value && aiStore.isOpen) {
      if (availableRecords.value.length) {
        applyRouteRecordDefault();
      } else {
        loadAvailableRecords();
      }
    }
  }
);

watch(
  () => [aiStore.messages.length, aiStore.pendingMessage, aiStore.isSending],
  scrollToBottom
);

onMounted(() => {
  initializeBallPosition();
  window.addEventListener("resize", handleViewportResize);
  if (aiStore.isOpen) {
    loadAvailableRecords();
    scrollToBottom();
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", handleViewportResize);
});
</script>

<style scoped>
.ai-floating-ball {
  position: fixed;
  z-index: 1850;
  width: 60px;
  height: 60px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  color: #fff;
  background: linear-gradient(145deg, #24b49a, #197bdb);
  box-shadow: 0 10px 28px rgba(23, 106, 157, 0.32);
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.ai-floating-ball:active {
  cursor: grabbing;
  transform: scale(0.97);
}

.ai-floating-ball span {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  margin: 7px;
  border: 1px solid rgba(255, 255, 255, 0.52);
  border-radius: 50%;
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.5px;
}

.ai-chat-panel {
  position: fixed;
  z-index: 1800;
  top: 0;
  right: 0;
  display: flex;
  flex-direction: column;
  width: var(--ai-panel-width);
  height: 100vh;
  border-left: 1px solid #dce5ec;
  background: #f8fbfc;
  box-shadow: -12px 0 36px rgba(29, 57, 74, 0.16);
}

.ai-resize-handle {
  position: absolute;
  z-index: 2;
  top: 0;
  bottom: 0;
  left: -5px;
  width: 10px;
  cursor: ew-resize;
}

.ai-resize-handle::after {
  position: absolute;
  top: 50%;
  left: 4px;
  width: 2px;
  height: 54px;
  border-radius: 4px;
  background: #a9bcc7;
  content: "";
  transform: translateY(-50%);
}

.ai-chat-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 72px;
  padding: 14px 16px;
  color: #fff;
  background: linear-gradient(115deg, #126f87, #168e80);
}

.ai-chat-title {
  font-size: 18px;
  font-weight: 750;
}

.ai-chat-subtitle {
  margin-top: 3px;
  color: rgba(255, 255, 255, 0.8);
  font-size: 12px;
}

.ai-header-actions {
  display: flex;
  gap: 6px;
  align-items: center;
}

.ai-header-actions :deep(.el-button) {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.45);
  background: rgba(255, 255, 255, 0.1);
}

.ai-record-context {
  flex: 0 0 auto;
  padding: 12px 14px 10px;
  border-bottom: 1px solid #e2eaef;
  background: #fff;
}

.ai-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #314955;
  font-size: 13px;
  font-weight: 700;
}

.ai-selection-count {
  color: #66808d;
  font-size: 12px;
  font-weight: 500;
}

.ai-context-tip,
.ai-context-error {
  margin: 7px 0 0;
  font-size: 12px;
  line-height: 1.45;
}

.ai-context-tip {
  color: #6c7e87;
}

.ai-context-error {
  color: #d24b4b;
}

.ai-consent {
  height: auto;
  margin-top: 8px;
  white-space: normal;
}

.ai-consent :deep(.el-checkbox__label) {
  color: #5b6f79;
  font-size: 12px;
  line-height: 1.4;
}

.ai-message-area {
  flex: 1 1 auto;
  min-height: 0;
  padding: 16px 14px 20px;
  overflow-y: auto;
  scroll-behavior: smooth;
}

.ai-welcome-card {
  padding: 22px 18px;
  border: 1px solid #dfe9ed;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  text-align: center;
}

.ai-welcome-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  border-radius: 16px;
  color: #fff;
  background: linear-gradient(145deg, #23ac93, #1c7dcc);
  font-weight: 800;
}

.ai-welcome-card h2 {
  margin: 0 0 8px;
  color: #203944;
  font-size: 17px;
}

.ai-welcome-card p {
  margin: 0;
  color: #667b85;
  font-size: 13px;
  line-height: 1.6;
}

.ai-suggestions {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.ai-suggestions button {
  padding: 9px 12px;
  border: 1px solid #d6e5e8;
  border-radius: 9px;
  color: #28616b;
  background: #f4faf9;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
}

.ai-suggestions button:hover {
  border-color: #71bdb1;
  background: #edf8f5;
}

.ai-message-row {
  display: flex;
  margin-top: 14px;
}

.ai-message-row.user {
  justify-content: flex-end;
}

.ai-message-bubble {
  max-width: 88%;
  padding: 10px 12px;
  border-radius: 13px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(34, 68, 84, 0.08);
}

.ai-message-row.user .ai-message-bubble {
  color: #fff;
  background: linear-gradient(120deg, #258a9a, #1d8c7b);
  border-bottom-right-radius: 4px;
}

.ai-message-row.assistant .ai-message-bubble {
  border: 1px solid #e0e8ec;
  border-bottom-left-radius: 4px;
}

.ai-message-row.pending .ai-message-bubble {
  opacity: 0.68;
}

.ai-message-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
  color: #33717a;
  font-size: 11px;
  font-weight: 700;
}

.ai-message-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: 14px;
  line-height: 1.65;
}

.ai-phone-link {
  display: inline-block;
  margin-top: 8px;
  color: #0c7b75;
  font-size: 13px;
  font-weight: 700;
}

.ai-thinking {
  display: flex;
  gap: 5px;
  padding: 14px 16px;
}

.ai-thinking span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #66a8a1;
  animation: ai-bounce 1.1s infinite ease-in-out;
}

.ai-thinking span:nth-child(2) {
  animation-delay: 0.14s;
}

.ai-thinking span:nth-child(3) {
  animation-delay: 0.28s;
}

.ai-composer {
  flex: 0 0 auto;
  padding: 12px 14px 10px;
  border-top: 1px solid #dfe8ec;
  background: #fff;
}

.ai-error-alert {
  margin-bottom: 8px;
}

.ai-composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
}

.ai-composer-actions span {
  color: #81939b;
  font-size: 11px;
}

.ai-disclaimer {
  margin: 7px 0 0;
  color: #87969d;
  font-size: 10px;
  line-height: 1.4;
}

.ai-panel-slide-enter-active,
.ai-panel-slide-leave-active {
  transition: transform 0.2s ease;
}

.ai-panel-slide-enter-from,
.ai-panel-slide-leave-to {
  transform: translateX(100%);
}

@keyframes ai-bounce {
  0%,
  70%,
  100% {
    transform: translateY(0);
  }
  35% {
    transform: translateY(-5px);
  }
}

@media (max-width: 860px) {
  .ai-chat-panel {
    width: 100vw;
  }

  .ai-resize-handle {
    display: none;
  }

  .ai-chat-header {
    min-height: 66px;
  }

  .ai-message-bubble {
    max-width: 92%;
  }
}
</style>
