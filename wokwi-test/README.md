# Machine à états Wokwi ESP32-S3 en MicroPython

Le premier test de bouton et de LED a été validé par l’utilisateur le 12 octobre 2026. Il est conservé dans [test_entrees_sorties.py](test_entrees_sorties.py).

Le programme [main.py](main.py) propose deux modes : faux réseau ou essais réels Wi-Fi/Pushbullet. Il conserve AIDE sur GPIO12, l’orange en PWM, la suspension des relances pendant l’annulation, le retour au repos et la relance manuelle après confirmation ou plafond. Deux interrupteurs à glissière commandent les coupures sur GPIO13 et GPIO14. Cent vingt-six tests locaux passent : machine à états, PWM vert → bleu, faux réseau, reconnaissance des réponses et transport réel avec HTTP remplacé par des réponses de test. Le fichier de certificats valide le certificat actuel de l’API Pushbullet depuis le PC. La lecture HTTPS fonctionne sans jeton dans Wokwi (HTTP 401 attendu) ; l’utilisateur a ensuite validé l’aller-retour avec le jeton temporaire ; aucun jeton ni envoi réel n’a été utilisé par l’assistant.

## Cyan fixe pendant les communications

Les traces de l’utilisateur avec `MP-HTTPS-20261012-3` confirment la réutilisation HTTPS sur le POST et les GET, puis le OK autorisé et le passage à CONFIRMEE. Elles mesurent une pause de boucle de 7 679 ms pendant la première négociation TLS et des pauses de 270 à 694 ms pendant le traitement des réponses. Les traces ne permettent pas de répartir précisément ces dernières entre lecture, déchiffrement et traitement JSON.

L’utilisateur a choisi une couleur fixe spécifique avant les communications, puis la reprise des animations à leur fin. `main.py` ajoute le **cyan fixe `(0, 255, 255)`**, prioritaire pendant une communication, sans modifier l’état de la demande. `pushbullet_reel.py` active cet indicateur après acquisition du verrou réseau, laisse vingt millisecondes à la boucle des boutons pour appliquer le PWM avant DNS/TLS, puis le retire dans un `finally`, y compris après erreur, timeout ou annulation. Les lectures des réponses et la vérification du compte sont couvertes, ainsi que les envois. Le mode réseau simulé utilise aussi ce cyan pendant sa latence d’envoi.

Remplacer **deux fichiers** dans Wokwi : `main.py` et `pushbullet_reel.py`. Garder la configuration, les certificats et le montage. Le transport doit afficher `MP-HTTPS-20261012-5` et le programme « Cyan fixe : communication en cours ». Après l’échange, la couleur de l’état reprend : orange clignotant, vert, bleu ou violet si indisponible. Le cyan indique une opération réseau, pas une confirmation de réception ni une prise en charge. Les temporisations de demande restent celles du prototype.

Cinq tests supplémentaires couvrent le cyan fixe, la reprise de l’animation, la préservation de l’état confirmé, le nettoyage après erreur/annulation et le PWM effectivement posé avant un appel bloquant. Les 113 tests locaux passent. La modification est locale et reste à essayer dans Wokwi. Elle traite le rendu du voyant ; une pause TLS peut toujours retarder la lecture des boutons. Le choix d’un autre firmware n’est pas acté et reste une option si les mesures sur carte montrent une réactivité insuffisante.

Après l’ajout du cyan, l’utilisateur indique que le prototype « marche pas trop mal » et demande un commit. Ce retour concerne le simulateur ; la réactivité sur les cartes physiques reste à mesurer.

## Gestes prioritaires sur le réseau (`MP-HTTPS-20261012-5`)

