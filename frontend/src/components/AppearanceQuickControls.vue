<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from "vue";

import { useAppearanceStore } from "../stores/appearance";

const appearance = useAppearanceStore();
appearance.initialize();

const themeOptions = Object.freeze([
  { value: "system", label: "跟随系统" },
  { value: "light", label: "亮色模式" },
  { value: "dark", label: "暗色模式" },
]);

const root = ref(null);
const themeTrigger = ref(null);
const optionElements = ref([]);
const themeMenuOpen = ref(false);
const menuId = `appearance-theme-menu-${useId()}`;

const currentThemeLabel = computed(
  () => themeOptions.find((option) => option.value === appearance.themeMode)?.label ?? "跟随系统"
);
const themeButtonLabel = computed(() => `主题模式，当前${currentThemeLabel.value}`);
const careButtonLabel = computed(() =>
  appearance.careMode ? "关闭关怀模式" : "开启关怀模式"
);

function setOptionElement(element, index) {
  if (element) {
    optionElements.value[index] = element;
  }
}

async function openThemeMenu() {
  themeMenuOpen.value = true;
  await nextTick();
  const currentIndex = Math.max(
    0,
    themeOptions.findIndex((option) => option.value === appearance.themeMode)
  );
  optionElements.value[currentIndex]?.focus();
}

function closeThemeMenu(restoreFocus = false) {
  themeMenuOpen.value = false;
  if (restoreFocus) {
    nextTick(() => themeTrigger.value?.focus());
  }
}

function toggleThemeMenu() {
  if (themeMenuOpen.value) {
    closeThemeMenu(true);
    return;
  }
  openThemeMenu();
}

function selectTheme(themeMode) {
  appearance.setThemeMode(themeMode);
  closeThemeMenu(true);
}

function handleMenuKeydown(event) {
  if (event.key === "Escape") {
    event.preventDefault();
    closeThemeMenu(true);
    return;
  }

  const supportedKeys = ["ArrowDown", "ArrowUp", "Home", "End"];
  if (!supportedKeys.includes(event.key)) {
    return;
  }

  event.preventDefault();
  const options = optionElements.value.filter(Boolean);
  if (!options.length) {
    return;
  }

  const currentIndex = Math.max(0, options.indexOf(document.activeElement));
  let nextIndex = currentIndex;
  if (event.key === "ArrowDown") {
    nextIndex = (currentIndex + 1) % options.length;
  } else if (event.key === "ArrowUp") {
    nextIndex = (currentIndex - 1 + options.length) % options.length;
  } else if (event.key === "Home") {
    nextIndex = 0;
  } else if (event.key === "End") {
    nextIndex = options.length - 1;
  }
  options[nextIndex]?.focus();
}

function handleOutsidePointer(event) {
  if (themeMenuOpen.value && !root.value?.contains(event.target)) {
    closeThemeMenu();
  }
}

onMounted(() => document.addEventListener("pointerdown", handleOutsidePointer));
onBeforeUnmount(() => document.removeEventListener("pointerdown", handleOutsidePointer));
</script>

<template>
  <div ref="root" class="appearance-controls" aria-label="外观设置">
    <div class="appearance-controls__theme">
      <button
        ref="themeTrigger"
        class="appearance-control"
        type="button"
        :aria-label="themeButtonLabel"
        aria-haspopup="menu"
        :aria-expanded="themeMenuOpen"
        :aria-controls="menuId"
        :title="themeButtonLabel"
        data-testid="appearance-theme-trigger"
        @click="toggleThemeMenu"
        @keydown.down.prevent="openThemeMenu"
      >
        <span aria-hidden="true" class="appearance-control__theme-icon">◐</span>
        <span class="appearance-control__label">主题：{{ currentThemeLabel }}</span>
      </button>

      <div
        v-if="themeMenuOpen"
        :id="menuId"
        class="appearance-menu"
        role="menu"
        aria-label="选择主题模式"
        @keydown="handleMenuKeydown"
      >
        <button
          v-for="(option, index) in themeOptions"
          :key="option.value"
          :ref="(element) => setOptionElement(element, index)"
          class="appearance-menu__option"
          :class="{ 'is-selected': appearance.themeMode === option.value }"
          type="button"
          role="menuitemradio"
          :aria-checked="appearance.themeMode === option.value"
          @click="selectTheme(option.value)"
        >
          <span class="appearance-menu__indicator" aria-hidden="true" />
          <span>{{ option.label }}</span>
        </button>
      </div>
    </div>

    <button
      class="appearance-control"
      :class="{ 'is-active': appearance.careMode }"
      type="button"
      :aria-label="careButtonLabel"
      :aria-pressed="appearance.careMode"
      :title="careButtonLabel"
      data-testid="appearance-care-trigger"
      @click="appearance.toggleCareMode()"
    >
      <span class="appearance-control__care-icon" aria-hidden="true">A+</span>
      <span class="appearance-control__label">关怀模式</span>
    </button>
  </div>
