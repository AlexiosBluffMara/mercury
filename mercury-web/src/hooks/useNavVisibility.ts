import { useState, useCallback } from "react";

const STORAGE_KEY = "mercury.hiddenNavSections";

/** Sections that are hidden by default to keep the nav clean. */
const DEFAULT_HIDDEN = ["cron", "skills", "config", "env", "docs"];

export type NavSection = "analytics" | "logs" | "cron" | "skills" | "config" | "env" | "docs";

export const ALL_TOGGLEABLE_SECTIONS: NavSection[] = [
  "analytics",
  "logs",
  "cron",
  "skills",
  "config",
  "env",
  "docs",
];

function loadHidden(): NavSection[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored) as NavSection[];
  } catch {
    /* ignore */
  }
  return DEFAULT_HIDDEN as NavSection[];
}

export function useNavVisibility() {
  const [hidden, setHidden] = useState<NavSection[]>(loadHidden);

  const toggle = useCallback((section: NavSection) => {
    setHidden((prev) => {
      const next = prev.includes(section)
        ? prev.filter((s) => s !== section)
        : [...prev, section];
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const isVisible = useCallback(
    (section: NavSection) => !hidden.includes(section),
    [hidden],
  );

  return { hidden, toggle, isVisible };
}