- **Orange du geste prioritaire sur le cyan.** Une lecture des OK démarrée pendant un maintien d’annulation ne remplace plus son orange fixe.
- **Lectures des OK différées sous le doigt.** Aucune nouvelle lecture de fond ne démarre pendant un appui sur AIDE ni dans les deux secondes suivantes ; retard plafonné à vingt secondes si le bouton reste bloqué. Les envois AIDE et ANNULATION ne sont pas différés.
- **Appui bref mémorisé pendant une pause TLS.** Une interruption sur le front descendant d’AIDE mémorise l’appui ; il n’est utilisé que si la boucle a été figée au moins 50 ms et si le bouton est déjà relâché. En boucle normale, l’anti-rebond reste seul juge, ce qui écarte les parasites.
- **Appuis brefs répétés en ATTENTE.** Ils ne repoussent plus les relances : le calendrier n’est décalé que si une relance est réellement tombée pendant le geste.
- **Cyan réservé aux envois AIDE et ANNULATION.** Les lectures des OK et la vérification du compte figent seulement l’animation sur la couleur de l’état (orange, rouge ou violet fixe), sans cyan.
- **Lectures des OK toutes les dix secondes** (`INTERVALLE_LECTURE_MS = 10_000`), au lieu de cinq : deux fois moins de pauses, et toujours sous les trente secondes qui ferment la connexion HTTPS.
- **Backoff après erreur.** La vérification du compte s’espace : 5, 10, 20, 40 puis 60 secondes. Un appui sur AIDE remet le délai à cinq secondes.
- **Watchdog matériel de 60 s** (`WATCHDOG_MS`), nourri par la boucle des boutons tant que la tâche réseau vit. Un redémarrage par watchdog est signalé au démarrage ; la demande en RAM est alors perdue, faute de persistance. Le watchdog ne peut pas être arrêté : après Ctrl-C, la carte redémarre au bout de 60 s ; mettre `WATCHDOG_MS = 0` pour déboguer.

Treize tests supplémentaires, soit 126 au total. Remplacer `main.py` et `pushbullet_reel.py`, et changer à la main `INTERVALLE_LECTURE_MS = 10_000` dans le `configuration.py` de Wokwi (il contient le jeton). À vérifier dans Wokwi : le transport affiche `MP-HTTPS-20261012-5`, un appui bref pendant « Pause de la boucle » est pris en compte, le maintien de dix secondes reste orange, et l’attente ne passe plus au cyan toutes les dix secondes. Le fonctionnement du watchdog dans le simulateur reste à confirmer.

## Essai avec le vrai Wi-Fi et Pushbullet

