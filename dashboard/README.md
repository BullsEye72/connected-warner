# Dashboard Connected Warner

Application Next.js hébergée sur Vercel, avec connexion Google via Supabase
(OAuth / PKCE) et base PostgreSQL. Chaque compte accède à son propre logement.
Le tableau privé permet de créer le logement et d'enregistrer ses boîtiers.
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

Dans le **SQL Editor** du projet Supabase, exécuter une seule fois le fichier
[supabase/migrations/202610160001_dashboard.sql](supabase/migrations/202610160001_dashboard.sql).
Les migrations suivantes seront des fichiers supplémentaires ; ne pas réexécuter
cette migration initiale sur des tables déjà créées.

Les tables sont :

- `households` : un logement par compte propriétaire ;
- `devices` : noms, emplacements et derniers états reçus ;
- `device_events` : structure préparée pour les futurs événements des cartes.

Les règles RLS empêchent un compte de lire ou modifier le logement d'un autre.
Les clients anonymes n'ont aucun accès aux tables. Un utilisateur peut créer
et renommer ses boîtiers, mais ne peut pas écrire une fausse présence, une
confirmation ou un événement via l'API publique.

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
inscriptions sont autorisées. Chaque nouveau compte obtient un espace vide,
sans accès aux boîtiers existants d'un autre compte. Le partage d'un logement
entre proches n'est pas encore implémenté.

Documentation : [Google avec Supabase](https://supabase.com/docs/guides/auth/social-login/auth-google),
[sessions Next.js](https://supabase.com/docs/guides/auth/server-side/creating-a-client).

## 3. Vérifier après déploiement

Ouvrir `/` : un visiteur est redirigé vers `/login`. Cliquer **Continuer avec
Google**, choisir son compte, puis créer le logement. Enregistrer un boîtier :
il doit afficher **Jamais vu**, sans présence ou état inventés.

Tester la déconnexion et la reconnexion. Avec un second compte, le logement et
les boîtiers du premier ne doivent pas apparaître. `/demo` reste public et
n'affiche que des données fictives.

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

Les tests utilisent PostgreSQL embarqué (PGlite), avec deux comptes fictifs,
pour appliquer la vraie migration et vérifier RLS, les privilèges de colonnes,
l'absence d'accès anonyme et l'impossibilité de fabriquer la télémétrie.
Ils ne touchent pas au projet Supabase distant ni à Google.

## Raccordement des cartes : étape suivante

L'API d'ingestion et le heartbeat toutes les dix minutes ne sont pas encore
implémentés. Aucun jeton d'appareil n'est créé par l'enregistrement d'un boîtier.
Les colonnes de télémétrie et les événements sont réservés à cette future API,
qui authentifiera chaque carte et datera les présences côté serveur.

Le tableau actualise ses lectures chaque minute lorsqu'il est visible. Les
seuils de 15 et 30 minutes restent provisoires, comme dans la spécification.
Une présence ne prouve pas le fonctionnement du bouton, du voyant ou de Pushbullet.
Le suivi reste indépendant des alertes directes Pushbullet. Ne jamais transmettre
le jeton Pushbullet ni le mot de passe Wi-Fi au dashboard.
