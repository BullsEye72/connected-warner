# Dashboard Connected Warner

Application Next.js hébergée sur Vercel, avec connexion Google via Supabase
(OAuth / PKCE) et base PostgreSQL. **Une installation héberge un seul logement**,
partagé avec les comptes autorisés par son administrateur. Chaque personne qui
déploie l'outil utilise son propre projet Vercel et sa propre instance Supabase.
La démonstration publique est conservée sur `/demo`.

## Variables Vercel

Le **Root Directory** reste `dashboard`, le framework `Next.js`, la branche
`main`, Node.js `24.x` et les commandes automatiques.

| Nom | Valeur |
| --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | URL du projet, depuis Supabase > Connect |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Clé publique `sb_publishable_…` |
| `NEXT_PUBLIC_SITE_URL` | `https://connected-warner.vercel.app` |

L'ancien nom `NEXT_PUBLIC_SUPABASE_ANON_KEY` est accepté si la variable
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` est absente. Utiliser la clé `anon`,
pas la clé `service_role`. Redéployer après ajout ou modification des variables
`NEXT_PUBLIC_`, car Next.js peut les figer pendant le build.

Aucune clé privilégiée n'est nécessaire pour cette version. Le préfixe
`NEXT_PUBLIC_` rend une valeur publiable dans le navigateur : ne jamais
l'utiliser pour un secret Google, une clé `sb_secret_`, un mot de passe de base
ou une clé `service_role`. Le code refuse les clés de service à cet emplacement.

## 1. Préparer la base

Dans le **SQL Editor** du projet Supabase, exécuter les migrations une seule fois,
dans l'ordre. Sur une installation existante, appliquer uniquement les fichiers
qui n'ont pas encore été exécutés :

1. [202610160001_dashboard.sql](supabase/migrations/202610160001_dashboard.sql)
2. [202610160002_device_presence.sql](supabase/migrations/202610160002_device_presence.sql)
3. [202610160003_single_household_access.sql](supabase/migrations/202610160003_single_household_access.sql)
4. [202610180004_pushbullet_error.sql](supabase/migrations/202610180004_pushbullet_error.sql)

Les tables sont :

- `households` : le logement unique de cette installation ;
- `devices` : noms, emplacements et derniers états reçus ;
- `device_events` : événements reçus des cartes ;
- `dashboard_members` : comptes, adresses e-mail et décisions d'accès.

Les migrations 002 et 003 conservent le logement, les boîtiers et leurs clés.
La 003 conserve comme administrateur le propriétaire du logement existant.
Sans logement existant, elle retient le plus ancien compte ; sans aucun compte,
le premier inscrit devient administrateur automatiquement. Un verrou de ligne
sérialise les inscriptions pour ne désigner qu'un seul administrateur.
Si plusieurs logements existent déjà, la migration s'arrête sans supprimer de
données : il faut d'abord choisir le logement à conserver.

Les règles RLS bloquent les comptes en attente ou refusés et les clients
anonymes. Les membres approuvés consultent le même logement et ses boîtiers.
Seul l'administrateur configure les boîtiers, génère leurs clés et gère les accès.
Aucun compte humain ne peut fabriquer une présence ou un événement via les tables.

## 2. Activer la connexion Google

Dans **Google Cloud > Google Auth Platform** :

1. Créer ou sélectionner le projet, configurer l'écran de consentement et
   l'audience. Pour les essais en mode Testing, ajouter les comptes Google
   autorisés dans les utilisateurs de test.
2. Créer un client OAuth de type **Web application**.
3. Ajouter l'origine autorisée `https://connected-warner.vercel.app`.
4. Ajouter l'URI de redirection **Supabase** affichée dans le fournisseur Google :
   `https://<identifiant-projet>.supabase.co/auth/v1/callback`.

Dans **Supabase > Authentication > Sign In / Providers > Google** : activer
Google et y renseigner le **Client ID** et le **Client Secret** obtenus.
Ces deux valeurs vont dans Supabase, pas dans les variables Vercel.
Ne pas désactiver la vérification du nonce.

Dans **Supabase > Authentication > URL Configuration** :

- **Site URL** : `https://connected-warner.vercel.app`
- **Redirect URLs** : `https://connected-warner.vercel.app/auth/callback`

Il y a deux retours distincts : Google renvoie vers Supabase (`/auth/v1/callback`),
puis Supabase renvoie vers le dashboard (`/auth/callback`).

La connexion Google peut créer le compte Supabase au premier passage si les
inscriptions sont autorisées. Après le premier administrateur, chaque nouveau
compte entre automatiquement dans la liste d'attente. Laisser les inscriptions
ouvertes pour permettre aux proches de demander leur accès. Les restrictions
Google Testing restent applicables avant cette étape.

