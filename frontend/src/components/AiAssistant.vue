<template>
  <button
    v-if="!aiStore.isOpen"
    ref="ballButton"
    class="ai-floating-ball"
    :style="ballStyle"
    type="button"
    aria-label="打开 AI 智能助手"
    title="AI 智能助手（可拖动）"
    @pointerdown="startBallDrag"
    @click="handleBallClick"
    @keydown.enter.prevent="openAssistant"
    @keydown.space.prevent="openAssistant"
  >
    <span>AI</span>
  </button>

  <transition name="ai-panel-slide">
    <aside
      v-if="aiStore.isOpen"
      id="ai-chat-panel"
      ref="chatPanel"
      class="ai-chat-panel"
      tabindex="-1"
      :role="compactViewport ? 'dialog' : 'complementary'"
      :aria-modal="compactViewport ? 'true' : undefined"
      aria-labelledby="ai-chat-title"
      @keydown.tab="trapPanelFocus"
      @keydown.esc="handlePanelEscape"
    >
      <div
        class="ai-resize-handle"
        role="separator"
        tabindex="0"
        aria-label="调整 AI 对话栏宽度；左方向键增大，右方向键缩小"
        aria-controls="ai-chat-panel"
        aria-orientation="vertical"
        :aria-valuemin="PANEL_MIN_WIDTH"
        :aria-valuemax="panelMaxWidth"
        :aria-valuenow="panelWidthNow"
        :aria-valuetext="`${panelWidthNow} 像素`"
        title="拖动调整宽度；也可使用左右方向键"
        @pointerdown="startResize"
        @keydown="resizeWithKeyboard"
      />

      <header class="ai-chat-header">
        <div>
          <h2 id="ai-chat-title" class="ai-chat-title">AI 智能助手</h2>
          <div class="ai-chat-subtitle">
            {{ authenticated ? "健康科普与系统帮助" : "访客系统导览" }}
          </div>
        </div>
        <div class="ai-header-actions">
          <el-button size="small" plain @click="confirmEndConversation">结束对话</el-button>
          <el-button size="small" circle aria-label="收起对话栏" @click="closeAssistant">×</el-button>
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

      <section
        ref="messageArea"
        class="ai-message-area"
        role="log"
        tabindex="0"
        aria-label="AI 对话消息"
        aria-live="polite"
        aria-relevant="additions text"
        :aria-busy="aiStore.isSending"
      >
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
              @click="selectSuggestion(question)"
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

        <div
          v-if="aiStore.pendingMessage"
          class="ai-message-row user pending"
          aria-hidden="true"
        >
          <div class="ai-message-bubble">
            <div class="ai-message-content">{{ aiStore.pendingMessage }}</div>
          </div>
        </div>

        <div v-if="aiStore.isSending" class="ai-message-row assistant" aria-hidden="true">
          <div class="ai-message-bubble ai-thinking">
            <span />
            <span />
            <span />
          </div>
        </div>
      </section>

      <footer class="ai-composer">
        <span class="ai-sr-only" role="status" aria-live="polite" aria-atomic="true">
          {{ sendingAnnouncement }}
        </span>
        <el-alert
          v-if="errorMessage"
          class="ai-error-alert"
          :title="errorMessage"
          type="error"
          role="alert"
          show-icon
          closable
          @close="errorMessage = ''"
        />
        <el-input
          ref="composerInput"
          v-model="inputMessage"
          type="textarea"
          aria-label="发送给 AI 助手的消息"
          aria-describedby="ai-chat-disclaimer"
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
        <p id="ai-chat-disclaimer" class="ai-disclaimer">
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
const BALL_TOP_SAFE_AREA = 80;
const PANEL_MIN_WIDTH = 360;
const PANEL_MAX_WIDTH = 760;
const PANEL_COMPACT_BREAKPOINT = 860;
const PANEL_KEYBOARD_STEP = 24;
const PANEL_FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "textarea:not([disabled])",
  "input:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

let suppressBallClick = false;

const aiStore = useAiChatStore();
const authStore = useAuthStore();
const route = useRoute();

const inputMessage = ref("");
const errorMessage = ref("");
const ballButton = ref(null);
const chatPanel = ref(null);
const composerInput = ref(null);
const messageArea = ref(null);
const recordsLoading = ref(false);
const recordsError = ref("");
const availableRecords = ref([]);
const ballPosition = ref({ x: 0, y: 0 });
const viewportWidth = ref(window.innerWidth);

