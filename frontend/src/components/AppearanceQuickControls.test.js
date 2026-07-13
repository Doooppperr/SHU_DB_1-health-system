import { mount } from "@vue/test-utils";
import { createPinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AppearanceQuickControls from "./AppearanceQuickControls.vue";
import { useAppearanceStore } from "../stores/appearance";

const originalMatchMedia = window.matchMedia;
const wrappers = [];

beforeEach(() => {
  window.sessionStorage.clear();
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn(() => ({
      matches: false,
      media: "(prefers-color-scheme: dark)",
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

afterEach(() => {
  wrappers.splice(0).forEach((wrapper) => wrapper.unmount());
  vi.restoreAllMocks();
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  });
});

function mountControls() {
  const pinia = createPinia();
  const wrapper = mount(AppearanceQuickControls, {
    attachTo: document.body,
    global: { plugins: [pinia] },
  });
  wrappers.push(wrapper);
  return { wrapper, store: useAppearanceStore(pinia) };
}

describe("AppearanceQuickControls", () => {
  it("opens an accessible three-option theme menu and selects a mode", async () => {
    const { wrapper, store } = mountControls();
    const trigger = wrapper.get('[data-testid="appearance-theme-trigger"]');

    expect(trigger.attributes("aria-label")).toBe("主题模式，当前跟随系统");
    expect(trigger.attributes("aria-expanded")).toBe("false");
    await trigger.trigger("click");

    expect(trigger.attributes("aria-expanded")).toBe("true");
    const options = wrapper.findAll('[role="menuitemradio"]');
    expect(options.map((option) => option.text())).toEqual(["跟随系统", "亮色模式", "暗色模式"]);
    expect(options[0].attributes("aria-checked")).toBe("true");

    await options[2].trigger("click");
    expect(store.themeMode).toBe("dark");
    expect(trigger.attributes("aria-label")).toBe("主题模式，当前暗色模式");
    expect(wrapper.find('[role="menu"]').exists()).toBe(false);
  });

  it("toggles care mode directly and exposes its pressed state", async () => {
    const { wrapper, store } = mountControls();
    const careButton = wrapper.get('[data-testid="appearance-care-trigger"]');

    expect(careButton.attributes("aria-label")).toBe("开启关怀模式");
    expect(careButton.attributes("aria-pressed")).toBe("false");
    await careButton.trigger("click");

    expect(store.careMode).toBe(true);
    expect(careButton.attributes("aria-label")).toBe("关闭关怀模式");
    expect(careButton.attributes("aria-pressed")).toBe("true");
    expect(document.documentElement.dataset.care).toBe("on");
  });

  it("closes the theme menu with Escape and restores trigger focus", async () => {
    const { wrapper } = mountControls();
    const trigger = wrapper.get('[data-testid="appearance-theme-trigger"]');
    await trigger.trigger("click");

    const menu = wrapper.get('[role="menu"]');
    await menu.trigger("keydown", { key: "Escape" });
    await wrapper.vm.$nextTick();

    expect(wrapper.find('[role="menu"]').exists()).toBe(false);
    expect(document.activeElement).toBe(trigger.element);
  });
});
