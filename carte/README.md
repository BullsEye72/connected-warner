# Premier essai physique ESP32-S3 N16R8

Carte AYWHP reçue le 14 octobre 2026, identifiée sur COM4 : 16 Mo de flash,
8 Mo de PSRAM. MicroPython 1.29.0, variante `ESP32_GENERIC_S3-SPIRAM_OCT`,
installé et démarrage vérifié. Le port COM de la carte utilise un pont CH343.
Les fichiers embarqués du profil simulé ont été transférés sur cette carte.
La boucle réelle a été exécutée pendant une seconde, puis arrêtée proprement ;
les tests locaux couvrent les voyants, la logique des demandes et le portail Wi-Fi.

La LED RGB intégrée est pilotée comme une NeoPixel sur GPIO48 : l’utilisateur
valide le cycle rouge/vert/bleu rejoué à trois secondes par couleur, puis le bleu
au repos, le 14 octobre 2026. Certaines autres révisions
DevKitC-1 utilisent GPIO38, mais la carte reçue répond bien sur GPIO48.
Le démarrage autonome du programme est vérifié par son diagnostic console :
état REPOS et couleur bleue après une minute de fonctionnement.

## Fichiers et transfert depuis VS Code

Le programme reste dans `wokwi-test/main.py` : la machine à états est commune
au simulateur et à la carte. Le profil physique est séparé de celui de Wokwi.

1. Pour personnaliser les réglages, copier `configuration_exemple.py` en
   `configuration_privee.py` dans ce dossier. Ce fichier privé est ignoré par Git.
2. Depuis la racine du projet, exécuter `python carte/preparer.py`.
   Les dix fichiers nécessaires sont préparés dans `.deploy/`, ignoré par Git,
   dont les modules `contacts.py`, `audio.py`, `journal.py` et `dashboard.py`.
3. Dans MicroPico, sélectionner COM4 puis utiliser le transfert du projet.
   `micropico.syncFolder` vise `.deploy` : les tests et documents restent sur le PC.
   Dans la palette `Ctrl+Shift+P`, choisir `MicroPico: Connect`, puis
   `MicroPico: Upload Project to Board`. Attendre la fin du transfert, puis
   `MicroPico: Restart Board and Show Output` pour lancer le programme et lire
   ses diagnostics. Les extensions `py` et `pem` sont autorisées au transfert.
4. Repréparer `.deploy` après toute modification du programme ou du profil privé.

La connexion automatique de MicroPico est désactivée pour laisser le port libre
aux outils de flash et de diagnostic. Déconnecter MicroPico avant leur utilisation.
Le fichier `carte/test_led.py` permet de rejouer la séquence lente depuis
MicroPico avec la commande d’exécution du fichier courant.

## Configuration Wi-Fi depuis le téléphone

La reconfiguration peut être déclenchée à chaque redémarrage, même avec un Wi-Fi
déjà enregistré, avec le bouton principal raccordé à GPIO12.
Dans le prototype actuel, une demande d’aide en RAM est perdue au redémarrage :
faire cette opération de maintenance hors demande d’aide.

Cette manipulation est destinée au proche chargé de l’installation et de la
maintenance. Le gros bouton accessible sert à l’aide au quotidien et à la
configuration lors de la mise sous tension. Le réseau
enregistré est retrouvé automatiquement au démarrage normal.

1. Couper l’alimentation. Pour un essai USB depuis VS Code, déconnecter MicroPico.
2. Maintenir le bouton principal et remettre sous tension. Garder le bouton
   enfoncé au moins trois secondes pendant le blanc, jusqu’au blanc clignotant,
   puis le relâcher. Un maintien commencé pendant la fenêtre blanche de quatre
   secondes fonctionne aussi.
3. Connecter le téléphone au réseau `Aide-…`. Sa clé WPA2 propre à la carte est
   affichée dans la console sous `[WIFI] Configuration`. Accepter de rester
   connecté à ce réseau même si le téléphone indique une absence d’Internet.
