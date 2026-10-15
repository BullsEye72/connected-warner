import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { getSupabaseConfig } from "./config";
import type { Database } from "./database.types";

export async function createClient() {
  const config = getSupabaseConfig();
  if (!config) throw new Error("Supabase public configuration is missing or invalid.");
  const store = await cookies();
  return createServerClient<Database>(config.url, config.key, {
    cookies: {
      getAll: () => store.getAll(),
      setAll(values) {
        try {
          values.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // Les Server Components ne peuvent pas ecrire les cookies.
          // src/proxy.ts rafraichit la session avant leur execution.
        }
      },
    },
  });
}
