import { redirect } from "next/navigation";
import { Brand } from "@/components/brand";
import { DashboardView } from "@/components/dashboard-view";
import { RegistrationForm } from "@/components/registration-form";
import { SubmitButton } from "@/components/submit-button";
import { signOut } from "./auth/actions";
import { displayDevice } from "@/lib/device-status";
import { getSupabaseConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (!getSupabaseConfig()) redirect("/login");
  const supabase = await createClient();
  const { data: auth, error: authError } = await supabase.auth.getUser();
  if (authError || !auth.user) redirect("/login");
  const { data: household, error: householdError } = await supabase.from("households").select("*").eq("owner_id", auth.user.id).maybeSingle();
  const { error: pageError } = await searchParams;

  if (householdError || !household) {
    return (
      <main className="auth-page"><div className="auth-brand"><Brand /></div><section className="auth-card">
        <span className="eyebrow">VOTRE ESPACE PRIVÉ</span>
        <h1>Bienvenue<span>.</span></h1>
        {householdError ? <><p className="form-error" role="alert">Les données du logement sont indisponibles. Si c’est la première installation, la base doit encore être préparée.</p><a className="text-link" href="/">Réessayer ↗</a></> : <><p className="auth-intro">Donnez un nom à votre logement pour commencer à enregistrer vos boîtiers.</p><RegistrationForm kind="household" /></>}
        <form action={signOut} className="onboarding-signout"><SubmitButton className="quiet-button">Se déconnecter</SubmitButton></form>
      </section></main>
    );
  }

  const { data: devices, error: deviceError } = await supabase.from("devices").select("*").eq("household_id", household.id).order("created_at");
  if (deviceError) return <main className="auth-page"><section className="auth-card"><Brand /><h1>Lecture indisponible<span>.</span></h1><p className="form-error" role="alert">Les boîtiers n’ont pas pu être chargés. Aucun état ne peut être confirmé.</p><a className="text-link" href="/">Réessayer ↗</a><form action={signOut}><SubmitButton className="quiet-button">Se déconnecter</SubmitButton></form></section></main>;

  const now = Date.now();
  return (
    <DashboardView householdName={household.name} devices={(devices ?? []).map(device => displayDevice(device, now))} email={auth.user.email}>
      {pageError === "deconnexion" && <p className="form-error" role="alert">La déconnexion n’a pas abouti. Réessayez.</p>}
      <details className="add-device"><summary>Ajouter un boîtier <span aria-hidden="true">＋</span></summary><p>Enregistrez le boîtier ici pour préparer son raccordement. Aucun signal réel n’est encore collecté par cette version.</p><RegistrationForm kind="device" /></details>
    </DashboardView>
  );
}