const authenticated = computed(() => Boolean(authStore.accessToken && authStore.user));
const compactViewport = computed(() => viewportWidth.value <= PANEL_COMPACT_BREAKPOINT);
const panelMaxWidth = computed(() =>
  Math.max(
    PANEL_MIN_WIDTH,
    Math.round(Math.min(PANEL_MAX_WIDTH, viewportWidth.value * 0.55))
  )
);
const panelWidthNow = computed(() =>
  Math.round(
    Math.min(Math.max(PANEL_MIN_WIDTH, aiStore.panelWidth), panelMaxWidth.value)
  )
);
const sendingAnnouncement = computed(() =>
  aiStore.isSending ? "消息正在发送，正在等待 AI 回复。" : ""
);

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

async function focusComposer() {
  await nextTick();
  if (composerInput.value?.focus) {
    composerInput.value.focus();
  } else {
    chatPanel.value?.focus({ preventScroll: true });
  }
}

function openAssistant() {
  aiStore.setOpen(true);
}

function closeAssistant() {
  aiStore.setOpen(false);
}

function handleBallClick(event) {
  if (suppressBallClick) {
    event.preventDefault();
    return;
  }
  openAssistant();
}

function trapPanelFocus(event) {
  if (!compactViewport.value || !chatPanel.value) {
    return;
  }

  const focusableElements = [...chatPanel.value.querySelectorAll(PANEL_FOCUSABLE_SELECTOR)]
    .filter(
      (element) =>
        element.getAttribute("aria-hidden") !== "true" &&
        !element.closest("[hidden]") &&
        !element.classList.contains("ai-resize-handle")
    );
  if (focusableElements.length === 0) {
    event.preventDefault();
    chatPanel.value.focus({ preventScroll: true });
    return;
  }

  const firstElement = focusableElements[0];
  const lastElement = focusableElements.at(-1);
  if (!focusableElements.includes(document.activeElement)) {
    event.preventDefault();
    (event.shiftKey ? lastElement : firstElement).focus();
  } else if (event.shiftKey && document.activeElement === firstElement) {
    event.preventDefault();
    lastElement.focus();
  } else if (!event.shiftKey && document.activeElement === lastElement) {
    event.preventDefault();
    firstElement.focus();
  }
}

function handlePanelEscape(event) {
  if (event.defaultPrevented) return;
  event.preventDefault();
  closeAssistant();
}

async function selectSuggestion(question) {
  inputMessage.value = question;
  await focusComposer();
}

function clampBall(position) {
  const maxY = Math.max(BALL_MARGIN, window.innerHeight - BALL_SIZE - BALL_MARGIN);
  const minY = Math.min(BALL_TOP_SAFE_AREA, maxY);
  return {
    x: Math.min(
      Math.max(BALL_MARGIN, position.x),
      Math.max(BALL_MARGIN, window.innerWidth - BALL_SIZE - BALL_MARGIN)
    ),
    y: Math.min(
      Math.max(minY, position.y),
      maxY
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
    } else {
      suppressBallClick = true;
      window.setTimeout(() => {
        suppressBallClick = false;
      }, 0);
    }
  };

  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", finish);
  window.addEventListener("pointercancel", finish);
}

