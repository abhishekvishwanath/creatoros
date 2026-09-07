"use client";

/**
 * Dev-mode identity (CLAUDE.md 46 requires authorization on every
 * creator-scoped operation; real enforcement lives in the backend —
 * see backend/app/api/deps.py). Until Supabase Auth is wired into this
 * frontend, we hold onto the ids returned at onboarding and send the
 * user id as X-Debug-User-Id. Swapping in Supabase Auth later only
 * touches this file and lib/api.ts, not the pages that call them.
 */

const STORAGE_KEY = "creatoros.session";

export interface Session {
  userId: string;
  creatorId: string;
  creatorName: string;
}

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function setSession(session: Session): void {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}
