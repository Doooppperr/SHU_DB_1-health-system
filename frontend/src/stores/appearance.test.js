import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  APPEARANCE_STORAGE_KEY,
  useAppearanceStore,
} from "./appearance";

const originalMatchMedia = window.matchMedia;
const stores = [];

function installMatchMedia(initialMatches = false) {
  let matches = initialMatches;
  const listeners = new Set();
  const mediaQuery = {
    media: "(prefers-color-scheme: dark)",
    get matches() {
      return matches;
    },
    onchange: null,
    addEventListener: vi.fn((_type, listener) => listeners.add(listener)),
    removeEventListener: vi.fn((_type, listener) => listeners.delete(listener)),
    addListener: vi.fn((listener) => listeners.add(listener)),
    removeListener: vi.fn((listener) => listeners.delete(listener)),
    dispatchEvent: vi.fn(),
  };

  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: vi.fn(() => mediaQuery),
  });

  return {
    mediaQuery,
    change(nextMatches) {
      matches = nextMatches;
      listeners.forEach((listener) => listener({ matches: nextMatches, media: mediaQuery.media }));
    },
  };
}

function createStore() {
  setActivePinia(createPinia());
  const store = useAppearanceStore();
  stores.push(store);
  return store;
}

beforeEach(() => {
  window.sessionStorage.clear();
  installMatchMedia(false);
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-care");
  document.documentElement.removeAttribute("class");
  document.documentElement.removeAttribute("style");
  document.querySelector('meta[name="theme-color"]')?.remove();
});

afterEach(() => {
  stores.splice(0).forEach((store) => store.dispose());
  vi.restoreAllMocks();
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: originalMatchMedia,
  });
});

describe("appearance store", () => {
  it("defaults to the live system theme and synchronizes the document", () => {
    const media = installMatchMedia(true);
    const store = createStore();

    store.initialize();

    expect(store.themeMode).toBe("system");
    expect(store.effectiveTheme).toBe("dark");
    expect(store.careMode).toBe(false);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.care).toBe("off");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.style.colorScheme).toBe("dark");
    expect(document.querySelector('meta[name="theme-color"]')?.content).toBe("#101012");
    expect(media.mediaQuery.addEventListener).toHaveBeenCalledWith("change", expect.any(Function));
  });

  it("tracks system changes only while system mode is selected", () => {
    const media = installMatchMedia(false);
    const store = createStore();
    store.initialize();

    media.change(true);
    expect(store.effectiveTheme).toBe("dark");

    store.setThemeMode("light");
    media.change(false);
    media.change(true);
    expect(store.effectiveTheme).toBe("light");

    store.setThemeMode("system");
    expect(store.effectiveTheme).toBe("dark");
  });

  it("persists independent theme and care preferences for a refreshed tab", () => {
    const firstStore = createStore();
    firstStore.initialize();
    firstStore.setThemeMode("dark");
    firstStore.setCareMode(true);

    expect(JSON.parse(window.sessionStorage.getItem(APPEARANCE_STORAGE_KEY))).toEqual({
      themeMode: "dark",
      careMode: true,
    });

    firstStore.dispose();
    const refreshedStore = createStore();
    refreshedStore.initialize();

    expect(refreshedStore.themeMode).toBe("dark");
    expect(refreshedStore.effectiveTheme).toBe("dark");
    expect(refreshedStore.careMode).toBe(true);
    expect(document.documentElement.dataset.care).toBe("on");
  });

  it("falls back safely when stored data is corrupt", () => {
    window.sessionStorage.setItem(APPEARANCE_STORAGE_KEY, "not-json");
    const store = createStore();

    store.initialize();

    expect(store.themeMode).toBe("system");
    expect(store.effectiveTheme).toBe("light");
    expect(store.careMode).toBe(false);
    expect(window.sessionStorage.getItem(APPEARANCE_STORAGE_KEY)).toBeNull();
  });

  it("uses light mode when matchMedia is unavailable", () => {
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      writable: true,
      value: undefined,
    });
    const store = createStore();

    store.initialize();

    expect(store.themeMode).toBe("system");
    expect(store.effectiveTheme).toBe("light");
  });

  it("continues in memory when sessionStorage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("Blocked", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("Blocked", "SecurityError");
    });
    const store = createStore();

    expect(() => store.initialize()).not.toThrow();
    expect(() => store.setThemeMode("dark")).not.toThrow();
    expect(() => store.toggleCareMode()).not.toThrow();
    expect(store.effectiveTheme).toBe("dark");
    expect(store.careMode).toBe(true);
  });
});