Documentation : [Google avec Supabase](https://supabase.com/docs/guides/auth/social-login/auth-google),
[sessions Next.js](https://supabase.com/docs/guides/auth/server-side/creating-a-client).

## 3. Vérifier après déploiement

Ouvrir `/` : un visiteur est redirigé vers `/login`. Cliquer **Continuer avec
Google**, choisir son compte, puis créer le logement. Enregistrer un boîtier :
il doit afficher **Jamais vu**, sans présence ou état inventés.

Tester la déconnexion et la reconnexion. Avec un second compte, seul l'écran
**Demande en attente** doit apparaître. Depuis le premier compte, utiliser
**Accès au logement → Autoriser** : le second compte voit alors le même logement,
sans boutons d'administration. Tester **Refuser**, **Retirer l'accès** et une
nouvelle autorisation. Le retrait bloque les prochaines lectures en base même
avec une session déjà ouverte ; les données déjà affichées ne peuvent pas être
effacées à distance. Le site se rafraîchit chaque minute ou à la reprise du focus.
`/demo` reste public et n'affiche que des données fictives.

## Gérer les accès

Dans le dashboard administrateur, **Accès au logement** liste les adresses
Google en attente, autorisées et refusées. Les membres ne voient que leur propre
statut, jamais la liste des autres comptes. Un refus persiste aux reconnexions.
L'administrateur ne peut pas retirer son propre accès depuis cette interface.

La validation peut aussi se faire dans le SQL Editor Supabase :

```sql
select user_id, email, status from public.dashboard_members order by created_at;

-- Remplacer par l'adresse exacte relevee dans la liste.
update public.dashboard_members
set status = 'approved', updated_at = now()
where email = 'proche@example.com';
-- Utiliser 'rejected' pour refuser ou retirer un acces.
```

Les clients publics ne disposent d'aucun droit d'écriture sur cette table ;
l'interface utilise une fonction SQL qui vérifie l'administrateur. Aucun rôle
n'est déduit de métadonnées Google modifiables par le client. Le compte
administrateur est protégé contre la suppression accidentelle par une référence
en base ; son transfert n'est pas proposé dans cette version.

Sans variables valides, la connexion indique que la préparation est en cours.
Si la migration manque, un utilisateur connecté voit un message d'indisponibilité
de la base au lieu de données fictives présentées comme réelles.

## Développement local et validation

Node.js 22 ou 24 et npm sont nécessaires.

```powershell
cd dashboard
npm ci
Copy-Item .env.example .env.local
# Renseigner l'URL et la clé publique dans .env.local.
# Pour l'essai local, utiliser NEXT_PUBLIC_SITE_URL=http://localhost:3000
npm run dev
```

Ajouter aussi `http://localhost:3000/auth/callback` aux Redirect URLs Supabase
et `http://localhost:3000` aux origines Google pour essayer Google localement.
Aucun secret n'est inclus dans le dépôt ; `.env.local` est ignoré.

```powershell
npm run typecheck
npm test
npm run build
```

Les tests utilisent PostgreSQL embarqué (PGlite), avec plusieurs comptes fictifs,
pour appliquer les quatre vraies migrations et vérifier le premier administrateur,
l'attente, l'approbation, la révocation, RLS, les privilèges de colonnes,
l'absence d'accès anonyme et l'impossibilité de fabriquer la télémétrie.
Ils ne touchent pas au projet Supabase distant ni à Google.

## Raccorder le boîtier existant

1. Exécuter la migration **202610160002_device_presence.sql** dans le SQL Editor
   du même projet Supabase. Aucune nouvelle variable Vercel n'est nécessaire.
2. Dans le dashboard connecté, ouvrir **Détails du boîtier**, puis
   **Créer / remplacer la clé**. Cette action invalide la clé précédente.
3. Copier les quatre lignes affichées dans `carte/configuration_privee.py`.
   La clé ne s'affiche qu'à la création ; seul son SHA-256 est conservé en base.
   Ne pas coller cette clé dans le chat, un ticket ou un fichier suivi par Git.
4. Exécuter `python carte/preparer.py`, transférer `.deploy/` sur la carte avec
   MicroPico, puis redémarrer. Le profil doit utiliser `MODE_RESEAU = "reel"`.
5. Après connexion Wi-Fi et synchronisation de l'horloge, le premier signal part
   après deux secondes de calme. La console affiche `[DASHBOARD] Presence
   transmise (HTTP 200).` Actualiser le site, ou attendre son rafraîchissement.

Le module embarqué envoie un instantané au démarrage, aux changements de demande
et toutes les dix minutes après une transmission réussie. Il privilégie le
dernier état en attente plutôt qu'une file d'événements sans limite : des
transitions très rapides ou hors réseau peuvent ne pas toutes être historisées.
Les alertes directes Pushbullet gardent leur propre fonctionnement.

Le signal utilise `POST /api/devices/<UUID>/heartbeat`, HTTPS et
`Authorization: Bearer <clé>`. Le corps JSON est limité à 2 Kio et n'accepte que
`session`, `sequence`, `state`, `uptime_seconds`, `firmware_version`,
`micropython_version`, `wifi_rssi`, `request_id` et le code facultatif
`pushbullet_error` (`quota_mensuel` ou `null`). Il n'inclut aucun nom de
contact, mot de passe Wi-Fi ou jeton Pushbullet.

L'API appelle une RPC restreinte avec la clé publique Supabase. La RPC vérifie
le secret d'appareil, verrouille son suivi et date la réception côté serveur.
Elle refuse les rapports hors ordre, les sessions de démarrage déjà remplacées
et les rapports espacés de moins de deux secondes. Les doublons retournent
`200 {"accepted":false}` sans rafraîchir la présence. Les codes 401 refusent une
clé absente/invalide, 400 un rapport invalide, 413 un corps trop grand, 429 un
envoi trop rapproché, et 503 un serveur ou une migration indisponible.

Les empreintes et sessions sont dans `warner_private`, inaccessible aux rôles
anonyme et utilisateur. Seul le propriétaire peut remplacer une clé via la RPC
authentifiée `set_device_key`. L'ancienne clé cesse immédiatement de fonctionner.
Le compteur affiché correspond aux redémarrages observés depuis le raccordement,
pas au total de redémarrages physiques de la carte depuis sa fabrication.

Les 27 tests du dashboard appliquent les migrations à PostgreSQL embarqué et
vérifient les accès au logement partagé, la rotation des clés, l'ordre, les doublons,
la validation et les événements. Un parcours HTTP local vérifie aussi la connexion,
l'attente, l'approbation, la consultation sans administration, la révocation et
l'absence d'accès si la migration manque, avec Supabase simulé. Aucun compte ou boîtier réel n'est utilisé
par ces tests. Le 16 octobre, la carte ESP32 réelle transmet sa première présence
avec HTTP 200, après correction de la reconnaissance du code TCP `EINPROGRESS`.

Le tableau actualise ses lectures chaque minute lorsqu'il est visible. Les
seuils de 15 et 30 minutes restent provisoires, comme dans la spécification.
Une présence ne prouve pas le fonctionnement du bouton, du voyant ou de Pushbullet.
Le suivi reste indépendant des alertes directes Pushbullet. Ne jamais transmettre
le jeton Pushbullet ni le mot de passe Wi-Fi au dashboard.

## Quota Pushbullet signalé par la carte (18 octobre)

La version préparée affiche « Quota mensuel Pushbullet atteint » sur la fiche
du boîtier, sans ouvrir ses détails. Le boîtier entre aussi dans « À vérifier »,
même si sa présence est récente. Son état d’aide reste indépendant : une demande
confirmée demeure confirmée lorsque l’accusé échoue pour quota atteint.

La carte transmet seulement le code fixe `quota_mensuel` après un refus explicite
de Pushbullet, jamais le texte de la réponse ni un secret. Le signal part au
prochain créneau de transmission disponible, sans attendre les dix minutes de
présence périodique. Un envoi Pushbullet réellement accepté permet de transmettre
`null` pour lever l’alerte. Une lecture de compte réussie, un redémarrage ou un
ancien firmware sans ce champ ne l’effacent pas. Une nouvelle erreur est
historisée une fois ; les rapports répétés ne dupliquent pas l’événement.

Mise en service, dans cet ordre :

1. Appliquer **202610180004_pushbullet_error.sql** dans le SQL Editor Supabase,
   après les trois migrations précédentes. Elle réutilise `devices.last_error`
   et conserve les appareils, clés, comptes et événements existants.
2. Redéployer le dashboard Vercel avec cette version du code. Aucune variable
   supplémentaire ni nouvelle clé n’est nécessaire.
3. Exécuter `python carte/preparer.py`, transférer `.deploy/` puis redémarrer la
   carte. L’ancienne API refuse ce nouveau champ : le serveur doit être prêt
   avant le transfert de cette version embarquée.

Validation locale : 285 tests MicroPython sur PC, 27 tests du dashboard, contrôle
TypeScript et build de production réussis. Les tests SQL couvrent l’erreur,
l’absence de doublons, la conservation après reboot, l’effacement explicite et
le refus des codes arbitraires. L’utilisateur confirme l’application de la
migration distante le 18 octobre ; la publication du site précède le transfert
de la version embarquée compatible.
