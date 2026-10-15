import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { getSiteUrl, getSupabaseConfig } from "@/lib/supabase/config";

export async function GET(request: Request) {
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  if (code && !url.searchParams.has("error") && getSupabaseConfig()) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) {
      // Destination fixe : ne jamais suivre un parametre next fourni par l'URL.
      const response = NextResponse.redirect(new URL("/", getSiteUrl()));
      response.headers.set("Cache-Control", "private, no-store");
      return response;
    }
  }
  const response = NextResponse.redirect(new URL("/login?error=retour-google", getSiteUrl()));
  response.headers.set("Cache-Control", "private, no-store");
  return response;
}