function startResize(event) {
  if (event.button !== 0 || compactViewport.value) {
    return;
  }
  event.preventDefault();
  event.currentTarget?.focus({ preventScroll: true });
  const move = (moveEvent) => {
    const width = Math.min(
      Math.max(PANEL_MIN_WIDTH, window.innerWidth - moveEvent.clientX),
      panelMaxWidth.value
    );
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

function resizeWithKeyboard(event) {
  if (compactViewport.value) {
    return;
  }

  let width = panelWidthNow.value;
  const step = event.shiftKey ? PANEL_KEYBOARD_STEP * 2 : PANEL_KEYBOARD_STEP;
  if (event.key === "ArrowLeft") {
    width += step;
  } else if (event.key === "ArrowRight") {
    width -= step;
  } else if (event.key === "Home") {
    width = PANEL_MIN_WIDTH;
  } else if (event.key === "End") {
    width = panelMaxWidth.value;
  } else {
    return;
  }

  event.preventDefault();
  aiStore.setPanelWidth(
    Math.min(Math.max(PANEL_MIN_WIDTH, width), panelMaxWidth.value)
  );
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
  viewportWidth.value = window.innerWidth;
  ballPosition.value = clampBall(ballPosition.value);
  aiStore.setBallPosition(ballPosition.value);
  if (!compactViewport.value) {
    aiStore.setPanelWidth(
      Math.min(Math.max(PANEL_MIN_WIDTH, aiStore.panelWidth), panelMaxWidth.value)
    );
  }
}

watch(
  () => aiStore.isOpen,
  async (isOpen) => {
    if (isOpen) {
      loadAvailableRecords();
      scrollToBottom();
      await focusComposer();
    } else {
      await nextTick();
      ballButton.value?.focus({ preventScroll: true });
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
    focusComposer();
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
  border: 1px solid var(--color-accent, #0b7a6b);
  border-radius: 50%;
  color: var(--color-accent-strong, #075e54);
  background: var(--color-accent-soft, #e5f3f0);
  box-shadow: var(--shadow-md, 0 12px 32px rgb(29 29 31 / 16%));
  cursor: grab;
  touch-action: none;
  user-select: none;
}

.ai-floating-ball:focus-visible,
.ai-resize-handle:focus-visible,
.ai-message-area:focus-visible,
.ai-suggestions button:focus-visible {
  outline: 3px solid var(--color-focus, #1677ff);
  outline-offset: 3px;
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
  border: 1px solid var(--color-accent, #0b7a6b);
  border-radius: 50%;
  font-size: var(--text-lg, 1.125rem);
  font-weight: 800;
  letter-spacing: 0.03em;
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
  height: 100dvh;
  border-left: 1px solid var(--color-border, #d2d2d7);
  color: var(--color-text, #1d1d1f);
  background: var(--color-canvas, #f5f5f7);
  box-shadow: var(--shadow-md, -12px 0 36px rgb(29 29 31 / 16%));
  outline: none;
  overscroll-behavior: contain;
}

.ai-resize-handle {
  position: absolute;
  z-index: 2;
  top: 0;
  bottom: 0;
  left: -5px;
  width: 10px;
  cursor: ew-resize;
  touch-action: none;
}

.ai-resize-handle::after {
  position: absolute;
  top: 50%;
  left: 4px;
  width: 2px;
  height: 54px;
  border-radius: var(--radius-sm, 0.5rem);
  background: var(--color-text-secondary, #5f6368);
  content: "";
  transform: translateY(-50%);
}

.ai-resize-handle:hover::after,
.ai-resize-handle:focus-visible::after {
  width: 3px;
  background: var(--color-accent, #0b7a6b);
}

.ai-chat-header {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 72px;
  padding: max(14px, env(safe-area-inset-top)) max(16px, env(safe-area-inset-right)) 14px max(16px, env(safe-area-inset-left));
  border-bottom: 1px solid var(--color-border, #d2d2d7);
  background: var(--color-surface-elevated, #ffffff);
}

.ai-chat-header > div:first-child {
  min-width: 0;
}

.ai-chat-title {
  margin: 0;
  color: var(--color-text, #1d1d1f);
  font-size: var(--text-lg, 1.125rem);
  font-weight: 750;
  line-height: 1.3;
  overflow-wrap: anywhere;
}

.ai-chat-subtitle {
  margin-top: 3px;
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.ai-header-actions {
  display: flex;
  align-items: center;
  flex: 0 0 auto;
  gap: 6px;
}

.ai-header-actions :deep(.el-button) {
  min-height: var(--control-min-height, 36px);
  color: var(--color-text, #1d1d1f);
  border-color: var(--color-border, #d2d2d7);
  background: var(--color-surface, #ffffff);
  font-size: var(--text-sm, 0.875rem);
}

.ai-header-actions :deep(.el-button:hover),
.ai-header-actions :deep(.el-button:focus-visible) {
  color: var(--color-accent-strong, #075e54);
  border-color: var(--color-accent, #0b7a6b);
  background: var(--color-accent-soft, #e5f3f0);
}

.ai-record-context {
  flex: 0 0 auto;
  padding: 12px max(14px, env(safe-area-inset-right)) 10px max(14px, env(safe-area-inset-left));
  border-bottom: 1px solid var(--color-border, #d2d2d7);
  background: var(--color-surface, #ffffff);
}

.ai-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--color-text, #1d1d1f);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
  line-height: 1.4;
}

.ai-selection-count {
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-xs, 0.75rem);
  font-weight: 500;
}

.ai-record-context :deep(.el-select__wrapper) {
  color: var(--color-text, #1d1d1f);
  background: var(--color-surface-muted, #f5f5f7);
  box-shadow: 0 0 0 1px var(--color-border, #d2d2d7) inset;
  font-size: var(--text-sm, 0.875rem);
}

.ai-record-context :deep(.el-select__placeholder),
.ai-record-context :deep(.el-select__input),
.ai-record-context :deep(.el-tag) {
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-sm, 0.875rem);
}

.ai-record-context :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 2px var(--color-focus, #1677ff) inset;
}

.ai-context-tip,
.ai-context-error {
  margin: 7px 0 0;
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.ai-context-tip {
  color: var(--color-text-secondary, #5f6368);
}

.ai-context-error {
  color: var(--color-danger, #c9342f);
}

.ai-consent {
  height: auto;
  margin-top: 8px;
  white-space: normal;
}

.ai-consent :deep(.el-checkbox__label) {
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
  overflow-wrap: anywhere;
  white-space: normal;
}

.ai-message-area {
  flex: 1 1 auto;
  min-height: 0;
  padding: 16px max(14px, env(safe-area-inset-right)) 20px max(14px, env(safe-area-inset-left));
  overflow-y: auto;
  color: var(--color-text, #1d1d1f);
  background: var(--color-canvas, #f5f5f7);
  scrollbar-color: var(--color-border, #d2d2d7) var(--color-canvas, #f5f5f7);
  scroll-behavior: smooth;
}

.ai-welcome-card {
  padding: 22px 18px;
  border: 1px solid var(--color-border, #d2d2d7);
  border-radius: var(--radius-lg, 1rem);
  background: var(--color-surface-elevated, #ffffff);
  box-shadow: var(--shadow-sm, 0 2px 10px rgb(29 29 31 / 8%));
  text-align: center;
}

.ai-welcome-icon {
  display: grid;
  place-items: center;
  width: 54px;
  height: 54px;
  margin: 0 auto 12px;
  border: 1px solid var(--color-accent, #0b7a6b);
  border-radius: var(--radius-md, 0.75rem);
  color: var(--color-accent-strong, #075e54);
  background: var(--color-accent-soft, #e5f3f0);
  font-size: var(--text-base, 1rem);
  font-weight: 800;
}

.ai-welcome-card h2 {
  margin: 0 0 8px;
  color: var(--color-text, #1d1d1f);
  font-size: var(--text-lg, 1.125rem);
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.ai-welcome-card p {
  margin: 0;
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.6;
  overflow-wrap: anywhere;
}

.ai-suggestions {
  display: grid;
  gap: 8px;
  margin-top: 16px;
}

.ai-suggestions button {
  min-height: var(--control-min-height, 36px);
  padding: 9px 12px;
  border: 1px solid var(--color-border, #d2d2d7);
  border-radius: var(--radius-sm, 0.5rem);
  color: var(--color-accent-strong, #075e54);
  background: var(--color-accent-soft, #e5f3f0);
  cursor: pointer;
  font: inherit;
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.45;
  text-align: left;
  overflow-wrap: anywhere;
}

.ai-suggestions button:hover {
  border-color: var(--color-accent, #0b7a6b);
  background: var(--color-surface-muted, #f5f5f7);
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
  border-radius: var(--radius-md, 0.75rem);
  color: var(--color-text, #1d1d1f);
  background: var(--color-surface-elevated, #ffffff);
  box-shadow: var(--shadow-sm, 0 2px 8px rgb(29 29 31 / 8%));
}

.ai-message-row.user .ai-message-bubble {
  border: 1px solid var(--color-accent, #0b7a6b);
  color: var(--color-accent-strong, #075e54);
  background: var(--color-accent-soft, #e5f3f0);
  border-bottom-right-radius: var(--radius-sm, 0.5rem);
}

.ai-message-row.assistant .ai-message-bubble {
  border: 1px solid var(--color-border, #d2d2d7);
  border-bottom-left-radius: var(--radius-sm, 0.5rem);
}

.ai-message-row.pending .ai-message-bubble {
  opacity: 0.68;
}

.ai-message-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 5px;
  color: var(--color-accent-strong, #075e54);
  font-size: var(--text-xs, 0.75rem);
  font-weight: 700;
  line-height: 1.4;
}

.ai-message-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  font-size: var(--text-base, 1rem);
  line-height: 1.65;
}

.ai-phone-link {
  display: inline-block;
  margin-top: 8px;
  color: var(--color-accent-strong, #075e54);
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
  text-decoration: underline;
  text-underline-offset: 0.18em;
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
  background: var(--color-accent, #0b7a6b);
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
  padding: 12px max(14px, env(safe-area-inset-right)) max(10px, env(safe-area-inset-bottom)) max(14px, env(safe-area-inset-left));
  border-top: 1px solid var(--color-border, #d2d2d7);
  background: var(--color-surface, #ffffff);
}

.ai-error-alert {
  margin-bottom: 8px;
}

.ai-composer :deep(.el-textarea__inner) {
  color: var(--color-text, #1d1d1f);
  background: var(--color-surface-muted, #f5f5f7);
  box-shadow: 0 0 0 1px var(--color-border, #d2d2d7) inset;
  font-size: var(--text-base, 1rem);
  line-height: 1.55;
}

.ai-composer :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 2px var(--color-focus, #1677ff) inset;
}

.ai-composer :deep(.el-input__count) {
  color: var(--color-text-secondary, #5f6368);
  background: transparent;
  font-size: var(--text-xs, 0.75rem);
}

.ai-composer-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-top: 8px;
}

.ai-composer-actions span {
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.4;
}

.ai-composer-actions :deep(.el-button) {
  min-height: var(--control-min-height, 36px);
  font-size: var(--text-sm, 0.875rem);
}

.ai-disclaimer {
  margin: 7px 0 0;
  color: var(--color-text-secondary, #5f6368);
  font-size: var(--text-xs, 0.75rem);
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.ai-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
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

:global(html[data-care="on"] .ai-chat-header) {
  align-items: flex-start;
  flex-wrap: wrap;
  min-height: 84px;
}

:global(html[data-care="on"] .ai-header-actions) {
  flex-wrap: wrap;
  margin-left: auto;
}

:global(html[data-care="on"] .ai-header-actions .el-button),
:global(html[data-care="on"] .ai-composer-actions .el-button),
:global(html[data-care="on"] .ai-suggestions button) {
  min-height: 44px;
}

:global(html[data-care="on"] .ai-record-context .el-select__wrapper) {
  min-height: 44px;
  height: auto;
}

:global(html[data-care="on"] .ai-record-context .el-select__selection),
:global(html[data-care="on"] .ai-record-context .el-select__selected-item),
:global(html[data-care="on"] .ai-record-context .el-tag),
:global(html[data-care="on"] .ai-record-context .el-tag__content) {
  flex-wrap: wrap;
  max-width: 100%;
  height: auto;
  overflow: visible;
  white-space: normal;
  text-overflow: clip;
  overflow-wrap: anywhere;
}

:global(html[data-care="on"] .ai-consent .el-checkbox__input) {
  align-self: flex-start;
  margin-top: 0.2em;
}

:global(html[data-care="on"] .ai-message-bubble) {
  max-width: 96%;
}

:global(html[data-care="on"] .ai-message-label),
:global(html[data-care="on"] .ai-composer-actions) {
  flex-wrap: wrap;
}

:global(html[data-care="on"] .ai-composer .el-textarea__inner) {
  min-height: 120px !important;
}

@media (max-width: 860px) {
  .ai-chat-panel {
    inset: 0;
    width: 100%;
    max-width: 100vw;
    border-left: 0;
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

  .ai-composer-actions {
    flex-wrap: wrap;
  }
}

@media (max-width: 860px), (max-height: 600px) {
  .ai-chat-panel {
    overflow-y: auto;
  }

  .ai-message-area {
    flex: 1 0 clamp(8rem, 30dvh, 16rem);
  }
}

@media (max-width: 380px) {
  .ai-chat-header {
    align-items: flex-start;
    flex-wrap: wrap;
  }

  .ai-header-actions {
    margin-left: auto;
  }

  .ai-welcome-card {
    padding: 18px 14px;
  }

  .ai-message-bubble,
  :global(html[data-care="on"] .ai-message-bubble) {
    max-width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ai-floating-ball,
  .ai-panel-slide-enter-active,
  .ai-panel-slide-leave-active {
    transition: none;
  }

  .ai-floating-ball:active {
    transform: none;
  }

  .ai-message-area {
    scroll-behavior: auto;
  }

  .ai-thinking span {
    animation: none;
  }
}
</style>
