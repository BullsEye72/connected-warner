# Boîtiers d’appel à l’aide — spécification de travail

Mise à jour : 12 octobre 2026.

Les exigences ci-dessous décrivent la cible. Les propositions signalées restent à valider avant leur réalisation. Les prototypes décrits ne couvrent qu’une partie de ces exigences.

## Objectif et décisions déjà retenues

Permettre au père de l’utilisateur, qui vit seul en France, de prévenir ses proches lors d’une grande faiblesse, sans dépendre de son élocution ni de la charge de sa montre. Il peut généralement appuyer sur un gros bouton.

- Deux boîtiers pour commencer : lit et salle de bains ; conception duplicable dans d’autres pièces.
- Un ESP32-S3 par boîtier, alimenté par chargeur USB, connecté au Wi-Fi.
- Chaque boîtier envoie directement ses alertes Pushbullet et traite ses propres confirmations. Le PC, Google Home et le futur site ne doivent pas être nécessaires à cette fonction.
- Version embarquée envisagée en MicroPython.
- Boîtier imprimé en 3D ; la fixation et les butées mécaniques doivent absorber un appui fort sans solliciter la carte électronique.
- Placement accessible depuis les situations d’usage prévues, y compris depuis le sol ; validation pratique avec le père avant fixation définitive.

Le panier matériel retenu, les variantes, les quantités, le budget et le stock existant sont consignés dans [MATERIEL.md](MATERIEL.md). La sélection comprend quatre ESP32-S3 N16R8 et cinq boutons RGB, avec deux boîtiers à réaliser en premier.

## État du prototype

Le fichier `pushbullet-boutons.html` simule les boutons et leurs voyants. Il envoie réellement des messages TEST, puis reconnaît les réponses Pushbullet provenant des comptes autorisés. L’utilisateur a validé l’aller-retour avec plusieurs comptes Pushbullet. Le prototype accepte désormais `OK` pour toutes les demandes en cours, ou `OK CODE` pour une seule demande.

Le prototype utilise par défaut cinq envois au total, espacés de deux minutes, et propose aussi un essai à envoi unique. Les demandes du prototype disparaissent au rechargement.

Le prototype sélectionne actuellement un seul destinataire à la fois. L’envoi simultané à une liste de proches décrit ci-dessous reste à implémenter ; les essais avec plusieurs comptes ont validé leurs échanges individuellement.

Un premier test MicroPython sur ESP32-S3 dans Wokwi a été validé par l’utilisateur le 12 octobre 2026 : séquence rouge/vert/bleu, puis rouge pendant l’appui et extinction au relâchement. Le câblage du bouton a été corrigé pour utiliser deux groupes de contacts distincts.

À sa demande, une [machine à états Wokwi](wokwi-test/README.md) prolonge désormais ce test : repos, demande en attente, plafond de relances sans confirmation, confirmation et annulation. Elle propose un mode réseau simulé et un mode réel Wi-Fi/Pushbullet. Les relances sont accélérées à cinq secondes en simulation ; le mode réel conserve par défaut deux minutes, maximum cinq envois acceptés par cycle. L’appui d’annulation reste de dix secondes et exige un relâchement après l’appui initial. AIDE utilise GPIO12 ; deux interrupteurs à glissière commandent les coupures Wi-Fi (GPIO13) et Pushbullet (GPIO14), gauche OFF et droite ON. En simulation, V représente une réponse fictive ; en mode réel, seule la réponse autorisée dans Pushbullet confirme. Cent treize tests locaux passent, avec les appels API remplacés par des réponses de test ; le certificat actuel de l’API a été vérifié depuis le PC avec le fichier CA fourni, sans jeton ni notification. La lecture HTTPS a été validée sans jeton dans Wokwi (HTTP 401 attendu) ; l’utilisateur a ensuite validé l’aller-retour authentifié : HTTP 200 puis OK autorisé et état CONFIRMEE. La synchronisation de plusieurs boîtiers et la persistance après redémarrage ne sont pas encore implémentées dans ce programme.

