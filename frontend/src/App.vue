<template>
  <div
    class="app-with-ai"
    :class="{ 'ai-panel-active': aiStore.isOpen }"
    :style="{ '--ai-panel-width': `${aiStore.panelWidth}px` }"
  >
    <main class="app-route-stage">
      <router-view />
    </main>
    <AiAssistant />
  </div>
</template>

<script setup>
import { watch } from "vue";

import AiAssistant from "./components/AiAssistant.vue";
import { useAiChatStore } from "./stores/aiChat";
import { useAuthStore } from "./stores/auth";

const authStore = useAuthStore();
const aiStore = useAiChatStore();

authStore.hydrate();
aiStore.initialize(authStore.user?.id || null);

watch(
  () => authStore.user?.id || null,
  (userId) => aiStore.switchIdentity(userId)
);
</script>
