import Link from "next/link";
import { redirect } from "next/navigation";
import { Brand } from "@/components/brand";
import { SubmitButton } from "@/components/submit-button";
import { getSupabaseConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";
import { signInWithGoogle } from "@/app/auth/actions";

export const dynamic = "force-dynamic";

export default async function Login({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  const configured = !!getSupabaseConfig();
  let unavailable = false;
  let signedIn = false;
  if (configured) {
    try {
      const supabase = await createClient();
      const { data } = await supabase.auth.getUser();
      signedIn = !!data.user;
    } catch {
      unavailable = true;
    }
  }
  if (signedIn) redirect("/");
  const { error } = await searchParams;
  return (
    <main className="auth-page">
      <div className="auth-brand"><Brand /></div>
      <section className="auth-card" aria-labelledby="login-title">
        <span className="eyebrow">VOTRE ESPACE PRIVÉ</span>
        <h1 id="login-title">Garder le lien<span>.</span></h1>
        <p className="auth-intro">Connectez-vous pour retrouver vos boîtiers et leur dernière présence.</p>
        {!configured ? <div className="form-notice" role="status">La connexion est en cours de préparation. Vous pouvez consulter l’aperçu en attendant.</div> : <>
          {(error || unavailable) && <p className="form-error" role="alert">La connexion n’a pas abouti. Réessayez avec votre compte Google.</p>}
          <form action={signInWithGoogle}>
            <SubmitButton pendingText="Ouverture de Google…" className="google-button"><span className="google-letter" aria-hidden="true">G</span> Continuer avec Google</SubmitButton>
          </form>
          <p className="auth-note">Ce site est réservé à un seul logement. Le premier compte l’administre ; les suivants attendent son autorisation. Aucun mot de passe à créer ici.</p>
        </>}
        <Link className="text-link" href="/demo">Voir la démonstration <span aria-hidden="true">↗</span></Link>
      </section>
      <p className="auth-footer">Connected Warner · Prendre soin du lien.</p>
    </main>
  );
}
