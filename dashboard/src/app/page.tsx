import { redirect } from "next/navigation";
import { AccessScreen } from "@/components/access-screen";
import { AccessManagement } from "@/components/access-management";
import { DashboardView } from "@/components/dashboard-view";
import { RegistrationForm } from "@/components/registration-form";
import { displayDevice } from "@/lib/device-status";
import { getSupabaseConfig } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Home({ searchParams }: { searchParams: Promise<{ error?: string }> }) {
  if (!getSupabaseConfig()) redirect("/login");
  const supabase = await createClient();
  const { data: auth, error: authError } = await supabase.auth.getUser();
  if (authError || !auth.user) redirect("/login");
  const [{ data: isAdmin, error: adminError }, { data: member, error: memberError }] = await Promise.all([
    supabase.rpc("is_dashboard_admin"),
    supabase.from("dashboard_members").select("*").eq("user_id", auth.user.id).maybeSingle(),
  ]);
  if (adminError || memberError || !member) return <AccessScreen title="Accès indisponible" email={auth.user.email}>
    <p className="form-error" role="alert">Les accès n’ont pas pu être vérifiés. Si l’installation vient d’être mise à jour, la base doit encore être préparée.</p>
  </AccessScreen>;
  if (!isAdmin && member.status !== "approved") return <AccessScreen title={member.status === "rejected" ? "Accès non autorisé" : "Demande en attente"} email={auth.user.email}>
    <p className="auth-intro">{member.status === "rejected" ? "L’administrateur n’a pas autorisé votre accès à ce logement. Contactez-le si nécessaire." : "Votre demande est enregistrée. L’administrateur doit l’autoriser avant que vous puissiez consulter les boîtiers du logement."}</p>
  </AccessScreen>;

  const { data: household, error: householdError } = await supabase.from("households").select("*").maybeSingle();
  const { error: pageError } = await searchParams;

  if (householdError || !household) {
    return <AccessScreen title={householdError ? "Lecture indisponible" : isAdmin ? "Bienvenue" : "Logement en préparation"} email={auth.user.email}>
      {householdError ? <p className="form-error" role="alert">Les données du logement sont indisponibles. Réessayez dans un instant.</p> : isAdmin ? <><p className="auth-intro">Vous êtes administrateur de cette installation. Donnez un nom au logement partagé pour commencer.</p><RegistrationForm kind="household" /></> : <p className="auth-intro">Votre accès est autorisé. L’administrateur doit encore créer le logement partagé.</p>}
    </AccessScreen>;
  }

  const { data: devices, error: deviceError } = await supabase.from("devices").select("*").eq("household_id", household.id).order("created_at");
  if (deviceError) return <AccessScreen title="Lecture indisponible" email={auth.user.email}><p className="form-error" role="alert">Les boîtiers n’ont pas pu être chargés. Aucun état ne peut être confirmé.</p></AccessScreen>;

  const { data: members, error: membersError } = isAdmin
    ? await supabase.from("dashboard_members").select("*").order("created_at")
    : { data: null, error: null };

  const now = Date.now();
  return (
    <DashboardView householdName={household.name} devices={(devices ?? []).map(device => displayDevice(device, now))} email={auth.user.email} canManage={isAdmin === true}>
      {pageError === "deconnexion" && <p className="form-error" role="alert">La déconnexion n’a pas abouti. Réessayez.</p>}
      {isAdmin && <>
        <details className="add-device"><summary>Ajouter un boîtier <span aria-hidden="true">＋</span></summary><p>Enregistrez le boîtier, puis ouvrez ses détails pour créer sa clé de connexion.</p><RegistrationForm kind="device" /></details>
        {membersError ? <p className="form-error" role="alert">La liste des accès est indisponible. Actualisez pour réessayer.</p> : <AccessManagement members={members ?? []} adminId={auth.user.id} />}
      </>}
    </DashboardView>
  );
}
