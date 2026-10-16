import Link from "next/link";
import { Brand } from "./brand";
import { SubmitButton } from "./submit-button";
import { Refresh } from "./refresh";
import { DeviceKey } from "./device-key";
import { signOut } from "@/app/auth/actions";
import type { DisplayDevice } from "@/lib/device-status";

export function DashboardView({ householdName, devices, email, demo = false, canManage = false, children }: {
  householdName: string;
  devices: DisplayDevice[];
  email?: string;
  demo?: boolean;
  canManage?: boolean;
  children?: React.ReactNode;
}) {
  const count = (value: number) => String(value).padStart(2, "0");
  const recent = devices.filter(device => device.presence === "recent").length;
  const attention = devices.length - recent;
  return (
    <div className="shell">
      {!demo && <Refresh />}
      <aside className="sidebar">
        <Brand />
        <div className="workspace"><span className="home-icon" aria-hidden="true">⌂</span><div>{householdName}<small>{devices.length} boîtier{devices.length > 1 ? "s" : ""}{demo ? " d’exemple" : " enregistré" + (devices.length > 1 ? "s" : "")}</small></div></div>
        <nav aria-label="Navigation principale">
          <a className="nav-item active" href="#vue-ensemble"><span aria-hidden="true">▦</span> Vue d’ensemble</a>
          <a className="nav-item" href="#boitiers"><span aria-hidden="true">▣</span> Boîtiers <span className="count">{devices.length}</span></a>
          <a className="nav-item" href="#fonctionnement"><span aria-hidden="true">ⓘ</span> Fonctionnement</a>
        </nav>
        <div className="sidebar-note"><span className="tiny-label">PRENDRE SOIN DU LIEN</span><p>Un regard sur les boîtiers.<br />Un lien avec vos proches.</p><span className="demo-tag">{demo ? "Démonstration" : "Espace privé"}</span></div>
        <footer>CONNECTED WARNER <span>V0.2</span></footer>
      </aside>
      <main id="vue-ensemble">
        <header className="topbar"><span>Logement <span className="slash">/</span> Vue d’ensemble</span>{demo ? <Link className="text-link" href="/login">Se connecter ↗</Link> : <div className="account"><span title={email}>{email}</span><form action={signOut}><SubmitButton className="quiet-button" pendingText="Déconnexion…">Se déconnecter</SubmitButton></form></div>}</header>
        <div className="content">
          <div className="page-heading"><div><span className="eyebrow">LES BOÎTIERS, EN UN COUP D’ŒIL</span><h1>Vue d’ensemble<span>.</span></h1><p>Retrouvez la dernière présence et l’état connu de chaque boîtier.</p></div><span className="house-label">⌂ &nbsp; {householdName}</span></div>
          {demo && <div className="demo-banner"><span className="banner-icon" aria-hidden="true">i</span><div><strong>Vous consultez des données fictives.</strong><p>Aucun boîtier n’est connecté à cet aperçu. Les informations ci-dessous illustrent le futur suivi.</p></div><span className="banner-label">MODE DÉMO</span></div>}
          <section className="metrics" aria-label={demo ? "Résumé de démonstration" : "Résumé des boîtiers"}>
            <article className="metric"><span>Boîtiers enregistrés</span><div>{count(devices.length)} <span className="metric-symbol">▣</span></div><small>{demo ? "Dans ce logement de démonstration" : "Dans votre logement"}</small></article>
            <article className="metric"><span>Présence récente</span><div>{count(recent)} <span className="metric-symbol green-text">●</span></div><small>Un signal reçu depuis moins de 15 min</small></article>
            <article className="metric"><span>À vérifier</span><div>{count(attention)} <span className="metric-symbol amber-text">◷</span></div><small>Signal en retard, absent ou jamais reçu</small></article>
          </section>
          <section id="boitiers" className="devices-section" aria-labelledby="devices-title">
            <div className="section-heading"><h2 id="devices-title">Vos boîtiers <span>{count(devices.length)}</span></h2><span>Signaux de présence prévus toutes les 10 min</span></div>
            {devices.length === 0 && <div className="empty-state"><h3>Votre premier boîtier</h3><p>Enregistrez son nom et son emplacement pour préparer son raccordement.</p></div>}
            <div className="device-grid">{devices.map(device => (
              <article className="device-card" key={device.id}>
                <div className="device-top"><span className="device-icon" aria-hidden="true">▣</span><span className={`status ${device.tone}`}><span className="dot" />{device.presenceLabel}</span></div>
                <h3>{device.name}</h3><p className="device-place">{device.location} <span>·</span> <span title={device.id}>{device.id.slice(0, 8)}</span></p>
                <div className="device-state" data-state={device.stateKind}><span>Dernier état connu</span><strong><span className="state-dot" aria-hidden="true" />{device.state}</strong></div>
                <dl className="device-info"><div><dt>Dernière présence</dt><dd>{device.seenDate ? <time dateTime={device.seenDate}>{device.lastSeen}</time> : device.lastSeen}</dd></div><div><dt>Signal Wi-Fi reçu</dt><dd>{device.wifi}</dd></div></dl>
                <details><summary>Détails du boîtier <span aria-hidden="true">＋</span></summary><dl className="detail-info"><div><dt>Identifiant</dt><dd className="device-id">{device.id}</dd></div><div><dt>Version du programme</dt><dd>{device.version}</dd></div><div><dt>MicroPython</dt><dd>{device.micropython}</dd></div><div><dt>Durée de fonctionnement reçue</dt><dd>{device.uptime}</dd></div><div><dt>Redémarrages observés par le site</dt><dd>{device.reboots}</dd></div></dl><p>{device.note}</p>{device.lastError && <p className="form-error">Dernière erreur reçue : {device.lastError}</p>}{!demo && canManage && <DeviceKey id={device.id} />}</details>
              </article>
            ))}</div>
            {children}
          </section>
          <section id="fonctionnement" className="info-panel" aria-labelledby="info-title"><div className="info-icon" aria-hidden="true">↗</div><div><span className="eyebrow">COMPRENDRE LA PRÉSENCE</span><h2 id="info-title">Un signal reçu, un état daté.</h2><p>Une présence récente indique que le boîtier a pu joindre le site. Elle ne confirme pas le fonctionnement du bouton, du voyant ou de Pushbullet. Après 30 minutes sans signal, l’état actuel est inconnu. Les seuils de 15 et 30 minutes sont provisoires.</p></div></section>
          <div className="page-footer"><span><span className="dot" /> {demo ? "Données de démonstration uniquement" : "Dernières données reçues · Actualisation chaque minute"}</span><span>Connected Warner · Prendre soin du lien.</span></div>
        </div>
      </main>
    </div>
  );
}
