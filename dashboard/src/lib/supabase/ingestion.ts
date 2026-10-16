import "server-only";
import { createClient } from "@supabase/supabase-js";
import { getSupabaseConfig } from "./config";
import type { Database } from "./database.types";

export function createIngestionClient() {
  const config = getSupabaseConfig();
  if (!config) return null;
  // Client anonyme par requete : la RPC n'autorise que le boitier dont la cle est verifiee.
  return createClient<Database>(config.url, config.key, {
    auth: { persistSession: false, autoRefreshToken: false, detectSessionInUrl: false },
  });
}
