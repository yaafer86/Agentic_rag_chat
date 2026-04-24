import { create } from "zustand";

type Theme = "light" | "dark";

type ThemeState = {
  theme: Theme;
  toggle: () => void;
  set: (t: Theme) => void;
};

function applyToDocument(t: Theme) {
  const root = document.documentElement;
  if (t === "dark") root.classList.add("dark");
  else root.classList.remove("dark");
}

function initial(): Theme {
  const stored = localStorage.getItem("theme");
  if (stored === "dark" || stored === "light") return stored;
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

const first = initial();
applyToDocument(first);

export const useThemeStore = create<ThemeState>((set) => ({
  theme: first,
  toggle: () =>
    set((s) => {
      const next: Theme = s.theme === "dark" ? "light" : "dark";
      applyToDocument(next);
      localStorage.setItem("theme", next);
      return { theme: next };
    }),
  set: (t) => {
    applyToDocument(t);
    localStorage.setItem("theme", t);
    set({ theme: t });
  },
}));