4. Le téléphone peut proposer une fenêtre ou notification « Se connecter au
   réseau », comme sur un Wi-Fi public. Sinon ouvrir **http://192.168.4.1**.
   Renseigner le nom du boîtier (par exemple « Lit »), choisir le Wi-Fi 2,4 GHz
   ou saisir son nom, puis son mot de passe. Le portail teste d’abord la connexion.
   En cas d’échec, **Continuer quand même** permet de préparer un réseau absent :
   le nom du boîtier et le réseau sont rappelés avant l’enregistrement non vérifié.
5. Après réussite, le boîtier redémarre. Bouton principal relâché, il reprend son
   fonctionnement normal et se reconnecte avec les réglages conservés.

### Contacts depuis le portail

La liste accepte jusqu’à huit contacts, avec un nom, l’e-mail du compte Pushbullet
et une case **Contact actif**. Ajouter ou supprimer une ligne avec les boutons
correspondants. Une adresse ne peut figurer qu’une fois et au moins un contact
doit être actif ; désactiver un proche conserve sa fiche sans lui envoyer d’alerte.

- **Vérifier le Wi-Fi et tout enregistrer** : enregistre réseau, nom et contacts
  après le test, ou après confirmation explicite d’une connexion non vérifiée.
- **Enregistrer le nom et les contacts** : conserve le réseau et son mot de passe
  déjà enregistrés, sans refaire le test Wi-Fi ni demander ce mot de passe.

La liste est stockée dans `wifi.json` et prime sur `DESTINATAIRES` du profil privé.
Le profil accepte une liste comme `[{"nom": "Paul", "email": "paul@example.com",
"actif": True}]`. L’ancien `DESTINATAIRE_EMAIL` sert de secours en l’absence de
liste. Le destinataire initial a été conservé lors de la migration, sans ajouter
d’autre compte réel. Les listes restent propres à chaque carte : configurer les
mêmes contacts pour les boîtiers d’un même logement.

Chaque appui transmet la même référence aux contacts actifs. Chacun a son compteur
(cinq acceptations maximum) et son délai de relance, deux minutes après sa propre
dernière acceptation. Un échec pour un proche ne renvoie pas immédiatement aux
autres ; le diagnostic `[CONTACT n]` suit les contacts actifs dans leur ordre.
Un contact refusé avec HTTP 400/404 est suspendu pour cet incident, les autres
continuent. Un refus global du jeton ou de ses droits arrête les envois ; HTTP 429
reporte aussi les destinataires pas encore servis. Les résultats incertains sont
signalés, sans garantie d’absence de doublon après un échec de communication.

Le premier `OK` autorisé après le début de la demande confirme le groupe et arrête
ses relances. `OK CODE` garde la référence de cette demande. Les comptes inconnus
ou inactifs et les anciennes réponses restent ignorés. L’annulation est envoyée
aux contacts qui ont pu recevoir l’aide ; un envoi d’annulation déjà accepté n’est
pas répété pendant le réessai des autres.

Après le premier `OK`, les autres contacts actifs reçoivent une note
`[TEST REPONSE]` : « C’est bon, [nom du contact] a répondu OK », avec le nom du
boîtier et la référence. Le nom vient de la liste configurée. Le répondant ne
reçoit pas cette note. Le vert et l’arrêt des relances sont acquis avant cet
envoi de fond. Une tentative est faite par destinataire ; un échec est journalisé
et ne retire pas la confirmation. La note ne compte pas parmi les cinq alertes.
Les 221 tests locaux couvrent aussi ces annonces, les réponses rejetées, les
contacts inactifs, les erreurs et le maintien de l’ancienne référence si un
nouveau cycle commence.
La version `MP-HTTPS-20261015-REPONSE` est chargée sur la carte. Le diagnostic
avec contacts fictifs valide l’annonce unique aux autres sans modifier le vert
ni les compteurs. Le redémarrage retrouve le compte Pushbullet (HTTP 200) ; COM4
est libéré. Aucun message réel n’est envoyé par ce diagnostic.

