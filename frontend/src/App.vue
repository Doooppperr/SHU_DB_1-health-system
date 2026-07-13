<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <div
    class="app-with-ai"
    :class="{ 'ai-panel-active': showAi && aiStore.isOpen }"
    :style="{ '--ai-panel-width': `${aiStore.panelWidth}px` }"
  >
    <div class="app-route-stage">
      <router-view />
    </div>
    <AiAssistant v-if="showAi" />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, watch } from "vue";
import { useRoute } from "vue-router";

import AiAssistant from "./components/AiAssistant.vue";
import { useAiChatStore } from "./stores/aiChat";
import { useAuthStore } from "./stores/auth";

const authStore = useAuthStore();
const aiStore = useAiChatStore();
const route = useRoute();
const guestAiRoutes = new Set(["public-home", "login", "register"]);
let tableObserver = null;
let tableResizeObserver = null;
const showAi = computed(() => {
  if (authStore.accessToken) return authStore.user?.role === "user";
  return guestAiRoutes.has(route.name);
});

authStore.hydrate();
aiStore.initialize(authStore.user?.id || null);

watch(
  () => authStore.user?.id || null,
  (userId) => aiStore.switchIdentity(userId)
);

watch(showAi, (visible) => {
  if (!visible) aiStore.setOpen(false);
});

watch(
  () => route.fullPath,
  async () => {
    await nextTick();
    const mainContent = document.querySelector("#main-content");
    if (mainContent instanceof HTMLElement) {
      mainContent.focus({ preventScroll: true });
    }
    enhanceDataTables();
  }
);

function enhanceDataTables(root = document) {
  const tables = [];
  if (root instanceof HTMLElement && root.matches(".el-table")) tables.push(root);
  tables.push(...(root.querySelectorAll?.(".el-table") || []));
  tables.forEach((table) => {
    if (!(table instanceof HTMLElement)) return;
    const scroller = table.querySelector(".el-scrollbar__wrap, .el-table__body-wrapper");
    if (!(scroller instanceof HTMLElement)) return;
    table.removeAttribute("tabindex");
    table.removeAttribute("aria-label");
    if (!scroller.hasAttribute("tabindex")) scroller.tabIndex = 0;
    scroller.setAttribute("role", "region");
    scroller.setAttribute("aria-label", "数据表格；可使用方向键或触控横向滚动查看完整内容");

    if (!table.dataset.accessibleScroll) {
      const hint = document.createElement("p");
      hint.className = "table-scroll-hint";
      hint.textContent = "横向滚动查看完整表格 →";
      hint.hidden = true;
      hint.setAttribute("aria-hidden", "true");
      table.before(hint);
      table.dataset.accessibleScroll = "true";
    }

    tableResizeObserver?.observe(scroller);
    window.requestAnimationFrame?.(() => updateTableScrollState(scroller));
  });
}

function updateTableScrollState(scroller) {
  if (!(scroller instanceof HTMLElement)) return;
  const table = scroller.closest(".el-table");
  const hint = table?.previousElementSibling;
  const scrollable = scroller.scrollWidth > scroller.clientWidth + 2;
  table?.toggleAttribute("data-horizontal-scroll", scrollable);
  if (hint?.classList.contains("table-scroll-hint")) hint.hidden = !scrollable;
}

onMounted(() => {
  if (typeof ResizeObserver === "function") {
    tableResizeObserver = new ResizeObserver((entries) => {
      entries.forEach((entry) => updateTableScrollState(entry.target));
    });
  }
  enhanceDataTables();
  if (typeof MutationObserver !== "function") return;
  tableObserver = new MutationObserver((records) => {
    records.forEach((record) => {
      record.addedNodes.forEach((node) => {
        if (node instanceof HTMLElement) {
          if (node.matches(".el-table")) enhanceDataTables(node.parentElement || node);
          else {
            enhanceDataTables(node);
            const owningTable = node.closest(".el-table");
            if (owningTable) enhanceDataTables(owningTable);
          }
        }
      });
    });
  });
  tableObserver.observe(document.body, { childList: true, subtree: true });
});

onBeforeUnmount(() => {
  tableObserver?.disconnect();
  tableResizeObserver?.disconnect();
});
</script>
