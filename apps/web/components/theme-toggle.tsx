"use client";

import { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import { getTheme, toggleTheme, type Theme } from "@/lib/theme";

export function ThemeToggle({ className }: { className?: string }) {
  // Starts null (not "light") so the button renders nothing until mounted —
  // the real theme is decided by the inline script in layout.tsx before
  // paint, and reading it here on mount just syncs this component's icon to
  // whatever that already applied, avoiding a hydration mismatch.
  const [theme, setThemeState] = useState<Theme | null>(null);

  useEffect(() => {
    setThemeState(getTheme());
  }, []);

  if (theme === null) {
    return <div className={className ? `${className} h-8 w-8` : "h-8 w-8"} />;
  }

  return (
    <button
      type="button"
      onClick={() => setThemeState(toggleTheme())}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      className={
        (className ? className + " " : "") +
        "flex h-8 w-8 items-center justify-center rounded-lg text-subtle transition-colors hover:bg-ink/5 hover:text-ink"
      }
    >
      {theme === "dark" ? <Sun className="h-4 w-4" strokeWidth={1.75} /> : <Moon className="h-4 w-4" strokeWidth={1.75} />}
    </button>
  );
}
