const devices = [
  { id: "DEMO-01", name: "Lit", place: "Chambre", presence: "Présence récente", tone: "green", lastSeen: "Il y a 2 min", state: "Au repos", wifi: "−58 dBm", uptime: "2 j 4 h", version: "Démo 0.1", note: "Aucune demande en cours." },
  { id: "DEMO-02", name: "Salle de bains", place: "Salle de bains", presence: "Signal en retard", tone: "amber", lastSeen: "Il y a 22 min", state: "Au repos · dernier état connu", wifi: "−72 dBm", uptime: "1 j 8 h", version: "Démo 0.1", note: "Le dernier état reçu est ancien. L’état actuel est inconnu." },
];

export default function Home() {
  return (
    <div className="shell">
      <aside className="sidebar">
        <a className="brand" href="#"><span className="brand-mark" aria-hidden="true">↗</span><span>connected<span className="brand-sub">warner</span></span></a>
        <div className="workspace"><span className="home-icon" aria-hidden="true">⌂</span><div>Logement de démonstration<small>2 boîtiers d’exemple</small></div></div>
        <nav aria-label="Navigation principale">
          <a className="nav-item active" href="#vue-ensemble"><span aria-hidden="true">▦</span> Vue d’ensemble</a>
          <a className="nav-item" href="#boitiers"><span aria-hidden="true">▣</span> Boîtiers <span className="count">2</span></a>
          <a className="nav-item" href="#fonctionnement"><span aria-hidden="true">ⓘ</span> Fonctionnement</a>
        </nav>
        <div className="sidebar-note"><span className="tiny-label">PREMIÈRE VERSION</span><p>Un regard sur les boîtiers.<br />Un lien avec vos proches.</p><span className="demo-tag">Démonstration</span></div>
        <footer>CONNECTED WARNER <span>V0.1</span></footer>
      </aside>

      <main id="vue-ensemble">
        <header className="topbar"><span>Logement <span className="slash">/</span> Vue d’ensemble</span><span className="preview-pill"><span className="dot" /> Aperçu du dashboard</span></header>
        <div className="content">
          <div className="page-heading"><div><span className="eyebrow">LES BOÎTIERS, EN UN COUP D’ŒIL</span><h1>Vue d’ensemble<span>.</span></h1><p>Retrouvez la dernière présence et l’état connu de chaque boîtier.</p></div><span className="house-label">⌂ &nbsp; Mon logement</span></div>

          <div className="demo-banner"><span className="banner-icon" aria-hidden="true">i</span><div><strong>Vous consultez des données fictives.</strong><p>Aucun boîtier n’est connecté à cet aperçu. Les informations ci-dessous illustrent le futur suivi.</p></div><span className="banner-label">MODE DÉMO</span></div>

          <section className="metrics" aria-label="Résumé de démonstration">
            <article className="metric"><span>Boîtiers enregistrés</span><div>02 <span className="metric-symbol">▣</span></div><small>Dans ce logement de démonstration</small></article>
            <article className="metric"><span>Présence récente</span><div>01 <span className="metric-symbol green-text">●</span></div><small>Un signal reçu depuis moins de 15 min</small></article>
            <article className="metric"><span>Signal en retard</span><div>01 <span className="metric-symbol amber-text">◷</span></div><small>Dernier signal reçu il y a 15 à 30 min</small></article>
          </section>

          <section id="boitiers" className="devices-section" aria-labelledby="devices-title">
            <div className="section-heading"><h2 id="devices-title">Vos boîtiers <span>02</span></h2><span>Signaux de présence prévus toutes les 10 min</span></div>
            <div className="device-grid">{devices.map(device => (
              <article className="device-card" key={device.id}>
                <div className="device-top"><span className="device-icon" aria-hidden="true">{device.id === "DEMO-01" ? "☾" : "≈"}</span><span className={`status ${device.tone}`}><span className="dot" />{device.presence}</span></div>
                <h3>{device.name}</h3><p className="device-place">{device.place} <span>·</span> {device.id}</p>
                <div className="device-state"><span>Dernier état connu</span><strong><span className="state-dot" />{device.state}</strong></div>
                <dl className="device-info"><div><dt>Dernière présence</dt><dd>{device.lastSeen}</dd></div><div><dt>Signal Wi-Fi reçu</dt><dd>{device.wifi}</dd></div></dl>
                <details><summary>Détails du boîtier <span aria-hidden="true">＋</span></summary><dl className="detail-info"><div><dt>Version d’exemple</dt><dd>{device.version}</dd></div><div><dt>Durée de fonctionnement reçue</dt><dd>{device.uptime}</dd></div></dl><p>{device.note}</p></details>
              </article>
            ))}</div>
          </section>

          <section id="fonctionnement" className="info-panel" aria-labelledby="info-title"><div className="info-icon" aria-hidden="true">↗</div><div><span className="eyebrow">COMPRENDRE LA PRÉSENCE</span><h2 id="info-title">Un signal reçu, un état daté.</h2><p>Une présence récente indique que le boîtier a pu joindre le site. Elle ne confirme pas le fonctionnement du bouton, du voyant ou de Pushbullet. Après 30 minutes sans signal, l’état actuel sera affiché comme inconnu.</p></div></section>
          <div className="page-footer"><span><span className="dot" /> Données de démonstration uniquement</span><span>Connected Warner · Prendre soin du lien.</span></div>
        </div>
      </main>
    </div>
  );
}
