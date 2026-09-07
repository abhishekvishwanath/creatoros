"use client";

import { useEffect, useState } from "react";
import { getSession } from "./session";
import { getCreatorState } from "./api";
import type { CreatorStateSnapshot } from "./types";

/**
 * Shared by every page that needs the Creator State Snapshot (CLAUDE.md §32).
 * `loading` always resolves to false, even with no session or a failed fetch,
 * so callers can render a definite "couldn't load" state instead of spinning
 * forever (e.g. if the session was cleared in another tab after this page
 * mounted).
 */
export function useCreatorState() {
  const [state, setState] = useState<CreatorStateSnapshot | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = getSession();
    if (!session) {
      setLoading(false);
      return;
    }
    getCreatorState(session.creatorId)
      .then(setState)
      .finally(() => setLoading(false));
  }, []);

  return { state, loading };
}
