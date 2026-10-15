"use client";

import { useActionState } from "react";
import { createDevice, createHousehold } from "@/app/actions";
import { SubmitButton } from "./submit-button";

export function RegistrationForm({ kind }: { kind: "household" | "device" }) {
  const household = kind === "household";
  const [state, action] = useActionState(household ? createHousehold : createDevice, { error: "" });
  return (
    <form action={action} className="registration-form">
      <label htmlFor={`${kind}-name`}>{household ? "Nom du logement" : "Nom du boîtier"}</label>
      <input id={`${kind}-name`} name="name" required maxLength={household ? 80 : 40} placeholder={household ? "Mon logement" : "Lit"} autoComplete="off" />
      {!household && <><label htmlFor="device-location">Emplacement <span className="optional">(facultatif)</span></label><input id="device-location" name="location" maxLength={80} placeholder="Chambre" autoComplete="off" /></>}
      {state.error && <p className="form-error" role="alert">{state.error}</p>}
      <SubmitButton pendingText="Enregistrement…">{household ? "Créer mon logement" : "Enregistrer le boîtier"}</SubmitButton>
    </form>
  );
}