Les 215 tests locaux passent. Sur l’ESP32, `carte/verifier_contacts.py` valide avec
des contacts fictifs : sauvegarde/relecture, diffusion, échec partiel, réessai ciblé
et premier OK. La version est transférée. Le redémarrage normal retrouve le Wi-Fi
et vérifie le compte Pushbullet avec HTTP 200 ; COM4 est libéré après le diagnostic.
L’utilisateur confirme l’accès au réseau et le fonctionnement du portail.
L’essai réel de l’annonce de réponse avec deux comptes reste à valider.
La syntaxe du JavaScript généré est vérifiée ; aucun message réel n’a été envoyé
pendant les essais automatisés de cette fonction.

Le geste de configuration n’envoie aucune aide. Si le bouton est encore maintenu
à la sortie du portail, les demandes attendent un relâchement stable, puis un
nouvel appui. Un appui court pendant le blanc n’ouvre pas le portail.

BOOT n’est plus utilisé pour ouvrir la page. GPIO12 n’est pas une broche de
sélection du démarrage sur l’ESP32-S3 ; son maintien ne sélectionne pas le chargeur
ROM. BOOT/GPIO0 conserve cette fonction matérielle : il doit rester relâché à
la mise sous tension et lors d’un RESET. Les problèmes de signaux série pendant
un RESET matériel sont distincts de ce nouveau geste de configuration.
Si le port COM reste occupé après une déconnexion, arrêter l’exécution et
déconnecter MicroPico ; un débranchement/rebranchement USB permet de réinitialiser
le pont série. Ne pas maintenir BOOT pendant le rebranchement.

Le mode installation suspend les demandes d’aide et s’arrête après cinq minutes.
Un redémarrage permet de le quitter plus tôt. Une connexion refusée conserve les
réglages précédents tant que l’on ne confirme pas **Continuer quand même**.
Cette confirmation remplace les anciens réglages même si le réseau est absent ;
le boîtier essaiera ce réseau au prochain démarrage et signalera son absence en
violet. Un échec d’écriture conserve les anciens réglages et ne déclenche pas
de redémarrage. Le formulaire permet de réessayer.
La connexion vérifiée concerne le Wi-Fi et une adresse IP, pas Internet/Pushbullet.

Le nom du boîtier est conservé dans `wifi.json` et chargé dans `PIECE` au démarrage,
donc utilisé dans les notifications AIDE/ANNULATION. Il accepte 1 à 40 caractères
sans caractères de contrôle. Les anciens fichiers sans nom gardent le nom du
profil privé. Le réseau d’installation conserve son identifiant `Aide-…`.
L’enregistrement non vérifié est marqué `connexion_verifiee: false` ; la
confirmation explicite est liée à la dernière tentative échouée. Le mot de passe
n’est pas renvoyé par les diagnostics du portail.

Les 185 tests locaux passent : maintien depuis la mise sous tension, appui bref,
durées discontinues, appui commencé en fin de fenêtre, et absence d’aide avant
relâchement du geste de configuration. Le 15 octobre, l’utilisateur valide sur
carte le maintien du bouton principal à la mise sous tension, le blanc clignotant
et l’accès au portail après relâchement.

Les identifiants sont dans `wifi.json` sur la carte, la clé du réseau d’installation
dans `wifi_installation.json`. Ces fichiers sont ignorés par Git et ne sont jamais
remplacés par le transfert des dix fichiers de programme. Le mot de passe du
Wi-Fi domestique n’est ni réaffiché dans la page, ni journalisé. Le serveur n’écoute
que sur l’adresse du réseau d’installation et ce réseau est éteint en fonctionnement
normal. `PORTAIL_WIFI_ACTIF = False` désactive ce mode et sa fenêtre de démarrage.

La station peut changer le canal radio lors de la connexion à la box. Si le
téléphone perd la page, se reconnecter au réseau `Aide-…` et rouvrir la page.
Le WPS n’est pas implémenté. Le mode simulé peut tester la reconnexion Wi-Fi
avec les réglages enregistrés, tout en gardant les alertes simulées.

Le portail captif répond aux requêtes DNS IPv4 avec l’adresse du boîtier et
redirige les sondes HTTP vers la page locale. Les requêtes DNS IPv6/HTTPS reçoivent
une réponse vide pour permettre le repli IPv4 ; les réponses ne sont pas mises
en cache. Les noms recherchés ne sont pas journalisés. Ce DNS fonctionne seulement
en mode installation et est arrêté à la sortie. La page et le formulaire restent
sur l’adresse locale ; les POST provenant d’un autre Host sont refusés.