Le faux transport simule 750 ms de délai par envoi sans bloquer les boutons. Seules les alertes acceptées augmentent le compteur ; après panne, reprendre sans rafale. Un OK déposé côté faux Pushbullet peut attendre le retour du Wi-Fi du boîtier. Les annulations à transmettre sont conservées en RAM et traitées avant une nouvelle aide ; aucune aide annulée ne repart à la reconnexion. Un voyant violet signale réseau indisponible, première alerte pas encore acceptée ou annulation à transmettre. Il remplace temporairement les couleurs d’état, sauf pendant le geste d’annulation qui reste orange. Après annulation, le REPOS est immédiat mais le bleu attend la transmission de l’annulation et un réseau disponible. Ce modèle traite des échecs certains : les résultats incertains d’une requête réelle restent à réaliser.

Le 12 octobre, l’utilisateur a accepté un jeton Pushbullet temporaire dans Wokwi, à révoquer après les essais. Le mode réel est préparé pour un seul destinataire d’essai, l’utilisateur, avec tous les messages marqués TEST. Configuration du jeton dans Wokwi, sans le communiquer à l’assistant. Le transport utilise Wokwi-GUEST, HTTPS avec validation du certificat, synchronisation NTP et tâches asyncio. Le fichier de certificats racines publics est fourni. Une réponse `OK` ou `OK CODE` est reconnue selon le compte autorisé, l’identifiant du compte expéditeur, la date serveur du premier envoi et les réponses déjà consommées. Les erreurs de transport n’ajoutent pas d’acceptation au compteur ; les résultats incertains et doublons possibles sont signalés, sans garantie de déduplication à cette étape. Les limites HTTP 429 déclenchent une pause ; les erreurs de configuration/authentification nécessitent correction puis relancement. La résolution DNS MicroPython reste bloquante ; la réactivité doit encore être mesurée dans Wokwi et sur carte. Le mode réel reste un prototype, sans état persistant, plusieurs destinataires, dashboard ni OTA.

L’utilisateur signale une extinction après environ dix minutes de vert, sans message de retour au REPOS ni erreur visible. La cause dans Wokwi n’est pas établie. La commande LED est désormais centralisée dans `VoyantRGB`, qui ne reprogramme le PWM que si la couleur change ; deux tests vérifient la sortie effective bleu après confirmation et l’absence de réécritures inutiles. Un diagnostic console toutes les trente secondes aide à distinguer arrêt de boucle, transition d’état et problème de rendu. La correction du symptôme dans Wokwi reste à confirmer.

Pendant le premier essai réel, Wokwi a signalé ENOENT au chargement de `ca.pem` : le fichier n’était pas accessible au chemin configuré. Le transport peut désormais charger les mêmes certificats publics depuis `certificats.py` si le PEM manque, et fournit une erreur explicite si les deux sources sont absentes. Les trois tests de cette correction passent ; le nouvel essai Wokwi reste à faire.

