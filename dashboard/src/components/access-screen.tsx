import { Brand } from "./brand";
import { Refresh } from "./refresh";
import { SubmitButton } from "./submit-button";
import { signOut } from "@/app/auth/actions";

export function AccessScreen({ title, children, email, refresh = true }: {
  title: string; children: React.ReactNode; email?: string; refresh?: boolean;
}) {
  return <main className="auth-page">
    {refresh && <Refresh />}
    <div className="auth-brand"><Brand /></div>
    <section className="auth-card">
      <span className="eyebrow">LOGEMENT PRIVÉ</span><h1>{title}<span>.</span></h1>
      {email && <p className="access-email">{email}</p>}
      {children}
      <a className="text-link" href="/">Actualiser ↗</a>
      <form action={signOut} className="onboarding-signout"><SubmitButton className="quiet-button">Se déconnecter</SubmitButton></form>
    </section>
  </main>;
}
