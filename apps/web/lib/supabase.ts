import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/**
 * Null when Supabase isn't configured (apps/web/.env.example: "Leave blank
 * to run in dev-mode auth"), mirroring the backend's own graceful-degrade
 * precedent (ModelRouter falling back to stub mode with no API key,
 * app/api/deps.py::get_current_user_id falling back to X-Debug-User-Id
 * with no SUPABASE_JWT_SECRET). Every caller must handle the null case —
 * see lib/session.ts, which is the only other module that touches this.
 */
export const supabase = supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;