L’utilisateur a accepté d’utiliser un jeton temporaire dans Wokwi et de le révoquer après les essais. Le prototype réel vise un seul destinataire, l’utilisateur, avec des messages explicitement marqués TEST. Le composant payant « WiFi Access Point » n’est pas nécessaire : utiliser le réseau gratuit Wokwi-GUEST. Sources : [réseau Wokwi](https://docs.wokwi.com/guides/esp32-wifi), [API Pushbullet](https://docs.pushbullet.com/).

1. Dans le projet Wokwi MicroPython ESP32-S3, remplacer `main.py` par [main.py](main.py). Garder le [diagram.json](diagram.json) à deux boutons et deux interrupteurs déjà utilisé.
2. Ajouter trois fichiers au projet avec leurs noms exacts : [configuration.py](configuration.py), [pushbullet_reel.py](pushbullet_reel.py) et [certificats.py](certificats.py). Copier le contenu de chacun ; les certificats sont publics, pas secrets. L’ancien [ca.pem](ca.pem) reste utilisable : le transport le lit s’il est présent, sinon importe `certificats.py`. Wokwi copie les fichiers du projet dans son système de fichiers MicroPython ([documentation](https://docs.wokwi.com/guides/micropython)).
3. Dans `configuration.py`, garder `MODE_RESEAU = "reel"` et renseigner `JETON_PUSHBULLET` et `DESTINATAIRE_EMAIL` avec le jeton temporaire et l’adresse du compte qui recevra le test. `PIECE = "Lit"` peut être adapté. Le jeton fourni dans le workspace est vide.
4. Mettre les deux interrupteurs sur ON à droite et lancer. Attendre les messages « Horloge reglee ; verification TLS active » puis « Compte Pushbullet verifie ; pret pour AIDE ». Le violet pendant cette préparation est normal.
5. Appuyer brièvement sur AIDE : recevoir **[TEST AIDE] Lit (Wokwi)**. L’acceptation de l’API augmente le compteur et passe à l’orange clignotant. Les relances réelles sont réglées à deux minutes, maximum cinq envois par cycle. On peut changer leur durée dans la configuration, avec un minimum de dix secondes pour les essais.
6. Répondre **OK** dans Pushbullet au compte expéditeur, ou **OK CODE** avec la référence contenue dans le message. Le programme vérifie les réponses toutes les cinq secondes tant que la demande est en attente. Si le destinataire est le même compte que l’expéditeur, envoyer une note « OK » vers tous les appareils du compte ou vers le PC, comme dans le prototype HTML. Le voyant passe au vert après reconnaissance d’une réponse autorisée. **V ne fabrique pas de OK en mode réel** ; il garde uniquement la remise au repos d’essai après confirmation.
7. Tester les interrupteurs et l’annulation de dix secondes. Wi-Fi OFF désactive réellement l’interface. Pushbullet OFF suspend les nouvelles requêtes vers le service ; il ne coupe pas le service pour les autres utilisateurs. Un envoi déjà engagé peut avoir abouti. Les annulations en attente ont priorité au rétablissement, puis retour au bleu.
8. Révoquer le jeton temporaire après les essais. Pour retrouver le faux réseau, régler `MODE_RESEAU = "simule"` ; sans fichier de configuration, `main.py` utilise aussi le mode simulé.

Le transport utilise des tâches asyncio, un délai HTTP de douze secondes, une horloge NTP et TLS avec vérification du nom d’hôte et du certificat. `ca.pem` et `certificats.py` contiennent quatorze certificats racines publics et le certificat d’émetteur YE1 actuel de Pushbullet, récupéré depuis sa chaîne TLS vérifiée sur le PC le 12 octobre 2026. L’ajout de cet émetteur comme autorité de confiance permet la validation dans Wokwi ; CERT_REQUIRED et la vérification du nom d’hôte restent actifs. YE1 expire le 2 septembre 2028 ; revoir les certificats si la chaîne du service change. Sources : [asyncio MicroPython](https://docs.micropython.org/en/latest/library/asyncio.html), [TLS MicroPython](https://docs.micropython.org/en/latest/library/ssl.html).

L’utilisateur a signalé `OSError: [Errno 2] ENOENT` à l’ancienne ligne 249, lors du chargement de `ca.pem` : ce fichier n’était pas accessible sous le nom configuré. Le transport dispose désormais d’un chargement de secours par `certificats.py`, avec les mêmes certificats, et d’un message explicite si les deux sources manquent. Trois tests vérifient les deux sources et le diagnostic d’absence.

L’essai suivant passait Wi-Fi et horloge, mais expirait pendant HTTPS. Le problème a été reproduit sans jeton dans le [projet public de l’utilisateur](https://wokwi.com/projects/477628209895659521), autorisé pour édition : le blocage survenait durant la négociation TLS, avant toute réponse HTTP. Un délai de trente secondes et une seule racine ne suffisaient pas ; l’ajout du certificat d’émetteur YE1 vérifié a permis un GET complet vers `users/me`, réponse HTTP 401 attendue sans jeton, en environ neuf secondes après début de connexion. Le test de TLS utilisait une date RTC valide connue afin d’isoler cette étape d’une réponse NTP momentanément absente dans le simulateur ; cette date fixe n’a pas été conservée dans le programme livré. La cause exacte dans le moteur TLS de Wokwi n’est pas établie.

Une [copie corrigée sans jeton](https://wokwi.com/projects/477633946468936705), intitulée « connected-warner - HTTPS corrige », a été enregistrée, car l’interface ne permettait pas de remplacer le projet d’origine depuis cette session. Le programme des boutons et le diagramme de l’utilisateur ont été rétablis ; aucun jeton ni POST de notification n’a été utilisé. Le client ajoute des traces `[HTTPS]` par étape et précise l’étape lors d’un délai dépassé, sans afficher les en-têtes ni le contenu privé. Les certificats corrigés et les diagnostics sont aussi enregistrés dans le workspace. Cent treize tests locaux passent. L’utilisateur a depuis validé l’identification du compte (HTTP 200) puis la réponse OK autorisée et le passage à CONFIRMEE.

Les erreurs HTTP 400/401/403/404 bloquent les envois jusqu’à correction de la configuration et relancement. Une erreur 429 déclenche une pause suivant Retry-After, avec un minimum de trente secondes. Les erreurs de transport ne comptent pas comme acceptations ; elles peuvent avoir un résultat incertain et un réessai peut créer un doublon. La confirmation reste fondée sur le compte autorisé, la date serveur du premier message, la référence du cycle et les réponses déjà consommées. Le jeton et le contenu privé des réponses ne sont pas imprimés dans les logs.

Limites du mode réel : un seul boîtier et un seul destinataire, état en RAM, pas de dashboard ni OTA. Les opérations réseau sont asynchrones, mais la résolution DNS de MicroPython reste bloquante ; la réactivité lors de ces phases est à mesurer dans Wokwi puis sur le matériel. Les résultats incertains sont signalés, sans déduplication garantie. Ce programme reste un prototype d’essai.

### Pauses du voyant pendant les communications

Après validation de l’aller-retour Pushbullet par l’utilisateur (compte vérifié avec HTTP 200, puis OK distant autorisé et état CONFIRMEE), celui-ci signale que l’animation du voyant se fige pendant les échanges. Le client initial ouvrait une connexion TLS pour chaque requête et comptait les cinq secondes de lecture depuis le début de la requête ; une lecture lente pouvait donc provoquer une nouvelle lecture immédiatement après sa fin.

`pushbullet_reel.py` conserve maintenant la connexion HTTPS lorsque le serveur le permet. Les réponses sont intégralement consommées, y compris les trailers des réponses chunked, avant toute réutilisation. La connexion est abandonnée après une erreur, une annulation, une demande de fermeture du serveur, une réponse sans longueur connue, un changement de Wi-Fi ou trente secondes d’inactivité. Aucun POST n’est automatiquement répété par ce transport. Le cache DNS dure cinq minutes ; le nom `api.pushbullet.com` est conservé pour SNI et la vérification TLS. L’intervalle entre lectures commence désormais à la fin de chaque lecture, y compris en cas d’échec.

Une surveillance signale `[DIAGNOSTIC] Pause de la boucle : ... ms` si la boucle asyncio n’a pas tourné pendant au moins 250 ms. Cela aide à vérifier la réactivité dans le simulateur. La première connexion, une reconnexion et les calculs TLS peuvent encore provoquer une pause : cette modification évite les négociations répétées, sans garantir une latence maximale des boutons. Les sources MicroPython montrent que la résolution DNS est bloquante et que le traitement TLS s’effectue dans les appels de lecture/écriture ([asyncio](https://docs.micropython.org/en/latest/library/asyncio.html), [implémentation TLS v1.28.0](https://github.com/micropython/micropython/blob/v1.28.0/extmod/modtls_mbedtls.c)).

Treize tests supplémentaires couvrent la réutilisation, le cadrage des réponses successives, la fermeture, l’annulation, le cache DNS avec conservation du nom TLS, les lectures lentes et les diagnostics ; 93 tests passent. Deux GET sans jeton vers l’API réelle depuis le PC ont confirmé la réutilisation (HTTP 401 attendu, deuxième requête sur la même connexion, également vérifiée après une attente de 5,1 secondes). Le test PC a utilisé le certificat d’émetteur comme autorité de confiance avec `VERIFY_X509_PARTIAL_CHAIN`, en conservant la validation TLS et du nom d’hôte ; aucune notification n’a été envoyée. L’essai dans Wokwi reste à faire en remplaçant uniquement `pushbullet_reel.py`, sans changer le jeton, les certificats ou le montage. Cette dernière version est locale, elle n’a pas été appliquée au projet en ligne.

L’utilisateur signale encore une longue pause à « envoi HTTPS et negociation TLS ». Le comportement n’est donc pas corrigé dans Wokwi. Le [plan de réactivité](../REACTIVITE-RESEAU.md) décrit les limites de cette approche et l’option de tâches réseau et commandes distinctes en C++/FreeRTOS, proposée pour choix. Aucun portage n’a encore été entrepris.

### Réutilisation absente : diagnostic à relever

L’utilisateur a fourni la documentation uasyncio v1.14 et des traces montrant une nouvelle ouverture TCP/TLS à chaque GET, sans réutilisation visible. Le prototype utilise déjà asyncio/uasyncio. Avant de modifier son architecture, vérifier pourquoi la liaison n’est pas conservée ; l’hypothèse d’un changement de langage nécessaire n’est pas démontrée par ces seules traces.

Au lancement, le dernier fichier affiche `[REEL] Transport MP-HTTPS-20261012-2`. Après la réponse HTTP, il affiche les indicateurs `fermeture`, `longueur` et `blocs`, puis soit la conservation de connexion, soit le motif de fermeture. Si l’appel synchrone `Stream.write()` prend au moins 250 ms, il affiche `[DIAGNOSTIC] Appel TLS write sans await : ... ms`. Ces diagnostics excluent le jeton, les valeurs d’en-têtes privés et les paramètres d’URL. Deux tests supplémentaires passent, soit 95 tests au total. Remplacer seulement `pushbullet_reel.py`, arrêter puis relancer, et relever la version, la fin de réponse, la fermeture éventuelle et les pauses mesurées. Cette dernière modification est locale et n’a pas encore été testée dans Wokwi.

### OK non reconnu : dates et identité du destinataire

L’utilisateur signale un OK ignoré alors que les GET retournent HTTP 200. Ses logs contiennent encore « Connexion/lecture indisponible (OSError) », format de l’ancien fichier, et ne contiennent aucun nouveau diagnostic de version/conservation de connexion. Ces traces ne permettent pas d’attribuer le rejet à une cause particulière.

Un défaut indépendant a été identifié et reproduit : MicroPython ESP32 utilise des flottants 32 bits, qui ne représentent pas précisément les horodatages Unix actuels. Une date d’alerte arrondie vers le futur peut décaler le filtre `modified_after` et masquer des réponses récentes. Le décodeur HTTP préserve maintenant les nombres JSON `created` et `modified` sous forme de texte avant `json.loads`; le suivi les convertit en millisecondes entières. Le filtre de lecture est envoyé en secondes entières avec une seconde de recouvrement ; la date exacte de création continue de rejeter les réponses antérieures à l’alerte. Le corps des messages n’est pas modifié. Sources : [flottants ESP32 MicroPython v1.28.0](https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/mpconfigport.h), [dates et champs des réponses Pushbullet](https://docs.pushbullet.com/).

Le destinataire effectif est désormais identifié par `receiver_iden` dans la réponse TLS vérifiée du POST envoyé à l’adresse configurée. Les réponses sont filtrées par l’identifiant de leur expéditeur lorsqu’il est connu ; cela évite les ambiguïtés d’alias et d’adresses normalisées. Sans cet identifiant, le filtre compare l’adresse originale et l’adresse normalisée, au lieu d’ignorer l’originale dès qu’une normalisée existe. Les réponses provenant d’un autre compte, adressées ailleurs, antérieures au cycle ou déjà utilisées restent rejetées.

La version locale est `MP-HTTPS-20261012-3`. Quand une page ne contient pas de OK accepté, elle affiche `[OK] Lecture : ... messages ; ... textes OK ; rejets=...`, sans adresse, identifiant de compte, jeton ou contenu privé. Treize tests supplémentaires couvrent dates exactes, notation scientifique, JSON avec échappements, arrondi float32 vers le futur, alias, identités et diagnostics confidentiels. Les 108 tests passent. Remplacer uniquement `pushbullet_reel.py` dans Wokwi, arrêter puis relancer, vérifier le marqueur de version, créer une nouvelle demande TEST et envoyer un nouveau OK. Ces corrections sont locales ; elles n’ont pas encore été validées dans Wokwi. Le gel TLS reste une question distincte à résoudre.

### Diagnostic OSError après ouverture TLS

L’utilisateur signale désormais un échec après « envoi HTTPS et negociation TLS ». Le type `OSError` seul ne permet pas d’identifier la cause. Le transport local affiche maintenant les codes numériques de l’exception et certains marqueurs TLS connus, ainsi que l’étape de la requête, sans recopier les arguments arbitraires ni le jeton. Il affiche aussi la date UTC après synchronisation NTP. Une erreur de fermeture du flux ne masque plus l’erreur initiale. Quatre tests supplémentaires portent sur ces diagnostics et sur la conservation de l’erreur initiale ; quatre-vingts tests passent au total.

Cette modification est disponible dans `pushbullet_reel.py` du workspace, mais n’a pas été appliquée à la copie Wokwi : l’inspection du navigateur a été refusée parce que la vérification automatique d’autorisation ne pouvait pas aboutir, du fait d’une limite d’utilisation. Remplacer uniquement le contenu de `pushbullet_reel.py` dans Wokwi, garder la configuration et les certificats, arrêter puis relancer. Relever « Horloge UTC » et la première ligne complète « Connexion HTTPS indisponible ». Le problème réseau reste à diagnostiquer ; aucun nouvel essai en ligne n’a été réalisé pour cette modification.

## Retour vert → repos bleu et diagnostic

L’utilisateur a signalé une extinction après environ dix minutes de vert, sans message « Etat : REPOS » ni erreur. Cette absence de transition ne permet pas d’attribuer l’extinction au changement d’état prévu. `VoyantRGB` centralise maintenant la commande des trois couleurs et n’écrit le PWM que lorsque la couleur change. Deux tests vérifient la commande effective bleu = `(0, 0, 65535)` après le vert et l’absence de réécriture inutile du PWM.

Toutes les trente secondes de temps simulé, la console affiche `[DIAGNOSTIC] boucle active`, l’état, la couleur RGB demandée et le compteur de temps. Si le programme se termine dans la boucle, il affiche `[DIAGNOSTIC] Programme arrete : voyant eteint`. Au retour normal après confirmation, la console doit afficher `Etat : REPOS`. Si le voyant s’éteint, vérifier si ces diagnostics continuent et si l’état est REPOS ou encore CONFIRMEE ; le rendu Wokwi de cette modification reste à vérifier.

## Montage actuel

- ESP32-S3, projet MicroPython Wokwi.
- LED RGB configurée en **cathode commune**, patte commune vers GND.
- Rouge : GPIO3, vert : GPIO8, bleu : GPIO18 ; une résistance de 330 ohms par couleur.
- Bouton AIDE : **GPIO12**, choisi par l’utilisateur, vers un contact du groupe 1, GND vers un contact du groupe 2. Exemple : `1.l` et `2.l`. Le premier test conservé utilise encore GPIO39.
- Bouton supplémentaire de validation simulée : GPIO40 vers un contact du groupe 1, GND vers un contact du groupe 2.
- Interrupteur Wi-Fi : **GPIO13 vers la borne centrale 2**, GND vers la borne droite 3 ; borne gauche 1 non connectée.
- Interrupteur Pushbullet : **GPIO14 vers la borne centrale 2**, GND vers la borne droite 3 ; borne gauche 1 non connectée.

Les deux interrupteurs sont sur **ON à droite** au démarrage (`value: "1"`). À droite, la borne centrale rejoint GND et le programme lit « disponible ». À gauche, le rappel interne PULL_UP donne « indisponible ». Le programme suit la position stable, avec anti-rebond de 30 ms, sans basculer à chaque boucle. Voir la [référence Wokwi des interrupteurs](https://docs.wokwi.com/parts/wokwi-slide-switch).

Les bornes `1.l` et `1.r` sont toujours reliées ; les bornes `2.l` et `2.r` aussi. L’appui relie les deux groupes. Le premier montage utilisait deux bornes d’un même groupe, ce qui maintenait l’entrée à la masse ; le déplacement d’un fil a résolu le problème.

## Utilisation

Ouvrir le [modèle ESP32-S3 MicroPython](https://wokwi.com/projects/new/micropython-esp32-s3), copier le contenu de [main.py](main.py) dans l’onglet `main.py` et remplacer `diagram.json` par le [diagram.json](diagram.json) fourni pour installer le montage à deux boutons et deux interrupteurs. Pour conserver son propre montage, remplacer seulement les commandes GPIO13 et GPIO14 par des interrupteurs câblés comme indiqué plus haut. Lancer la simulation avec le bouton de lecture.

Le schéma fourni définit **A** pour maintenir AIDE et **V** pour la réponse du proche. Cliquer sur les interrupteurs pour changer leur position : **gauche = OFF / panne**, **droite = ON / disponible**. Les anciennes touches W et P ne sont plus utilisées. Cliquer dans le diagramme pour lui donner le focus avant d’utiliser A et V. Pour un maintien avec la souris, Wokwi propose également Ctrl-clic pour garder un bouton appuyé, puis un clic pour le relâcher.

## Faux Wi-Fi et faux Pushbullet

La suite de cette section et les scénarios ci-dessous concernent `MODE_RESEAU = "simule"`.

Les deux interrupteurs fournis sont sur ON au démarrage. Si l’un est réglé sur OFF avant le lancement, sa position est prise en compte dès la première boucle, avant toute tentative d’aide. Un envoi simule 750 ms de délai sans bloquer la lecture des entrées. Le compteur 1/5, 2/5, etc. compte uniquement les alertes acceptées par le faux Pushbullet, pas les tentatives ni les annulations. Cette acceptation ne vaut pas confirmation d’un proche.

- Sans Wi-Fi ou sans Pushbullet, la demande reste en mémoire et le compteur n’avance pas. Au rétablissement des deux, la transmission reprend : premier envoi si aucun n’a été accepté, ou prochaine relance si son intervalle est écoulé. Pas de rafale de rattrapage.
- Une coupure pendant une requête produit un échec simulé sans augmenter le compteur. L’intervalle de réessai est de deux secondes, distinct de celui des relances ; un retour de disponibilité autorise une reprise immédiate.
- V ne peut simuler un OK que si une alerte de la demande a déjà été acceptée. Avec Pushbullet disponible mais le Wi-Fi du boîtier coupé, le faux proche peut répondre : le OK est conservé côté faux service et le boîtier ne passe au vert qu’à la reconnexion. Si Pushbullet est en panne, V n’enregistre aucune réponse ; réappuyer après rétablissement.
- Les OK portent l’identifiant de la demande. Une réponse ancienne ou déjà consommée est ignorée. À la reconnexion, lire les réponses disponibles avant de lancer une relance devenue due.
- Après annulation, arrêter les alertes et conserver le message d’annulation à transmettre si une tentative d’aide a déjà eu lieu. Le transmettre à la reconnexion ; une annulation en attente a priorité sur une nouvelle aide. Sans aucune tentative d’aide antérieure, l’annulation reste locale et aucune ancienne aide n’est envoyée ensuite.

Un **violet clignotant** signale une indisponibilité Wi-Fi/Pushbullet, une première alerte pas encore acceptée ou une annulation à transmettre. Le geste d’annulation garde priorité et affiche l’orange fixe. Après annulation, la machine revient au REPOS immédiatement ; le voyant reste violet tant que la transmission de l’annulation est en attente, puis revient au bleu lorsque le réseau est disponible. Le violet peut aussi masquer le vert d’une demande déjà confirmée si le réseau tombe ; sa confirmation reste conservée.

Limites du modèle : pas de connexion Wi-Fi réelle, HTTP, authentification, multi-destinataires ni synchronisation de boîtiers. Les requêtes simulées ont un résultat certain ; une aide en cours peut être interrompue avant son acceptation simulée lors d’une annulation. Sur le réseau réel, une requête interrompue peut avoir abouti : la gestion de cette incertitude reste à implémenter. Toutes les files et demandes sont en RAM ; un redémarrage les perd.

## États et commandes

| État | Voyant | Comportement |
| --- | --- | --- |
| REPOS | Bleu fixe | Appui sur AIDE : nouvelle demande et première tentative immédiate si le réseau est disponible |
| ATTENTE | Orange clignotant | La demande reste active après relâchement ; relances jusqu’au plafond ; VALIDATION simule un OK |
| SANS_CONFIRMATION | Rouge clignotant rapidement | Cinq notifications déjà simulées ; confirmation tardive acceptée ; appui bref AIDE : nouveau cycle au relâchement ; maintien dix secondes : annulation |
| CONFIRMEE | Vert fixe | Appui bref AIDE : nouveau cycle au relâchement ; maintien dix secondes : annulation ; retour au repos dix minutes après confirmation, ou par VALIDATION pour accélérer l’essai |
| ANNULEE (transition) | Violet pendant la transmission, puis bleu | Relances arrêtées, message « Tout compte fait, tout va bien » simulé une seule fois ; passage immédiat au REPOS, annulation à transmettre si nécessaire |

Un maintien d’annulation affiche de l’orange fixe et suspend les nouvelles relances dès son début. Un envoi déjà commencé peut encore terminer pendant le geste. Après dix secondes continues, la demande est annulée puis le boîtier revient immédiatement au REPOS, avec l’éventuel message d’annulation à transmettre décrit plus haut. Le résultat précédent reste dans le journal et dans `dernier_resultat`, en RAM. Si le geste a commencé en ATTENTE, relâcher plus tôt laisse la demande active. Si une relance est tombée pendant le geste, elle attend un intervalle complet depuis ce relâchement, sans rattrapage ; sinon le calendrier est inchangé, pour que des appuis répétés ne retardent jamais les relances.

Si le geste a commencé en CONFIRMEE ou SANS_CONFIRMATION, relâcher avant dix secondes crée une nouvelle demande avec un nouvel identifiant : première tentative au relâchement si le réseau est disponible, compteur à 1/5 après acceptation, puis orange clignotant et nouveau calendrier de relances. Attendre le relâchement distingue la relance de l’annulation ; un maintien de dix secondes n’envoie donc aucune nouvelle alerte. L’ancienne demande est remplacée dans la machine, et le journal conserve la trace du cycle précédent. Une confirmation reçue pendant un geste commencé en ATTENTE ne transforme pas ce geste en relance. Un OK simultané au relâchement ne confirme pas le nouveau cycle.

Le premier appui qui crée une demande envoie l’aide immédiatement et ne peut pas l’annuler par son seul maintien : il faut le relâcher puis maintenir à nouveau. Les relances continuent pendant ce premier appui. Le maintien prolongé après annulation ne déclenche ni autre message d’annulation ni nouvelle demande : relâcher puis appuyer de nouveau pour créer la demande suivante.

Les couleurs sont des intensités RGB de 0 à 255. `ORANGE = (255, 80, 0)` combine rouge à pleine intensité et vert atténué avec trois sorties PWM à 1 kHz. La valeur de vert peut être ajustée selon le rendu. Sources : [PWM MicroPython](https://docs.micropython.org/en/latest/library/machine.PWM.html), [LED RGB Wokwi](https://docs.wokwi.com/parts/wokwi-rgb-led).

Dans ce test, un second appui sur VALIDATION après confirmation permet de revenir au repos sans attendre dix minutes. Cette commande de reprise n’est pas un bouton supplémentaire prévu chez le père. AIDE permet désormais de relancer directement depuis CONFIRMEE. Le retour automatique attend le relâchement d’AIDE si un geste est en cours à l’échéance.

## Temporisations

- Anti-rebond : 30 ms sur les boutons et les interrupteurs.
- Annulation : **10 secondes** réelles de temps simulé.
- Retour automatique au repos : **10 minutes après confirmation**, réglage `RETOUR_REPOS_MS = 600_000`. Pour un essai rapide, le réduire temporairement à `30_000`. Après annulation, retour immédiat au REPOS, puis bleu après transmission et si le réseau est disponible. Une demande sans confirmation ne revient jamais automatiquement au repos.
- Latence simulée : **750 ms** par envoi, réglage `LATENCE_RESEAU_MS`.
- Réessai après échec : **2 secondes**, réglage `INTERVALLE_REESSAI_MS`.
- Relances : **5 secondes après acceptation du précédent envoi**, uniquement pour accélérer les essais ; cinq envois acceptés au maximum par cycle. Le délai de transmission s’ajoute à cet intervalle.
- La cible de la spec reste deux minutes : régler `INTERVALLE_RELANCE_MS` à `120_000` pour l’essayer avec les durées prévues. Les temporisations reposent sur le temps du simulateur, qui peut différer du temps réel du navigateur.

Le mode simulé ne transmet aucune alerte et n’utilise aucun jeton. Il ne traite qu’une demande d’un boîtier et ne simule pas la synchronisation entre plusieurs appareils. L’état reste en RAM : arrêter puis relancer la simulation repart au repos. Les mesures et le câblage du matériel réel restent à valider séparément.

## Scénarios d’essai

1. Appuyer brièvement sur AIDE : premier message simulé et orange clignotant qui reste après relâchement.
2. Appuyer sur VALIDATION : vert fixe et arrêt des relances. Relâcher puis appuyer de nouveau sur VALIDATION pour revenir au repos.
3. Créer une demande et attendre cinq envois : clignotement rouge accéléré, puis vérifier qu’une validation tardive passe toujours au vert.
4. Créer une demande, relâcher, puis maintenir AIDE dix secondes : orange fixe pendant le geste sans nouvelles relances, ensuite violet pendant l’envoi de l’annulation puis bleu. Continuer de maintenir : aucune nouvelle demande.
5. En ATTENTE, relâcher le maintien avant dix secondes : la demande reste en cours ; prochaine relance cinq secondes après le relâchement avec le réglage de test.
6. Maintenir le premier appui plus de dix secondes : la demande reste active, sans annulation automatique.
7. Confirmer puis maintenir AIDE dix secondes : la demande confirmée peut être annulée.
8. Confirmer puis attendre dix minutes : retour au bleu sans reset ; un nouvel appui crée une nouvelle demande. Refaire le même essai sans confirmation : aucun retour automatique au repos.
9. Depuis le vert ou le rouge clignotant rapidement, appuyer brièvement sur AIDE : nouveau cycle au relâchement, notification 1/5 et orange clignotant. Attendre les quatre autres envois ou confirmer ce nouveau cycle.
10. Depuis le vert ou le rouge clignotant rapidement, maintenir AIDE dix secondes : annulation de la demande précédente, sans nouvel envoi d’aide.
11. Wi-Fi à gauche (OFF), puis AIDE : violet, compteur à zéro. Wi-Fi à droite (ON) : la demande part, puis notification 1/5 après 750 ms. V passe ensuite au vert.
12. Après une alerte acceptée, Wi-Fi sur OFF puis V pour répondre : pas de vert avant reconnexion. Wi-Fi sur ON : lecture du OK avant toute relance et passage au vert.
13. Pushbullet sur OFF avec Wi-Fi disponible : mêmes attentes d’envoi, sans faux succès. V est ignoré pendant cette panne. Pushbullet sur ON puis V pour confirmer une alerte acceptée.
14. Après une alerte acceptée, couper le Wi-Fi et annuler : violet persistant. Rétablir : une seule annulation acceptée puis bleu ; aucune ancienne aide ne repart.
15. Passer le Wi-Fi sur OFF pendant les 750 ms d’un envoi : échec, compteur inchangé. Remettre sur ON : réessai, puis une seule notification acceptée.

Pour les tests locaux sous Python PC : `python -B -m unittest -v test_machine_etats test_reseau_simule test_pushbullet_reel`. Le fichier `test_entrees_sorties.py` est un programme matériel MicroPython conservé, et non un test unittest importable sous Python PC. Les tests asyncio ont nécessité une exécution hors sandbox sur Windows, car la boucle Python utilise une connexion interne ; tous les échanges Pushbullet des tests sont remplacés par des réponses locales.

Les couleurs et le geste d’annulation sont des choix d’essai à valider avec le père avant adoption définitive.
