import { defineStore } from "pinia";

import { sendAiChat } from "../api/ai";
import { AI_SESSION_PREFIX } from "../utils/aiSession";


const PANEL_WIDTH_KEY = "health-ai-panel-width";
const BALL_POSITION_KEY = "health-ai-ball-position";

function identityKey(userId) {
  return userId ? `user-${userId}` : "guest";
}

function sessionKey(key) {
  return `${AI_SESSION_PREFIX}${key}`;
}

function readJson(storage, key, fallback) {
  try {
    const raw = storage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    storage.removeItem(key);
    return fallback;
  }
}

function normalizeMessages(rawMessages) {
  if (!Array.isArray(rawMessages)) {
    return [];
  }
  const normalized = [];
  for (let index = 0; index + 1 < rawMessages.length; index += 2) {
    const userMessage = rawMessages[index];
    const assistantMessage = rawMessages[index + 1];
    if (
      userMessage?.role !== "user" ||
      assistantMessage?.role !== "assistant" ||
      typeof userMessage.content !== "string" ||
      typeof assistantMessage.content !== "string"
    ) {
      break;
    }
    normalized.push({ role: "user", content: userMessage.content });
    normalized.push({
      role: "assistant",
      content: assistantMessage.content,
      decision: assistantMessage.decision || "answer",
      supportPhone: assistantMessage.supportPhone || "",
      source: assistantMessage.source || "model",
    });
  }
  return normalized.slice(-20);
}

export const useAiChatStore = defineStore("ai-chat", {
  state: () => ({
    currentIdentity: "",
    hydrated: false,
    isOpen: false,
    panelWidth:
      Number(localStorage.getItem(PANEL_WIDTH_KEY)) ||
      Math.min(640, Math.max(360, Math.round(window.innerWidth / 3))),
    ballPosition: readJson(localStorage, BALL_POSITION_KEY, null),
    messages: [],
    summary: "",
    selectedRecordIds: [],
    consentGiven: false,
    isSending: false,
    pendingMessage: "",
    lastModel: "",
  }),
  actions: {
    initialize(userId = null) {
      const nextIdentity = identityKey(userId);
      if (this.hydrated && this.currentIdentity === nextIdentity) {
        return;
      }

      this.currentIdentity = nextIdentity;
      this.messages = [];
      this.summary = "";
      this.selectedRecordIds = [];
      this.consentGiven = false;
      this.pendingMessage = "";
      this.lastModel = "";

      const saved = readJson(sessionStorage, sessionKey(nextIdentity), null);
      if (saved) {
        this.messages = normalizeMessages(saved.messages);
        this.summary = typeof saved.summary === "string" ? saved.summary : "";
        this.selectedRecordIds = Array.isArray(saved.selectedRecordIds)
          ? saved.selectedRecordIds.filter(Number.isInteger).slice(0, 5)
          : [];
        this.consentGiven = saved.consentGiven === true;
        this.isOpen = saved.isOpen === true;
        this.lastModel = typeof saved.lastModel === "string" ? saved.lastModel : "";
      }
      this.hydrated = true;
    },

    persist() {
      if (!this.currentIdentity) {
        return;
      }
      sessionStorage.setItem(
        sessionKey(this.currentIdentity),
        JSON.stringify({
          messages: this.messages,
          summary: this.summary,
          selectedRecordIds: this.selectedRecordIds,
          consentGiven: this.consentGiven,
          isOpen: this.isOpen,
          lastModel: this.lastModel,
        })
      );
    },

    switchIdentity(userId = null) {
      this.hydrated = false;
      this.initialize(userId);
    },

    setOpen(value) {
      this.isOpen = value;
      this.persist();
    },

    setPanelWidth(width) {
      this.panelWidth = Math.round(width);
      localStorage.setItem(PANEL_WIDTH_KEY, String(this.panelWidth));
    },

    setBallPosition(position) {
      this.ballPosition = position;
      localStorage.setItem(BALL_POSITION_KEY, JSON.stringify(position));
    },

    setSelectedRecordIds(ids) {
      this.selectedRecordIds = [...new Set(ids)].slice(0, 5);
      if (this.selectedRecordIds.length === 0) {
        this.consentGiven = false;
      }
      this.persist();
    },

    setConsentGiven(value) {
      this.consentGiven = value;
      this.persist();
    },

    clearConversation({ close = true } = {}) {
      if (this.currentIdentity) {
        sessionStorage.removeItem(sessionKey(this.currentIdentity));
      }
      this.messages = [];
      this.summary = "";
      this.selectedRecordIds = [];
      this.consentGiven = false;
      this.pendingMessage = "";
      this.lastModel = "";
      if (close) {
        this.isOpen = false;
      }
    },

    async sendMessage(content, authenticated) {
      const message = content.trim();
      if (!message || this.isSending) {
        return null;
      }

      const oldHistory = this.messages.map(({ role, content: itemContent }) => ({
        role,
        content: itemContent,
      }));
      this.isSending = true;
      this.pendingMessage = message;

      try {
        const { data } = await sendAiChat({
          message,
          history: oldHistory,
          summary: this.summary,
          selected_record_ids: authenticated ? this.selectedRecordIds : [],
        });

        const compactedCount = Number(data.compacted_count) || 0;
        if (compactedCount > 0) {
          this.messages.splice(0, compactedCount);
        }
        this.messages.push({ role: "user", content: message });
        this.messages.push({
          role: "assistant",
          content: data.reply,
          decision: data.decision || "answer",
          supportPhone: data.support_phone || "",
          source: data.source || "model",
        });
        this.summary = data.summary || "";
        this.lastModel = data.model || this.lastModel;
        this.persist();
        return data;
      } finally {
        this.isSending = false;
        this.pendingMessage = "";
      }
    },
  },
});