</template>

<style scoped>
.appearance-controls {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
}

.appearance-controls__theme {
  position: relative;
}

.appearance-control {
  min-height: var(--control-min-height, 2.5rem);
  padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
  border: 1px solid var(--color-border, #d2d2d7);
  border-radius: var(--radius-sm, 0.75rem);
  background: var(--color-surface, #fff);
  color: var(--color-text, #1d1d1f);
  box-shadow: var(--shadow-sm, 0 1px 2px rgb(0 0 0 / 8%));
  font: inherit;
  font-size: var(--text-sm, 0.875rem);
  line-height: 1.25;
  white-space: nowrap;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2, 0.5rem);
}

.appearance-control:hover {
  border-color: var(--color-text-secondary, #5f6368);
  background: var(--color-surface-muted, #f5f5f7);
}

.appearance-control:focus-visible,
.appearance-menu__option:focus-visible {
  outline: 3px solid var(--color-focus, #0b7a6b);
  outline-offset: 2px;
}

.appearance-control.is-active {
  border-color: var(--color-accent, #0b7a6b);
  background: var(--color-accent-soft, #e7f3f0);
  color: var(--color-accent-strong, #075f54);
}

.appearance-control__theme-icon {
  width: 1.125rem;
  flex: 0 0 auto;
  font-size: 1.05rem;
  line-height: 1;
  text-align: center;
}

.appearance-control__care-icon {
  min-width: 1.5rem;
  font-size: var(--text-sm, 0.875rem);
  font-weight: 700;
  letter-spacing: -0.04em;
}

.appearance-menu {
  position: absolute;
  z-index: var(--z-popover, 1000);
  top: calc(100% + var(--space-2, 0.5rem));
  right: 0;
  min-width: 10rem;
  padding: var(--space-2, 0.5rem);
  border: 1px solid var(--color-border, #d2d2d7);
  border-radius: var(--radius-md, 0.875rem);
  background: var(--color-surface-elevated, var(--color-surface, #fff));
  box-shadow: var(--shadow-md, 0 0.75rem 2rem rgb(0 0 0 / 14%));
}

.appearance-menu__option {
  width: 100%;
  min-height: var(--control-min-height, 2.5rem);
  padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
  border: 0;
  border-radius: var(--radius-sm, 0.625rem);
  background: transparent;
  color: var(--color-text, #1d1d1f);
  font: inherit;
  font-size: var(--text-sm, 0.875rem);
  text-align: left;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
}

.appearance-menu__option:hover,
.appearance-menu__option.is-selected {
  background: var(--color-accent-soft, rgb(11 122 107 / 12%));
}

.appearance-menu__indicator {
  width: 0.75rem;
  height: 0.75rem;
  border: 2px solid var(--color-text-secondary, #5f6368);
  border-radius: 50%;
  flex: 0 0 auto;
}

.appearance-menu__option.is-selected .appearance-menu__indicator {
  border: 3px solid var(--color-accent, #0b7a6b);
}

@media (max-width: 37.5rem) {
  .appearance-control {
    width: 2.75rem;
    min-width: 2.75rem;
    padding-inline: var(--space-2, 0.5rem);
  }

  .appearance-control__label {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    border: 0;
  }
}
</style>
