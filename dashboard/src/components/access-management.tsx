"use client";

import { useActionState } from "react";
import { setDashboardAccess } from "@/app/actions";
import type { DashboardMember } from "@/lib/supabase/database.types";
import { SubmitButton } from "./submit-button";

function AccessDecision({ member, status, children }: {
  member: DashboardMember; status: "approved" | "rejected"; children: React.ReactNode;
}) {
  const [state, action] = useActionState(setDashboardAccess, { error: "" });
  return <form action={action}>
    <input type="hidden" name="user_id" value={member.user_id} />
    <input type="hidden" name="status" value={status} />
    <SubmitButton className="quiet-button" pendingText="Modification…">{children}</SubmitButton>
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
  </form>;
}

export function AccessManagement({ members, adminId }: { members: DashboardMember[]; adminId: string }) {
  const others = members.filter(member => member.user_id !== adminId);
  const pending = others.filter(member => member.status === "pending");
  const labels = { pending: "En attente", approved: "Accès autorisé", rejected: "Accès refusé" };
  return <section className="access-panel" aria-labelledby="access-title" id="acces">
    <div className="section-heading"><h2 id="access-title">Accès au logement</h2><span>{pending.length} en attente</span></div>
    <p>Vous êtes administrateur. Les personnes que vous autorisez peuvent consulter les boîtiers de ce logement.</p>
    {others.length === 0 ? <p className="access-empty">Aucune autre personne ne s’est encore connectée.</p> : <ul className="access-list">
      {others.map(member => <li key={`${member.user_id}-${member.status}`}>
        <div className="access-person"><strong>{member.email ?? "Compte sans adresse e-mail"}</strong><span>{labels[member.status]}</span></div>
        <div className="access-decisions">
          {member.status !== "approved" && <AccessDecision member={member} status="approved">Autoriser</AccessDecision>}
          {member.status !== "rejected" && <AccessDecision member={member} status="rejected">{member.status === "approved" ? "Retirer l’accès" : "Refuser"}</AccessDecision>}
        </div>
      </li>)}
    </ul>}
  </section>;
}
