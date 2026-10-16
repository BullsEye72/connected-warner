"use client";

import { useActionState, useState } from "react";
import { generateDeviceKey } from "@/app/actions";
import { SubmitButton } from "./submit-button";

export function DeviceKey({ id }: { id: string }) {
  const [state, action] = useActionState(generateDeviceKey, { error: "", configuration: "" });
  const [hidden, setHidden] = useState(false);
  return <section className="device-pairing" aria-label="Raccordement au dashboard">
    <p>Créer une clé pour connecter ce boîtier. Une nouvelle clé remplace immédiatement la précédente.</p>
    <form action={action} onSubmit={() => setHidden(false)}>
      <input type="hidden" name="device_id" value={id} />
      <SubmitButton className="quiet-button" pendingText="Création…">Créer / remplacer la clé</SubmitButton>
    </form>
    {state.error && <p className="form-error" role="alert">{state.error}</p>}
    {state.configuration && !hidden && <div className="pairing-result">
      <p role="status">Clé créée. Copiez cette configuration dans le profil privé de la carte ; elle ne sera plus affichée après rechargement.</p>
      <textarea aria-label="Configuration privée du dashboard" readOnly value={state.configuration} rows={5} spellCheck={false} />
      <button className="quiet-button" type="button" onClick={() => setHidden(true)}>Masquer la clé</button>
    </div>}
  </section>;
}
