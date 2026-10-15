# Dashboard Connected Warner

Application Next.js indépendante du programme MicroPython, dans le même dépôt.
Cette première version affiche uniquement deux boîtiers et des états fictifs.
Aucune requête n'est envoyée à une carte ou à Pushbullet.

## Développement local

Node.js 22 ou 24 et npm sont nécessaires.

```powershell
cd dashboard
npm ci
npm run dev
```

Ouvrir http://localhost:3000. `npm run typecheck` vérifie les types et
`npm run build` prépare la version de production.

## Projet Vercel

Importer le dépôt **BullsEye72/connected-warner** avec :

| Réglage | Valeur |
| --- | --- |
| Production Branch | `main` |
| Framework Preset | `Next.js` |
| Root Directory | `dashboard` |
| Node.js Version | `24.x` (ou `22.x`) |
| Install Command | valeur automatique (`npm install` ou `npm ci`) |
| Build Command | valeur automatique (`npm run build`) |
| Output Directory | valeur automatique Next.js |
| Environment Variables | aucune pour cette démonstration |

Le dossier ne dépend d'aucun fichier situé au-dessus de `dashboard/`.
Le déploiement du site ne transfère pas le programme sur les cartes.

## Étapes suivantes

- Ajouter l'authentification privée avant d'afficher des données réelles.
- Choisir une base persistante pour les boîtiers, présences et événements.
- Créer une API HTTPS avec une clé propre à chaque boîtier.
- Envoyer une présence toutes les dix minutes et lors des événements prévus.
- Dater les états côté serveur et afficher explicitement les états anciens.

Les seuils affichés (15 et 30 minutes) restent des propositions de la
spécification, à valider avant le raccordement des cartes. Le suivi web doit
rester indépendant des alertes directes Pushbullet. Ne jamais transmettre
le jeton Pushbullet ni le mot de passe Wi-Fi au dashboard.

Les secrets futurs iront dans les variables d'environnement Vercel et dans
un fichier `.env.local` ignoré pour le développement. Aucune authentification,
base de données ou API de collecte n'est encore implémentée.