La détection dépend du téléphone et de ses réglages : l’utilisateur confirme que
le parcours captif fonctionne sur le sien. La méthode par sondes HTTP
est notamment décrite par [Android](https://developer.android.com/about/versions/11/features/captive-portal).
La saisie directe de l’URL reste disponible. Aucun traitement HTTPS n’est ajouté.

Huit nouveaux tests couvrent le DNS, son arrêt, les sondes Android/iOS/Windows et
HTTP 1.0, soit 169 tests locaux. Sur carte, DNS UDP 53 et redirection HTTP 302
d’une sonde captive sont vérifiés, ainsi que l’accès direct HTTP 200 à la page.

Vérification sur la carte : AP WPA2, GET de la page avec HTTP 200, rejet HTTP 403
d’un POST sans jeton de formulaire, arrêt du réseau après sortie et sauvegarde
atomique avec relecture. La conservation après coupure de courant reste à essayer ;
la validation depuis le téléphone est décrite ci-dessous.
Les 159 tests locaux passent. La version est chargée sur la carte ; le redémarrage
sans BOOT est vérifié par son diagnostic REPOS bleu après la fenêtre de configuration.

Premier essai téléphone : l’utilisateur voit le blanc clignotant et signale
`ERR_CONNECTION_RESET`, avec routeur annoncé à 192.168.4.1. Le test HTTP interne
ne suffit pas à valider ce chemin externe. Le portail affiche maintenant toutes
les quinze secondes son IP, le nombre de stations associées et les compteurs TCP,
HTTP et erreurs, sans identifiants domestiques ni corps de formulaire. Il accepte
huit connexions HTTP simultanées pour tolérer les préconnexions des navigateurs.
Un GET à en-têtes longs a été validé sur carte. Deux nouveaux tests passent
(161 tests locaux au total). Après relance et reconnexion, la carte constate
une station Wi-Fi et quatre requêtes HTTP sans erreur ; l’utilisateur confirme
ensuite que la page s’ouvre sur son téléphone. La cause exacte du premier reset
de connexion n’est pas établie. La console montre ensuite un redémarrage logiciel
après enregistrement, puis « connexion et adresse IP OK » à partir des réglages
relus et un retour au REPOS bleu : la connexion au Wi-Fi saisi et sa reprise après
redémarrage logiciel sont ainsi vérifiées. Les notifications restent simulées.

## Deux voyants avec le même état

Le profil physique active désormais une **respiration bleue de dix secondes**
au repos et une **respiration verte de quatre secondes** après confirmation.
Le vert signifie toujours « aide confirmée » ; l’orange indique la demande en
attente. L’animation montre que la boucle du voyant tourne, sans modifier l’état
ni le délai de retour au bleu après dix minutes. Une intensité minimale reste
visible ; les lectures HTTPS de fond figent la respiration puis elle reprend.

Réglages dans le profil privé, activés par `RESPIRATION_VOYANTS` :

| Réglage | Valeur initiale |
| --- | --- |
| `PERIODE_RESPIRATION_BLEU_MS` | `10_000`, cycle complet |
| `PERIODE_RESPIRATION_VERT_MS` | `4_000`, cycle complet |
| `INTENSITE_BLEU_REPOS` | `64/255` avant réglage de luminosité carte |
| `INTENSITE_VERT_CONFIRME` | `96/255` avant réglage de luminosité carte |

Avec `LUMINOSITE_RGB_CARTE = 32`, la NeoPixel atteint environ `8/255` en bleu et
`12/255` en vert. Ce sont des points de départ à essayer dans une pièce sombre,
pas une adaptation automatique à la lumière ambiante. Les sorties du futur bouton
PWM partagent l’animation ; leur rendu devra être ajusté sur le matériel reçu.
Les signaux orange, rouge, violet, cyan et le blanc de configuration gardent leurs
priorités. Wokwi conserve ses couleurs fixes tant que la respiration n’est pas activée.

Les 215 tests locaux passent, dont les nouveaux cas de préconfiguration, nom
persistant et respiration. La syntaxe JavaScript de la page générée est vérifiée.
`carte/verifier_nouveautes.py` permet de tester sur carte un fichier temporaire
et de montrer deux cycles bleus puis deux cycles verts, sans notification réelle.
Le 15 octobre, l’utilisateur confirme avoir transféré cette mise à jour depuis
`.deploy` et donne un retour positif. Le réglage d’intensité est reporté aux vrais
boutons RGB. L’usage futur de la LED intégrée pour la configuration reste une piste
à reprendre plus tard. L’essai détaillé des nouvelles options du portail reste à
confirmer ; les 215 tests cités ci-dessus sont des tests locaux.

La surveillance du Wi-Fi réel est active sur carte, y compris avec des alertes
simulées :

- **Violet clignotant** : connexion absente, en cours ou non configurée.
- **Bleu avec deux éclats violets toutes les quatre secondes** : signal faible
  au repos. Seuil d’essai −75 dBm, retour normal à −70 dBm, après deux mesures.
- **Bleu** : repos disponible ; en mode réel, le compte Pushbullet doit aussi
  avoir été vérifié. Le violet peut donc signaler une indisponibilité du service
  alors que le Wi-Fi est connecté.

Les états d’une demande active priment sur l’avertissement de signal faible.
La couleur reste fixe pendant les lectures HTTPS de fond. Le maintien d’annulation
reste orange. `SURVEILLANCE_WIFI_REELLE` active ce contrôle ;
`SEUIL_WIFI_FAIBLE_DBM` règle son seuil. Une association Wi-Fi avec adresse IP
ne prouve pas l’accès à Internet.

Les 180 tests locaux passent. L’essai physique vérifie la coupure Wi-Fi, le violet
et la reconnexion (RSSI −54 dBm). Le rendu du signal faible est simulé pendant
huit secondes ; l’affaiblissement réel du signal reste à essayer.

`VoyantRGB` applique la même couleur et le même clignotement aux trois sorties
PWM du bouton et à la LED intégrée, sans réécrire une couleur inchangée.
La luminosité de la LED intégrée est réglable indépendamment, à 32/255 par défaut.

- `GPIO_RGB_CARTE` : GPIO vérifié de la NeoPixel ; `None` la désactive (Wokwi).
- `LUMINOSITE_RGB_CARTE` : entier de 0 à 255.
- `VOYANT_BOUTON_ACTIF` : `False` pour le premier essai sans montage externe ;
  `True` pour activer aussi les PWM rouge/vert/bleu sur GPIO3/8/18 après validation
  du circuit du bouton. La LED intégrée conserve alors le même état.
- AIDE reste sur GPIO12, contact vers GND avec rappel interne à 3,3 V.

Le 14 octobre, l’utilisateur valide l’appui bref sur le poussoir physique du
stock raccordé entre GPIO12 et GND : la demande simulée et son retour visuel
fonctionnent. Il observe ensuite le rouge clignotant, état attendu au plafond
des cinq envois sans confirmation. La demande reste active ; aucune confirmation
fictive n’est injectée automatiquement. L’utilisateur valide ensuite l’annulation
depuis le rouge clignotant : relâchement, nouvel appui maintenu dix secondes,
orange pendant le geste, bref cyan et retour au bleu. La transmission reste
simulée ; cet essai ne valide pas l’envoi d’une annulation réelle à Pushbullet.

Le circuit RGB du bouton métallique nécessite encore la vérification de son
brochage et de ses courants, puis les résistances et transistors prévus dans la
spécification. Il utilise trois sorties PWM, distinctes du signal NeoPixel.

Le profil exemple utilise un réseau simulé, sans jeton et sans notification.
Les entrées V et interrupteurs GPIO13/14 de Wokwi sont désactivées : leur absence
ne simule plus une panne de réseau. Les relances simulées restent à cinq secondes.
Le profil privé active désormais `WATCHDOG_MS = 60_000` : un minuteur matériel
redémarre la carte si la boucle des boutons ne le nourrit plus pendant une minute.
Une tâche réseau terminée empêche aussi son alimentation. Une panne Wi-Fi seule
ne le déclenche pas tant que la boucle tourne. Il est armé après la fenêtre de
configuration du démarrage. Le profil exemple garde `WATCHDOG_MS = 0` pour les
premiers essais ; le profil Wokwi conserve son réglage existant.
Pour déboguer longtemps avec MicroPico, remettre temporairement `WATCHDOG_MS = 0`,
transférer puis faire un RESET matériel : une fois armé, le minuteur continue
après un arrêt du programme. Le montage du voyant RGB externe reste à valider.
Par choix de l’utilisateur le 15 octobre, les demandes restent en RAM : après
coupure ou redémarrage, le boîtier revient au repos et un nouvel appui suffit
pour refaire une demande. Le Wi-Fi et le nom du boîtier restent enregistrés.

Le 16 octobre, l’utilisateur signale un bleu fixe sans réaction au bouton.
La lecture USB ne reçoit aucun diagnostic pendant 35 secondes, ni de réponse à
l’interruption. Un RESET matériel rétablit REPOS, le Wi-Fi et Pushbullet HTTP 200 ;
l’utilisateur confirme le retour du fondu et du bouton. La cause du blocage
reste inconnue. `carte/verifier_watchdog.py` permet de provoquer volontairement
un blocage après armement du minuteur, sans appel Pushbullet dans le diagnostic.
Essai effectué sur l’ESP32 : RESET automatique à 60 secondes, cause WDT reconnue
au démarrage, puis compte Pushbullet vérifié et prêt à 74 secondes. Les deux tests
locaux de surveillance passent. Le réglage de 60 secondes reste actif sur la carte
et COM4 est libéré après l’essai. Ce mécanisme récupère d’un blocage ; il n’en
identifie pas la cause et ne restaure pas une demande conservée seulement en RAM.

## Journal des incidents

Le journal est actif sur la carte, même sans PC. Deux fichiers de 32 Kio maximum,
`diagnostic.jsonl` et `diagnostic.jsonl.1`, gardent les événements récents : cause
du démarrage, état de la demande, changements Wi-Fi, erreurs HTTP, exceptions
non gérées (classe uniquement), pauses de boucle de deux secondes ou plus et
point d’activité toutes les trente minutes. Les erreurs identiques sont limitées
à une par minute. La rotation remplace les événements les plus anciens ; le
nombre obtenu concerne l’historique conservé, pas toute la vie de la carte.

La dernière phase réseau, l’état et le temps de fonctionnement sont aussi mis à
jour dans la mémoire RTC, sans écriture flash à chaque étape. Au démarrage suivant,
ils sont recopiés dans le journal. Cette trace survit aux resets logiciels et
watchdog ; une coupure d’alimentation peut la perdre. Elle indique la dernière
opération connue, pas une preuve de la cause du blocage. Le journal disque, lui,
reste après coupure ; une dernière ligne incomplète est ignorée à la lecture.

Avant la synchronisation NTP, `utc` vaut `null` et le temps est relatif au début
de la session, identifiée par un code aléatoire. Ensuite, les dates sont en UTC.
Aucun SSID, mot de passe, jeton, e-mail ou contenu Pushbullet n’est enregistré.
Le journal reçoit des champs techniques dédiés ; il ne copie pas la console.
Une erreur d’écriture ne doit pas empêcher le fonctionnement du bouton.

Pour exporter, déconnecter MicroPico puis, depuis la racine du projet :

```powershell
& "$env:TEMP\codex-ps2-esp32-tools\Scripts\python.exe" carte/lire_journal.py
```

L’outil utilise `mpremote`, déjà installé dans cet environnement. Il copie les
deux fichiers dans `logs/diagnostic-…/`, affiche le nombre de resets watchdog et
redémarre la carte. Cette lecture interrompt le programme : la faire sans demande
en cours, car le redémarrage efface la demande en RAM. Les journaux embarqués
restent en place et ne sont pas écrasés par `carte/preparer.py` ni le transfert.
Les essais de `verifier_watchdog.py` et les resets après un arrêt manuel identifié
sont comptés à part. Pour relire un export sans toucher à la carte :

```powershell
python carte/lire_journal.py --hors-ligne logs/diagnostic-…
```

Les 258 tests locaux passent, dont rotation, ligne tronquée, erreurs de stockage,
limitation des écritures, champs privés ignorés, contexte RTC et outil d’export.
Vérifié sur l’ESP32 : blocage volontaire, reset watchdog vers 61 secondes,
redémarrage prêt vers 75 secondes, puis export réel des fichiers. La cause WDT
et la phase RTC « blocage volontaire watchdog » sont bien relues sur disque.
Le résumé distingue cet essai des incidents spontanés (zéro dans ce nouvel
historique). Après l’export, la boucle est de nouveau en REPOS avec respiration
bleue ; COM4 est libéré. Le blocage initial est antérieur à ce journal.

## Essai Pushbullet sur carte

Le profil privé contient le jeton et le destinataire saisis localement par
l’utilisateur ; il reste ignoré par Git. Il utilise maintenant `MODE_RESEAU = "reel"`
et `PLATEFORME = "ESP32"`. Le profil exemple reste simulé. Au démarrage,
le Wi-Fi enregistré est relu et le compte Pushbullet est vérifié par HTTPS
avec validation TLS et mise à l’heure NTP : HTTP 200 obtenu sur cette carte.
Le démarrage ne transmet aucune notification.

Un appui bref transmet une notification **TEST**, sans intervention nécessaire.
Les relances sont espacées de deux minutes et plafonnées à cinq envois.
Depuis le compte destinataire, envoyer une note `OK` au compte expéditeur
(vers le PC ou tous les appareils si le compte est le même). Le voyant devient
vert lorsque cette réponse est reconnue. `OK CODE` confirme le cycle indiqué.
L’utilisateur valide la réception de la notification et le voyant vert après
son `OK`. La console confirme le POST HTTP 200, la réponse autorisée et l’état
CONFIRMEE. Un nouvel appui ouvre ensuite un cycle distinct, sans réutiliser
l’ancien `OK`. Une pause de boucle d’environ 750 ms est mesurée lors de la
négociation TLS sur cette carte ; la réactivité lors d’autres conditions réseau
reste à vérifier. L’annulation réelle reste à essayer.

Le 15 octobre, le jeton volontairement modifié est refusé avec HTTP 401 malgré
un Wi-Fi connecté ; l’utilisateur confirme le violet clignotant. Pour reprendre,
restaurer le jeton correct dans le profil privé, repréparer `.deploy`, transférer
le projet puis redémarrer. Le refus d’authentification bloque le transport jusqu’au
redémarrage ; il ne représente pas une panne temporaire avec reprise automatique.

Sources : [NeoPixel MicroPython](https://docs.micropython.org/en/latest/esp32/quickref.html#neopixel-and-apa106-driver),
[DevKitC-1 GPIO48](https://docs.espressif.com/projects/esp-idf/en/v4.4.8/esp32s3/hw-reference/esp32s3/user-guide-devkitc-1.html),
[Wi-Fi MicroPython 1.29](https://docs.micropython.org/en/v1.29.0/library/network.WLAN.html),
[GPIO ESP32-S3 et broches de démarrage](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/peripherals/gpio.html),
[GPIO0 et démarrage ESP32-S3](https://docs.espressif.com/projects/esptool/en/latest/esp32s3/advanced-topics/boot-mode-selection.html).

## Préparation sonore du 16 octobre

`audio.py` fait désormais partie des fichiers préparés pour la carte. La logique
est testée sur PC, sans pilote ADC ni sortie PWM sonore raccordés. Le profil
exemple documente `DETECTION_SONORE_ACTIVE = False` et `BIPS_ACTIFS = False` ;
un ancien profil privé sans ces options reste aussi inactif. Ne pas activer les
drapeaux seuls : des adaptateurs matériels validés restent nécessaires.
Les 246 tests PC passent, dont 25 nouveaux tests sonores ; cela ne valide pas
encore le microphone ou le speaker physiques. Voir les
[essais sans matériel](../wokwi-test/README.md#préparation-sonore-sans-matériel-16-octobre-2026).

## Présence sur le dashboard

Le module `dashboard.py` est inclus dans la préparation MicroPico. Il est
inactif si `DASHBOARD_ACTIF` est absent ou faux : le profil privé existant ne
change pas tout seul. Le [guide du dashboard](../dashboard/README.md#raccorder-le-boîtier-existant)
décrit la deuxième migration SQL et la création de la clé du boîtier.

Copier les quatre lignes affichées lors de la création de clé dans le profil
privé, sans modifier les paramètres Pushbullet ou Wi-Fi, puis repréparer et
transférer les dix fichiers. Aucun nouveau GPIO n'est utilisé. Le suivi n'est
activé qu'en mode réel, après synchronisation de l'horloge pour valider TLS.

Les instantanés comprennent l'identifiant de session aléatoire, une séquence,
le dernier état de demande, la durée de fonctionnement, les versions et le RSSI.
Une annulation reste identifiée comme telle malgré le retour immédiat du voyant
au repos. Le démarrage, un changement et la périodicité de dix minutes déclenchent
un essai après deux secondes de calme. Les changements hors réseau sont regroupés
sur le dernier état ; l'historique du site n'est donc pas un journal exhaustif.

Le DNS utilise des requêtes UDP non bloquantes vers le DNS de la box et un cache
borné à cinq minutes. TCP/TLS utilisent des sockets non bloquants, le nom du site
pour SNI et des certificats obligatoires. Un essai est borné à huit secondes.
Un appui, un maintien, une annulation à transmettre ou une communication
Pushbullet annule l'essai de suivi et ferme son socket. Une panne du site entraîne
un réessai espacé de 15 secondes à cinq minutes. Un refus de configuration/clé
suspend le suivi jusqu'au redémarrage, sans retirer l'état local du bouton.

La console `[DASHBOARD DIAGNOSTIC]` signale les pas TLS d'au moins 50 ms. Les
opérations cryptographiques restent du calcul partagé avec les boutons : les
essais PC ne garantissent pas le temps de réponse sur ESP32. Les essais physiques
restants concernent un appui pendant HTTPS, la priorité de Pushbullet, une coupure
Wi-Fi et le retour après reconnexion. Les certificats
fournis ont été vérifiés depuis le PC pour Vercel, sans clé d'appareil.

Les 17 tests `test_dashboard` couvrent la configuration, le contenu limité, le
DNS, les corps HTTP, la fermeture des sockets à l'annulation, les priorités,
la périodicité, les réessais et le refus de clé. Aucune notification réelle n'est
envoyée par ces tests. La suite PC complète comprend 275 tests réussis.

Le premier essai utilisateur signale des réessais de présence sans détail.
Le diagnostic `MP-20261016-PRESENCE-DIAG` ajoute l'étape `dns`, `tcp`, `tls` ou
`reponse_http`, la classe d'exception et les codes numériques autorisés. Une
réponse serveur indisponible indique son statut, par exemple `HTTP 503`.
La clé, les en-têtes, le corps HTTP et les textes arbitraires d'exception restent
exclus des traces. Les tests de suivi couvrent aussi cette absence de fuite.

Le 16 octobre, le transfert USB du diagnostic révèle `OSError`, code `119`,
à l'étape `tcp`. La liste numérique prévue pour la connexion non bloquante
ne reconnaissait pas `EINPROGRESS` sur cet ESP32. Le module
`MP-20261016-PRESENCE-TCP` utilise les constantes `errno` du port ; voir la
[documentation MicroPython](https://docs.micropython.org/en/v1.29.0/library/errno.html).
Après transfert de ce seul module et redémarrage au repos, la carte transmet
sa présence réelle avec `HTTP 200`. Aucune demande d'aide n'est déclenchée.
Le plus long pas TLS observé pendant cet envoi est de **275 ms** ; cette mesure
ne valide pas encore l'appui pendant HTTPS, la priorité Pushbullet ou la
reconnexion du suivi après une coupure Wi-Fi.
