"use client";

/**
 * Identity (CLAUDE.md §46: enforce authorization on every creator-scoped
 * operation). Two backing modes, matching the backend's own precedent
 * (app/api/deps.py::get_current_user_id):
 *
 * - Real mode (lib/supabase.ts's `supabase` is non-null): the auth user id
 *   and access token come from a live Supabase session, kept in sync via
 *   onAuthStateChange. lib/api.ts sends the access token as a Bearer
 *   header.
 * - Dev mode (Supabase not configured): a locally-generated id round-
 *   tripped through POST /creators, sent as X-Debug-User-Id — exactly the
 *   placeholder this file used before real auth existed.
 *
 * Either way, which *creator* is active is our own app concept, not
 * Supabase's, so it's always cached locally regardless of mode.
 */

import { supabase } from "./supabase";

const CREATOR_STORAGE_KEY = "creatoros.creator";
const DEV_USER_STORAGE_KEY = "creatoros.devUserId";

export interface Session {
  userId: string;
  creatorId: string;
  creatorName: string;
}

interface CreatorCache {
  creatorId: string;
  creatorName: string;
}

let cachedAuthUserId: string | null = null;
let cachedAccessToken: string | null = null;
// True immediately in dev mode (nothing async to wait for); in real mode,
// flips true once the initial supabase.auth.getSession() call resolves.
let authReady = !supabase;
const authReadyListeners: Array<() => void> = [];
const authChangeListeners: Array<() => void> = [];

function resolveAuthReady() {
  if (authReady) return;
  authReady = true;
  authReadyListeners.splice(0).forEach((cb) => cb());
}

if (supabase) {
  supabase.auth.getSession().then(({ data }) => {
    cachedAuthUserId = data.session?.user.id ?? null;
    cachedAccessToken = data.session?.access_token ?? null;
    resolveAuthReady();
  });

  supabase.auth.onAuthStateChange((_event, newSession) => {
    cachedAuthUserId = newSession?.user.id ?? null;
    cachedAccessToken = newSession?.access_token ?? null;
    resolveAuthReady();
    authChangeListeners.forEach((cb) => cb());
  });
}

/** True once the initial auth state (signed in or not) is known. Always
 * true synchronously in dev mode. */
export function isAuthReady(): boolean {
  return authReady;
}

/** Fires immediately if auth state is already known, else once it resolves. */
export function onAuthReady(cb: () => void): void {
  if (authReady) {
    cb();
    return;
  }
  authReadyListeners.push(cb);
}

/** Fires on every sign-in/sign-out (real mode only; a no-op subscription in dev mode). */
export function onAuthChange(cb: () => void): () => void {
  authChangeListeners.push(cb);
  return () => {
    const i = authChangeListeners.indexOf(cb);
    if (i >= 0) authChangeListeners.splice(i, 1);
  };
}

function getCreatorCache(): CreatorCache | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(CREATOR_STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as CreatorCache;
  } catch {
    return null;
  }
}

/** True once signed in (real mode) or once a dev identity has been minted
 * (dev mode) — independent of whether a creator has been picked/created yet. */
export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  if (supabase) return cachedAuthUserId !== null;
  return window.localStorage.getItem(DEV_USER_STORAGE_KEY) !== null;
}

/** Full session (auth identity + active creator), or null if either half is
 * missing. Synchronous — safe to call from render/effects once isAuthReady(). */
export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  const creator = getCreatorCache();
  if (!creator) return null;

  if (supabase) {
    if (!cachedAuthUserId) return null;
    return { userId: cachedAuthUserId, creatorId: creator.creatorId, creatorName: creator.creatorName };
  }

  const devUserId = window.localStorage.getItem(DEV_USER_STORAGE_KEY);
  if (!devUserId) return null;
  return { userId: devUserId, creatorId: creator.creatorId, creatorName: creator.creatorName };
}

/** Records just the active creator — the common case once already
 * authenticated (e.g. login picking an existing creator), where there's no
 * fresh userId to also record. */
export function setActiveCreator(creatorId: string, creatorName: string): void {
  window.localStorage.setItem(
    CREATOR_STORAGE_KEY,
    JSON.stringify({ creatorId, creatorName } satisfies CreatorCache)
  );
}

/** Records the active creator (both modes) and, in dev mode only, the
 * locally-minted user id — in real mode the auth identity already lives in
 * the Supabase session, not here. */
export function setSession(session: Session): void {
  window.localStorage.setItem(
    CREATOR_STORAGE_KEY,
    JSON.stringify({ creatorId: session.creatorId, creatorName: session.creatorName } satisfies CreatorCache)
  );
  if (!supabase) {
    window.localStorage.setItem(DEV_USER_STORAGE_KEY, session.userId);
  }
}

/** Forgets the active creator (and, in dev mode, the local identity) — does
 * NOT sign out of Supabase; call supabase.auth.signOut() for that (see
 * components/nav-sidebar.tsx). */
export function clearSession(): void {
  window.localStorage.removeItem(CREATOR_STORAGE_KEY);
  window.localStorage.removeItem(DEV_USER_STORAGE_KEY);
}

/** The current Supabase access token, for lib/api.ts to send as a Bearer
 * header. Null in dev mode (api.ts falls back to X-Debug-User-Id) or if
 * signed out. */
export async function getAccessToken(): Promise<string | null> {
  if (!supabase) return null;
  if (cachedAccessToken) return cachedAccessToken;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/** Auth headers for lib/api.ts's request() — independent of getSession(),
 * which also requires a cached *creator* and so returns null during
 * onboarding (an authenticated user with no creator yet still needs to be
 * able to call POST /creators). Empty object when signed out in either mode. */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  if (supabase) {
    const token = await getAccessToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  }
  if (typeof window === "undefined") return {};
  const devUserId = window.localStorage.getItem(DEV_USER_STORAGE_KEY);
  return devUserId ? { "X-Debug-User-Id": devUserId } : {};
}
