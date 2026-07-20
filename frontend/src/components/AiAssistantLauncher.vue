<template>
  <button
    v-if="available"
    type="button"
    class="ai-assistant-launcher"
    :class="{ 'is-active': aiStore.isOpen }"
    :aria-expanded="aiStore.isOpen ? 'true' : 'false'"
    aria-controls="ai-chat-panel"
    @click="aiStore.setOpen(!aiStore.isOpen)"
  >
    <span class="ai-assistant-launcher__mark" aria-hidden="true">AI</span>
    <span>{{ aiStore.isOpen ? "收起助手" : "AI 健康助手" }}</span>
  </button>
</template>

<script setup>
import { computed } from "vue";

import { useAiChatStore } from "../stores/aiChat";
import { useAuthStore } from "../stores/auth";

const aiStore = useAiChatStore();
const authStore = useAuthStore();
const available = computed(() => authStore.user?.role === "user");
</script>

<style scoped>
.ai-assistant-launcher {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 7px 12px 7px 8px;
  border: 1px solid color-mix(in srgb, var(--workspace-accent) 28%, #d9e3e1);
  border-radius: 10px;
  color: #36575a;
  background: color-mix(in srgb, var(--workspace-soft) 55%, #fff);
  cursor: pointer;
  font-size: 12px;
  font-weight: 750;
  white-space: nowrap;
}

.ai-assistant-launcher:hover,
.ai-assistant-launcher:focus-visible,
.ai-assistant-launcher.is-active {
  border-color: var(--workspace-accent);
  color: var(--workspace-accent-dark);
  background: var(--workspace-soft);
  outline: none;
}

.ai-assistant-launcher__mark {
  display: grid;
  place-items: center;
  width: 24px;
  height: 24px;
  border-radius: 8px;
  color: #fff;
  background: var(--workspace-accent);
  font-size: 10px;
  letter-spacing: .4px;
}

@media (max-width: 720px) {
  .ai-assistant-launcher > span:last-child {
    display: none;
  }

  .ai-assistant-launcher {
    min-width: 38px;
    padding: 6px;
  }
}
</style>