L’utilisateur a ensuite fourni son [projet public sans jeton](https://wokwi.com/projects/477628209895659521) et autorisé son édition pour résoudre TimeoutError après connexion et mise à l’heure. Reproduction sans jeton : échec pendant la négociation TLS avec la chaîne initiale. L’ajout de l’émetteur actuel YE1, obtenu depuis la chaîne TLS vérifiée sur PC, au fichier de confiance permet un GET HTTPS complet dans Wokwi avec HTTP 401 attendu sans jeton. La vérification TLS reste obligatoire ; la cause interne exacte dans le simulateur n’est pas établie. Le fichier contient maintenant quatorze racines et cet émetteur, à réexaminer si la chaîne change ou avant son expiration le 2 septembre 2028. Les diagnostics précisent les étapes de la connexion et du délai dépassé. Une [copie corrigée](https://wokwi.com/projects/477633946468936705) a été enregistrée sans jeton, avec les boutons et le diagramme rétablis. L’utilisateur a depuis validé l’aller-retour authentifié, avec HTTP 200 et réponse OK reconnue. Le symptôme du voyant après dix minutes reste à vérifier.

Le nouvel essai utilisateur échoue après « envoi HTTPS et negociation TLS » avec un `OSError` dont le détail était masqué. La version locale de `pushbullet_reel.py` précise maintenant les codes numériques et marqueurs TLS connus, l’étape de la requête et la date UTC synchronisée, sans afficher le jeton ni les arguments arbitraires. Une erreur de fermeture ne masque plus l’erreur initiale. Quatre tests supplémentaires passent, soit quatre-vingts au total. Cette dernière correction n’a pas été appliquée dans Wokwi : la vérification automatique d’autorisation du navigateur n’a pas pu aboutir en raison d’une limite d’utilisation. Le fichier local est à recopier dans le projet pour obtenir la prochaine erreur complète ; la cause reste à établir.

L’utilisateur a depuis validé l’aller-retour réel : compte Pushbullet vérifié (HTTP 200), puis OK autorisé et passage à CONFIRMEE. Il signale ensuite un gel des animations pendant les communications. La nouvelle version locale de `pushbullet_reel.py` réutilise la connexion HTTPS, cache le DNS cinq minutes en conservant le nom TLS, consomme intégralement les réponses HTTP et compte l’intervalle de lecture après la fin de chaque lecture. Une connexion est abandonnée après erreur, annulation, fermeture demandée par le serveur, réponse sans longueur, changement de Wi-Fi ou trente secondes d’inactivité. Aucun POST n’est automatiquement répété. Treize tests supplémentaires passent (93 au total) ; deux GET sans jeton sur le PC confirment la réutilisation de connexion. Une surveillance signale les pauses de boucle d’au moins 250 ms. Le comportement reste à essayer dans Wokwi en recopiant uniquement ce fichier. La première négociation TLS et les reconnexions peuvent encore bloquer la boucle ; la réactivité des boutons lors de ces phases n’est pas garantie par ce changement et reste à vérifier avant déploiement.

L’essai suivant ne résout pas le gel : l’utilisateur constate encore une longue pause à « envoi HTTPS et negociation TLS ». La réutilisation de connexion ne doit donc pas être présentée comme une correction suffisante. Le [plan de réactivité réseau](REACTIVITE-RESEAU.md) précise l’exigence de traitement des boutons pendant DNS/TCP/TLS/HTTP et les essais à mesurer. Une option C++/Arduino avec tâches FreeRTOS distinctes pour commandes et réseau est proposée ; la préférence de l’utilisateur est demandée avant portage. Un simple thread Python n’apporte pas de garantie d’indépendance avec le GIL et les appels TLS natifs. Aucun portage ni changement en ligne n’est encore effectué ; le symptôme reste non résolu.

L’utilisateur a ensuite envoyé la documentation uasyncio v1.14 et des traces où chaque GET ouvre une nouvelle connexion TLS, sans réutilisation visible. Le programme utilise déjà asyncio/uasyncio. La proposition immédiate de portage C++ était prématurée ; aucun choix de langage ni portage n’est acté. Le fichier local affiche désormais la version `MP-HTTPS-20261012-2`, les raisons de fermeture ou de conservation de connexion et la durée de l’écriture TLS synchrone lorsque celle-ci dépasse 250 ms. Les diagnostics évitent les données privées. Deux nouveaux tests passent, soit 95 au total. La prochaine vérification Wokwi doit distinguer ancienne version, fermeture serveur et blocage natif avant de décider d’un changement d’architecture.

L’utilisateur signale ensuite un OK non reconnu malgré HTTP 200. Les traces gardent le format d’erreur de l’ancien transport, sans les nouveaux diagnostics. Un défaut de précision des dates a été reproduit avec l’équivalent float32 utilisé par MicroPython ESP32 : l’arrondi d’une date d’alerte vers le futur peut masquer les réponses récentes. Le décodeur conserve désormais les dates JSON avant conversion flottante et les traite en millisecondes entières ; la requête utilise des secondes entières et la comparaison rejette toujours les anciens OK. Le destinataire effectif est lié à l’identifiant fourni par le POST vérifié, avec comparaison originale/normalisée en secours. La version locale `MP-HTTPS-20261012-3` affiche aussi les nombres de textes OK et motifs de rejet, sans données privées. Treize nouveaux tests passent (108 au total). L’utilisateur doit recopier ce fichier, relancer et envoyer un nouveau OK après une nouvelle demande TEST. La cause du cas utilisateur et le gel TLS restent à confirmer dans Wokwi.

Les nouvelles traces `MP-HTTPS-20261012-3` montrent la réutilisation HTTPS et la reconnaissance du OK, avec état CONFIRMEE. Elles mesurent 7 679 ms de pause lors de la première négociation TLS et 270 à 694 ms pendant les réponses. L’utilisateur choisit un voyant de couleur fixe pendant les communications, puis la reprise de l’animation. La version locale ajoute le cyan `(0, 255, 255)`, prioritaire pendant les requêtes HTTPS, posé avant DNS/TLS grâce à un délai coopératif de vingt millisecondes et retiré après succès, erreur ou annulation. L’état de la demande ne change pas du fait de ce voyant. Le faux réseau utilise le même affichage pendant ses envois. Remplacer `main.py` et `pushbullet_reel.py` dans Wokwi ; version du transport `MP-HTTPS-20261012-4`. Cinq nouveaux tests passent, soit 113 au total. Le rendu reste à essayer ; le choix ne supprime pas les pauses de lecture des boutons lors de TLS. Aucun changement de langage n’est décidé.

## Demande d’aide et confirmation

Au repos, un appui déclenche une demande sans attendre la durée d’un appui long. Chaque demande possède un identifiant, le nom de la pièce et un code propre. Les appuis répétés pendant une demande en ATTENTE, avant le plafond d’envois, ne doivent pas multiplier les incidents.

**Exigence ajoutée le 12 octobre :** depuis CONFIRMEE (vert) ou SANS_CONFIRMATION (rouge clignotant rapidement), un nouvel appui bref sur AIDE permet de relancer. Dans le test, l’envoi attend le relâchement avant dix secondes pour distinguer cette action du maintien d’annulation. La relance crée un nouveau cycle avec un nouvel identifiant, remplace la demande courante, envoie une notification 1/5 et reprend les quatre relances prévues. Conserver la trace de l’ancienne demande sans la déclarer annulée ni envoyer « tout va bien ». Une ancienne confirmation ne doit pas confirmer ce nouveau cycle. Le choix du geste est fixé par l’état au début de l’appui : une confirmation reçue pendant un geste commencé en ATTENTE ne doit pas le transformer en nouvelle demande.

Le boîtier distingue : demande enregistrée localement, transmission impossible ou incertaine, message accepté par Pushbullet, attente d’un proche et prise en charge confirmée. Une lecture ou une suppression de notification ne vaut pas confirmation. Un voyant vert de prise en charge suppose une réponse valide d’un compte autorisé.

### Confirmation globale

L’utilisateur souhaite qu’une réponse simple **« OK »**, insensible à la casse, confirme **toutes les demandes en cours du même logement**. Il est acceptable de mettre tous les voyants concernés au vert et d’arrêter toutes leurs relances, même si plusieurs boutons ont été utilisés. Les espaces au début et à la fin de la réponse sont ignorés.

Le prototype valide le compte expéditeur pour au moins une demande active avant d’appliquer le `OK` global aux demandes déjà envoyées. Une réponse avec code reste disponible pour une confirmation individuelle. Une réponse globale ne doit pas confirmer une demande créée après cette réponse, ni réactiver une demande annulée. Une réponse déjà utilisée ne doit pas être réutilisée pour un nouvel incident.

Pour les appareils autonomes, prévoir un groupe de logement et une liste commune de proches autorisés, afin que chaque boîtier reconnaisse la même confirmation globale lorsqu’il lit Pushbullet. Retrouver également cette confirmation après reconnexion d’un boîtier, sans lui faire confirmer une demande plus récente. Le dashboard devra présenter cette prise en charge globale de manière cohérente.

La version embarquée doit conserver l’état nécessaire en mémoire persistante, retrouver une demande après redémarrage, borner les attentes réseau et reconnecter le Wi-Fi. Une requête interrompue peut avoir abouti : traiter explicitement les résultats incertains et les doublons.

### Relances retenues

Le 11 octobre 2026, l’utilisateur a proposé cinq envois espacés de deux minutes. Interprétation appliquée : **cinq envois au total**, soit un envoi immédiat et quatre relances. Le calendrier nominal est **0, 2, 4, 6 et 8 minutes**, tant qu’aucun proche n’a confirmé et que la demande n’a pas été annulée. Dans le prototype, l’intervalle est mesuré après acceptation de l’envoi précédent ; les délais réseau peuvent donc décaler ce calendrier.

Après le cinquième envoi, arrêter les relances automatiques mais conserver la demande comme non prise en charge et continuer à chercher une confirmation. Ne pas afficher un retour à l’état « tout va bien ». Une confirmation tardive reste valable pour cette demande.

Une modification du réglage s’applique aux nouvelles demandes. Avec plusieurs proches, les cinq envois s’entendent par destinataire : chaque cycle envoie individuellement la demande à chacun des proches actifs. Les lectures des confirmations et les signaux vers le site ne comptent pas comme relances.

Proposition à valider ultérieurement : après épuisement des cinq envois sans confirmation, prévoir un relais par un autre canal ou une notification distincte à un proche de secours. Le choix du relais et de ses destinataires reste à définir ; aucun relais supplémentaire n’est mis en place à cette étape.

### Retour au repos et voyants

Le 12 octobre, l’utilisateur a demandé un retour automatique au repos pour éviter un reset manuel. Comportement proposé et appliqué au test Wokwi : retour au bleu dix minutes après confirmation, et immédiatement après annulation. L’historique de la demande reste conservé ; une demande sans réponse reste active, même après dix minutes. Le retour automatique après confirmation attend la fin d’un geste d’annulation en cours. Cette interprétation du délai reste à valider avec l’utilisateur.

Palette d’essai : bleu au repos, orange clignotant en attente, orange fixe pendant le geste d’annulation, rouge clignotant rapidement après épuisement des cinq envois, vert après confirmation. Le mélange orange utilise du PWM ; adapter le rendu au matériel réel et valider la lisibilité avec le père.

## Plusieurs proches destinataires

**Exigence retenue :** une même demande d’aide peut prévenir plusieurs proches, chacun sur son propre compte Pushbullet. Une liste privée de destinataires remplace le destinataire unique du prototype. L’envoi se fait individuellement à chaque compte ; aucun channel public n’est utilisé.

- Chaque proche possède un nom d’affichage, l’adresse e-mail de son compte Pushbullet et un état actif ou désactivé. Éviter les doublons dans la liste.
- Les boîtiers du même logement partagent la même liste de proches autorisés. Un seul compte expéditeur Pushbullet suffit, avec son jeton configuré sur les boîtiers ; les jetons des proches ne sont pas nécessaires.
- Un appui envoie la même demande et le même identifiant à tous les proches actifs. Chaque relance suit le même principe, jusqu’à cinq notifications de demande par proche et par demande.
- Le premier proche autorisé qui répond `OK`, quelle que soit la casse, confirme toutes les demandes en cours du logement antérieures à sa réponse. Tous les boîtiers concernés arrêtent leurs relances et passent au vert lorsqu’ils reçoivent cette confirmation. Les autres proches n’ont pas besoin de confirmer à leur tour.
- Une réponse d’un compte inconnu est ignorée. Les protections contre les réponses anciennes ou déjà utilisées restent applicables. `OK CODE` conserve la confirmation individuelle.
- Une annulation informe les destinataires de la demande concernée, conformément aux règles de l’appui long.

Suivre séparément les envois à chaque destinataire : acceptation par Pushbullet, échec ou résultat incertain. Un échec pour un proche ne doit pas empêcher de prévenir les autres. L’acceptation par Pushbullet ne prouve pas que le proche a vu la notification. Le suivi doit permettre d’identifier les destinataires pour lesquels la transmission n’est pas confirmée, sans annoncer une réussite complète sur la seule réussite d’un envoi.

Exemple de consommation : quatre proches et cinq notifications représentent au maximum **vingt notifications de demande d’aide par demande**, hors messages d’annulation ou d’information de prise en charge. Des demandes provenant de plusieurs boîtiers s’ajoutent à ce total.

**Propositions à valider ultérieurement :** informer les autres proches avec un message tel que « Pris en charge par Paul », et gérer la liste depuis le dashboard. Le mécanisme de distribution des changements de liste aux boîtiers reste à définir ; la configuration initiale doit déjà permettre une liste commune sans dépendre du site pour envoyer les alertes.

## Dashboard sur l’hébergement web de l’utilisateur

**Exigence retenue :** afficher l’état de chaque appareil sur un tableau de bord hébergé chez l’utilisateur. Chaque appareil transmet un signal de présence, ou heartbeat, toutes les **dix minutes**. Il s’agit d’une requête HTTPS vers le site, pas d’un ping ICMP.

Proposition : transmettre également au démarrage et après un changement de demande, une confirmation, une annulation ou une mise à jour. Ces transmissions ne doivent pas retarder les alertes aux proches.

Informations prévues par appareil :

- Identifiant stable et emplacement, par exemple « Lit » ou « Salle de bains ».
- Date de dernière réception, enregistrée par le serveur.
- Version du programme, version MicroPython et état de mise à jour.
- État de la demande courante : aucune, en attente, confirmée ou annulée ; état de transmission associé.
- Dernière erreur connue, durée de fonctionnement depuis démarrage et nombre de redémarrages si disponible.
- Qualité du signal Wi-Fi, si disponible.

Une présence récente prouve que le programme a pu joindre le site à ce moment-là. Elle ne prouve pas à elle seule que le bouton mécanique, les LED ou Pushbullet fonctionnent. Le dashboard doit montrer l’état connu et sa date, sans confondre état ancien et état actuel.

Seuils proposés, à valider :

| Temps depuis le dernier signal | Affichage |
| --- | --- |
| Jusqu’à 15 minutes | Présence récente |
| Plus de 15 à 30 minutes | Signal en retard |
| Plus de 30 minutes | Appareil non joignable / état actuel inconnu |
| Aucun signal reçu | Appareil jamais vu |

L’absence de signal ne permet pas de distinguer coupure de courant, panne Wi-Fi, perte d’Internet ou panne du serveur. Une éventuelle notification aux proches pour appareil absent reste à définir, avec regroupement si plusieurs boîtiers deviennent absents ensemble.

Chaque appareil dispose d’une authentification propre auprès du site. Le dashboard est privé. Les données de suivi ne contiennent ni le jeton Pushbullet ni le mot de passe Wi-Fi. La panne du site laisse fonctionner le chemin direct vers Pushbullet ; elle rend seulement indisponibles le suivi et la détection de mises à jour.

Avec deux appareils, la fréquence nominale représente 288 signaux par jour, hors événements supplémentaires. Ces requêtes vers le site ne sont pas des notifications Pushbullet.

## Annulation par maintien du bouton pendant dix secondes

**Exigence retenue :** un appui continu de **dix secondes** permet d’annuler une demande en annonçant aux proches : **« Tout compte fait, tout va bien. »**

- L’annulation identifie la demande et la pièce concernées ; elle ne touche pas une demande d’un autre boîtier.
- Elle arrête les relances de cette demande et conserve un événement d’annulation dans l’historique.
- Elle est transmise aux destinataires de la demande, même si un proche l’a déjà prise en charge.
- Le message présente une déclaration issue du boîtier, par exemple « Lit — demande annulée par maintien du bouton : “Tout compte fait, tout va bien.” ».
- Un relâchement avant dix secondes n’annule pas la demande : en ATTENTE, il laisse le cycle en cours ; après confirmation ou plafond d’envois, il relance conformément au geste décrit plus haut. Un maintien prolongé au-delà du seuil n’envoie qu’une seule annulation et aucune nouvelle alerte d’aide.
- Dès le début du geste d’annulation, suspendre les nouvelles relances. Si le geste est interrompu avant dix secondes, reprendre après un intervalle complet depuis le relâchement, sans rafale de rattrapage. Le premier envoi d’aide reste immédiat ; un envoi réseau déjà engagé ne peut pas être supposé annulé.
- Sans demande à annuler, le geste d’annulation ne doit pas émettre un message « tout va bien » concernant une ancienne demande.
- Prévoir un retour visuel pendant le maintien et à sa validation. Les couleurs et le rythme sont à choisir avec le père.

**Proposition ergonomique à valider :** demander le relâchement du premier appui avant d’accepter un nouvel appui de dix secondes pour annuler. Ainsi, le premier appui déclenche l’aide immédiatement et son maintien involontaire ne l’annule pas automatiquement. Vérifier la facilité de ce geste avec le père.

Si le réseau est absent, l’annulation est enregistrée durablement et les relances locales cessent. L’écran de suivi et le retour local distinguent « annulée sur le boîtier » de « information des proches transmise ». Si un envoi initial a été tenté ou accepté, transmettre l’annulation dès le retour réseau. Une demande annulée avant toute tentative d’envoi ne doit pas être envoyée ensuite comme nouvelle alerte.

Une confirmation tardive ne réactive pas une demande annulée. Les événements utilisent le même identifiant de demande et un ordre explicite. Un nouvel appui d’aide après annulation crée une nouvelle demande. Le voyant vert reste réservé à une confirmation de prise en charge, pas à l’annulation.

## Mises à jour OTA

**Exigence retenue :** prévoir la mise à jour à distance des appareils, sans câble USB. La réponse au signal de présence peut indiquer une version disponible et fournir les informations permettant son téléchargement.

Deux niveaux sont distingués :

1. **Programme Python : priorité proposée.** Télécharger une nouvelle version des fichiers applicatifs dans un emplacement séparé, les vérifier, puis les activer au redémarrage avec un mécanisme de retour à la version précédente.
2. **Firmware MicroPython : étape ultérieure.** Possible sur ESP32 avec un partitionnement et un firmware adaptés. Vérifier les partitions disponibles et la prise en charge du retour automatique avant de l’annoncer comme fonction du boîtier. La disponibilité d’une API OTA n’installe pas à elle seule un système de mise à jour complet.

Déroulement cible :

- Le serveur indique une version compatible et les appareils autorisés à la recevoir. Par défaut proposé, le dashboard signale sa disponibilité ; l’utilisateur choisit la version à déployer et les appareils concernés.
- Le boîtier reporte l’activation lorsqu’une demande d’aide ou une annulation à transmettre est en cours.
- Le téléchargement et les vérifications se font avant de remplacer la version active. La gestion du bouton conserve la priorité ; interrompre ou reporter la mise à jour si une demande survient.
- Vérifier l’intégrité, la provenance et la compatibilité de la version. Utiliser HTTPS avec validation du certificat ; une empreinte de fichier sert à contrôler son intégrité, pas à prouver seule son origine. Le mécanisme d’authenticité de publication est à choisir avant réalisation.
- Conserver la version précédente et un lanceur de récupération pour les mises à jour Python ; ne pas écraser les fichiers actifs au fil du téléchargement.
- Une nouvelle version n’est validée qu’après un démarrage réussi et des contrôles définis. Un watchdog et un compteur d’échecs doivent permettre le retour à la version précédente si le programme ne démarre plus correctement.
- Préserver la configuration, les secrets et l’historique des demandes. Les formats de données doivent rester compatibles avec le retour arrière ou disposer d’une migration réversible.
- Afficher sur le dashboard : version disponible, téléchargement, activation reportée, version active, échec ou retour arrière.
- Tester le déploiement sur un boîtier avant de généraliser aux autres.

Prévoir une fenêtre d’activation configurable ; la durée d’indisponibilité pendant le redémarrage doit être connue. Les mises à jour du programme et du firmware nécessitent des mécanismes de récupération distincts. La faisabilité sur l’hébergement dépend de ses fonctions HTTPS, de son stockage, de son traitement des requêtes et de son authentification ; ces caractéristiques restent à relever.

## Bouton RGB à anode commune : information reçue

L’utilisateur rapporte un commentaire d’acheteur concernant la version RGB. Cette information est provisoire et ne vaut pas fiche technique pour toutes les variantes du vendeur.

| Broche indiquée dans le commentaire | Fonction annoncée |
| --- | --- |
| 1 | Anode commune positive |
| 2 | Cathode de la LED rouge |
| 3 | Cathode de la LED verte |
| 4 | Cathode de la LED bleue |

Le commentaire indique un fonctionnement à 3,3 V ou 5 V et un pilotage en drain ouvert. Ce mode allume une couleur en ramenant sa cathode vers la masse et l’éteint en libérant cette connexion. Relier en permanence les cathodes à la masse les maintiendrait allumées et ne permettrait pas de sélectionner les couleurs.

Ces quatre connexions concernent l’éclairage. Repérer séparément les deux bornes du contact momentané normalement ouvert (1NO) ; contrôler au multimètre leur fermeture à l’appui et leur séparation du circuit des LED.

Contraintes pour le schéma définitif :

- Les GPIO de l’ESP32-S3 utilisent une logique à 3,3 V. Le mode drain ouvert ne rend pas une broche tolérante au 5 V. Ne pas valider le raccordement direct des cathodes au GPIO avec une anode alimentée en 5 V.
- Proposition retenue pour l’étude : trois transistors ou MOSFET adaptés, un par couleur, commandés à 3,3 V et commutant les cathodes vers la masse. Cette solution permet de séparer le courant des LED de la commande des GPIO. Prévoir leur état éteint au démarrage et une masse commune.
- Vérifier les résistances intégrées et le courant de chaque couleur à la tension choisie. Ajouter une limitation de courant par couleur si nécessaire ; ne pas choisir les valeurs sans ces données.
- Une commande directe à 3,3 V en drain ouvert reste une possibilité seulement après validation du courant, de la tension et du comportement du bouton reçu.
- Le contact d’appui sera étudié comme une entrée indépendante avec rappel à 3,3 V et anti-rebond ; ne pas lui appliquer le 5 V du circuit d’éclairage.
- Choisir les GPIO d’après la carte et sa variante exacte, en évitant les broches réservées à la mémoire, au démarrage ou à d’autres fonctions utilisées.
- Vérifier le diamètre réel de la surface d’appui, la force nécessaire et la course : « 25 mm » peut désigner le perçage de montage.

Pour la salle de bains, valider l’emplacement du chargeur, du câble et du boîtier ainsi que la protection contre l’humidité. L’étanchéité annoncée du bouton ne certifie pas l’ensemble imprimé.

## Vérifications à prévoir avant usage des boîtiers

- Appui bref, rebonds, appuis répétés et appui long inférieur ou supérieur à dix secondes.
- Annulation avant envoi, après envoi et après prise en charge ; confirmation tardive après annulation.
- Envoi à plusieurs proches, échec pour un seul destinataire, réponse `OK` de chacun des proches autorisés et rejet d’une réponse d’un compte inconnu.
- Confirmation globale de plusieurs boîtiers, dont un temporairement hors ligne ; arrêt des relances sans attendre les réponses des autres proches.
- Coupure Wi-Fi, perte d’Internet, panne du site et indisponibilité de Pushbullet.
- Coupure de courant puis reprise, avec demande ou annulation conservée.
- Détection d’un appareil absent selon les seuils choisis et affichage explicite d’un état ancien.
- Mise à jour interrompue, fichier incomplet, version incompatible, échec au démarrage et retour à la version précédente.
- Appui pendant téléchargement et pendant la fenêtre d’activation d’une mise à jour.
- Vérification mécanique et électrique des composants réellement reçus.

## Sources et éléments à confirmer

- [API Pushbullet](https://docs.pushbullet.com/) : envoi des alertes et lecture des confirmations.
- [Firmware MicroPython ESP32-S3](https://micropython.org/download/ESP32_GENERIC_S3/) : choix selon la carte et la PSRAM.
- [MicroPython : partitions et OTA ESP32](https://docs.micropython.org/en/latest/library/esp32.html#flash-partitions) : l’OTA firmware et son retour arrière dépendent du partitionnement et de la configuration du firmware.
- [MicroPython : HTTPS et certificats](https://docs.micropython.org/en/latest/library/ssl.html) : validation du certificat, nom du serveur et horloge.
- [Fiche technique ESP32-S3, caractéristiques électriques](https://www.espressif.com/sites/default/files/documentation/esp32-s3_datasheet_en.pdf) : tableaux 5-2 et 5-4, logique à 3,3 V et caractéristiques des GPIO.
- Brochage du bouton : commentaire d’acheteur transmis par l’utilisateur, à vérifier sur le produit reçu. Résistances, courant, force d’appui et numérotation des bornes restent à confirmer.
