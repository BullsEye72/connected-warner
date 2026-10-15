export type SupabaseConfig = { url: string; key: string };

export function parseSupabaseConfig(url?: string, key?: string): SupabaseConfig | null {
  if (!url || !key) return null;
  try {
    const parsed = new URL(url);
    const local = ["localhost", "127.0.0.1"].includes(parsed.hostname);
    if (parsed.protocol !== "https:" && !(local && parsed.protocol === "http:")) return null;
    if (parsed.username || parsed.password || parsed.search || parsed.hash) return null;
    if (!key.startsWith("sb_publishable_")) {
      // Les anciennes cles anon sont des JWT. Refuser toute cle de service.
      const payload = JSON.parse(Buffer.from(key.split(".")[1] ?? "", "base64url").toString());
      if (payload.role !== "anon") return null;
    }
    return { url: parsed.origin, key };
  } catch {
    return null;
  }
}

export function getSupabaseConfig() {
  return parseSupabaseConfig(
    process.env.NEXT_PUBLIC_SUPABASE_URL,
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
  );
}

export function getSiteUrl() {
  const url = process.env.NEXT_PUBLIC_SITE_URL ||
    (process.env.NODE_ENV === "development" ? "http://localhost:3000" : "https://connected-warner.vercel.app");
  return new URL(url).origin;
}
