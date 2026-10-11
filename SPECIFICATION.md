# Boîtiers d’appel à l’aide — spécification de travail

Mise à jour : 11 octobre 2026.

Les exigences ci-dessous décrivent la cible. Les propositions signalées restent à valider avant leur réalisation. Cette mise à jour ajoute de la documentation ; elle ne modifie pas le prototype.

## Objectif et décisions déjà retenues

Permettre au père de l’utilisateur, qui vit seul en France, de prévenir ses proches lors d’une grande faiblesse, sans dépendre de son élocution ni de la charge de sa montre. Il peut généralement appuyer sur un gros bouton.

- Deux boîtiers pour commencer : lit et salle de bains ; conception duplicable dans d’autres pièces.
- Un ESP32-S3 par boîtier, alimenté par chargeur USB, connecté au Wi-Fi.
- Chaque boîtier envoie directement ses alertes Pushbullet et traite ses propres confirmations. Le PC, Google Home et le futur site ne doivent pas être nécessaires à cette fonction.
- Version embarquée envisagée en MicroPython.
- Boîtier imprimé en 3D ; la fixation et les butées mécaniques doivent absorber un appui fort sans solliciter la carte électronique.
- Placement accessible depuis les situations d’usage prévues, y compris depuis le sol ; validation pratique avec le père avant fixation définitive.

## État du prototype

Le fichier `pushbullet-boutons.html` simule les boutons et leurs voyants. Il envoie réellement des messages TEST, puis reconnaît les réponses Pushbullet provenant des comptes autorisés. L’utilisateur a validé l’aller-retour avec plusieurs comptes Pushbullet. Le prototype accepte désormais `OK` pour toutes les demandes en cours, ou `OK CODE` pour une seule demande.

Le prototype utilise par défaut cinq envois au total, espacés de deux minutes, et propose aussi un essai à envoi unique. Les demandes du prototype disparaissent au rechargement.

## Demande d’aide et confirmation

Un appui déclenche une demande sans attendre la durée d’un appui long. Chaque demande possède un identifiant, le nom de la pièce et un code propre. Les appuis répétés pendant une demande en attente ne doivent pas multiplier les incidents.

Le boîtier distingue : demande enregistrée localement, transmission impossible ou incertaine, message accepté par Pushbullet, attente d’un proche et prise en charge confirmée. Une lecture ou une suppression de notification ne vaut pas confirmation. Un voyant vert de prise en charge suppose une réponse valide d’un compte autorisé.

### Confirmation globale

L’utilisateur souhaite qu’une réponse simple **« OK »**, insensible à la casse, confirme **toutes les demandes en cours du même logement**. Il est acceptable de mettre tous les voyants concernés au vert et d’arrêter toutes leurs relances, même si plusieurs boutons ont été utilisés. Les espaces au début et à la fin de la réponse sont ignorés.

Le prototype valide le compte expéditeur pour au moins une demande active avant d’appliquer le `OK` global aux demandes déjà envoyées. Une réponse avec code reste disponible pour une confirmation individuelle. Une réponse globale ne doit pas confirmer une demande créée après cette réponse, ni réactiver une demande annulée. Une réponse déjà utilisée ne doit pas être réutilisée pour un nouvel incident.

Pour les appareils autonomes, prévoir un groupe de logement et une liste commune de proches autorisés, afin que chaque boîtier reconnaisse la même confirmation globale lorsqu’il lit Pushbullet. Retrouver également cette confirmation après reconnexion d’un boîtier, sans lui faire confirmer une demande plus récente. Le dashboard devra présenter cette prise en charge globale de manière cohérente.

La version embarquée doit conserver l’état nécessaire en mémoire persistante, retrouver une demande après redémarrage, borner les attentes réseau et reconnecter le Wi-Fi. Une requête interrompue peut avoir abouti : traiter explicitement les résultats incertains et les doublons.

### Relances retenues

Le 11 octobre 2026, l’utilisateur a proposé cinq envois espacés de deux minutes. Interprétation appliquée : **cinq envois au total**, soit un envoi immédiat et quatre relances. Le calendrier nominal est **0, 2, 4, 6 et 8 minutes**, tant qu’aucun proche n’a confirmé et que la demande n’a pas été annulée. Dans le prototype, l’intervalle est mesuré après acceptation de l’envoi précédent ; les délais réseau peuvent donc décaler ce calendrier.

Après le cinquième envoi, arrêter les relances automatiques mais conserver la demande comme non prise en charge et continuer à chercher une confirmation. Ne pas afficher un retour à l’état « tout va bien ». Une confirmation tardive reste valable pour cette demande.

Une modification du réglage s’applique aux nouvelles demandes. Les cinq envois concernent les notifications de demande d’aide ; les lectures des confirmations et les signaux vers le site ne comptent pas comme relances.

Proposition à valider ultérieurement : après épuisement des cinq envois sans confirmation, prévoir un relais par un autre canal ou une notification distincte à un proche de secours. Le choix du relais et de ses destinataires reste à définir ; aucun relais supplémentaire n’est mis en place à cette étape.

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
- Un relâchement avant dix secondes n’annule pas la demande. Un maintien prolongé au-delà du seuil n’envoie qu’une seule annulation.
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
