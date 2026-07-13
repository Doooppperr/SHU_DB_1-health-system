import { defineStore } from "pinia";

export const APPEARANCE_STORAGE_KEY = "health-system-appearance";
export const THEME_MODES = Object.freeze(["system", "light", "dark"]);

const DARK_MEDIA_QUERY = "(prefers-color-scheme: dark)";
const THEME_COLORS = Object.freeze({
  light: "#f5f5f7",
  dark: "#101012",
});
const subscriptions = new WeakMap();

function isThemeMode(value) {
  return THEME_MODES.includes(value);
}

function getSessionStorage() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function readPreference() {
  const storage = getSessionStorage();
  if (!storage) {
    return { themeMode: "system", careMode: false };
  }

  try {
    const rawPreference = storage.getItem(APPEARANCE_STORAGE_KEY);
    if (!rawPreference) {
      return { themeMode: "system", careMode: false };
    }

    const preference = JSON.parse(rawPreference);
    if (!preference || typeof preference !== "object" || Array.isArray(preference)) {
      throw new TypeError("Invalid appearance preference");
    }

    return {
      themeMode: isThemeMode(preference.themeMode) ? preference.themeMode : "system",
      careMode: preference.careMode === true,
    };
  } catch {
    try {
      storage.removeItem(APPEARANCE_STORAGE_KEY);
    } catch {
      // A failed cleanup should not prevent the application from starting.
    }
    return { themeMode: "system", careMode: false };
  }
}

function persistPreference(themeMode, careMode) {
  const storage = getSessionStorage();
  if (!storage) {
    return;
  }

  try {
    storage.setItem(
      APPEARANCE_STORAGE_KEY,
      JSON.stringify({ themeMode, careMode })
    );
  } catch {
    // Appearance still works in memory when session storage is unavailable.
  }
}

function getSystemMediaQuery() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return null;
  }

  try {
    return window.matchMedia(DARK_MEDIA_QUERY);
  } catch {
    return null;
  }
}

function systemTheme(mediaQuery) {
  return mediaQuery?.matches ? "dark" : "light";
}

function updateDocument(theme, careMode) {
  if (typeof document === "undefined") {
    return;
  }

  const root = document.documentElement;
  root.dataset.theme = theme;
  root.dataset.care = careMode ? "on" : "off";
  root.classList.toggle("dark", theme === "dark");
  root.style.colorScheme = theme;

  let themeColor = document.querySelector('meta[name="theme-color"]');
  if (!themeColor && document.head) {
    themeColor = document.createElement("meta");
    themeColor.name = "theme-color";
    document.head.append(themeColor);
  }
  themeColor?.setAttribute("content", THEME_COLORS[theme]);
}

function addMediaListener(mediaQuery, listener) {
  if (typeof mediaQuery?.addEventListener === "function") {
    mediaQuery.addEventListener("change", listener);
    return;
  }
  mediaQuery?.addListener?.(listener);
}

function removeMediaListener(mediaQuery, listener) {
  if (typeof mediaQuery?.removeEventListener === "function") {
    mediaQuery.removeEventListener("change", listener);
    return;
  }
  mediaQuery?.removeListener?.(listener);
}

function unsubscribe(store) {
  const subscription = subscriptions.get(store);
  if (!subscription) {
    return;
  }
  removeMediaListener(subscription.mediaQuery, subscription.listener);
  subscriptions.delete(store);
}

export const useAppearanceStore = defineStore("appearance", {
  state: () => ({
    themeMode: "system",
    effectiveTheme: "light",
    careMode: false,
    initialized: false,
  }),

  actions: {
    initialize() {
      if (this.initialized) {
        updateDocument(this.effectiveTheme, this.careMode);
        return;
      }

      const preference = readPreference();
      this.themeMode = preference.themeMode;
      this.careMode = preference.careMode;

      const mediaQuery = getSystemMediaQuery();
      this.effectiveTheme =
        this.themeMode === "system" ? systemTheme(mediaQuery) : this.themeMode;

      if (mediaQuery) {
        const listener = (event) => {
          if (this.themeMode !== "system") {
            return;
          }
          this.effectiveTheme = event.matches ? "dark" : "light";
          updateDocument(this.effectiveTheme, this.careMode);
        };
        addMediaListener(mediaQuery, listener);
        subscriptions.set(this, { mediaQuery, listener });
      }

      this.initialized = true;
      updateDocument(this.effectiveTheme, this.careMode);
    },

    setThemeMode(themeMode) {
      const nextMode = isThemeMode(themeMode) ? themeMode : "system";
      this.themeMode = nextMode;
      const mediaQuery = subscriptions.get(this)?.mediaQuery ?? getSystemMediaQuery();
      this.effectiveTheme =
        nextMode === "system" ? systemTheme(mediaQuery) : nextMode;
      persistPreference(this.themeMode, this.careMode);
      updateDocument(this.effectiveTheme, this.careMode);
    },

    setCareMode(enabled) {
      this.careMode = enabled === true;
      persistPreference(this.themeMode, this.careMode);
      updateDocument(this.effectiveTheme, this.careMode);
    },

    toggleCareMode() {
      this.setCareMode(!this.careMode);
    },

    dispose() {
      unsubscribe(this);
      this.initialized = false;
    },
  },
});
