"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export type FormState = { error: string };

async function authenticatedClient() {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) redirect("/login");
  return { supabase, user: data.user };
}

function text(form: FormData, key: string) {
  const value = form.get(key);
  return typeof value === "string" ? value.trim() : "";
}

export async function createHousehold(_state: FormState, form: FormData): Promise<FormState> {
  const name = text(form, "name");
  if (!name || name.length > 80 || /[\u0000-\u001f\u007f]/.test(name)) return { error: "Indiquez un nom de logement de 1 à 80 caractères." };
  const { supabase, user } = await authenticatedClient();
  const { error } = await supabase.from("households").insert({ name, owner_id: user.id });
  if (error && error.code !== "23505") return { error: "Le logement n’a pas pu être enregistré. Réessayez." };
  revalidatePath("/");
  redirect("/");
}

export async function createDevice(_state: FormState, form: FormData): Promise<FormState> {
  const name = text(form, "name");
  const location = text(form, "location");
  if (!name || name.length > 40 || location.length > 80 || /[\u0000-\u001f\u007f]/.test(name + location)) return { error: "Indiquez un nom de 1 à 40 caractères et un emplacement de 80 caractères maximum." };
  const { supabase, user } = await authenticatedClient();
  const { data: household, error: householdError } = await supabase.from("households").select("id").eq("owner_id", user.id).maybeSingle();
  if (householdError || !household) return { error: "Votre logement n’a pas pu être retrouvé. Rechargez la page." };
  const { error } = await supabase.from("devices").insert({ household_id: household.id, name, location });
  if (error) return { error: "Le boîtier n’a pas pu être enregistré. Réessayez." };
  revalidatePath("/");
  redirect("/");
}
