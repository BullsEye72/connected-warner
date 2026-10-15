# Matériel retenu pour les prototypes et le stock

Mise à jour : 16 octobre 2026.

Cette liste reprend les choix communiqués par l’utilisateur. Le 15 octobre, il confirme avoir tout reçu sauf les boutons RGB et les MOSFET AliExpress : les articles Amazon du panier initial et le support de soudure Goobay sont donc reçus. Pour le lot de microphones ajouté ensuite au panier, l’utilisateur annonce qu’il passe commande ; la finalisation de l’achat et la réception ne sont pas confirmées. Les caractéristiques annoncées et le contenu exact des kits restent à vérifier sur les pièces.

Livraisons annoncées le 12 octobre : AliExpress indiquait une arrivée entre le **20 et le 23 octobre 2026**. Au 15 octobre, seuls les boutons RGB et les MOSFET restent attendus ; cette estimation initiale n’est pas une nouvelle confirmation de livraison. Le 14 octobre, une carte AYWHP ESP32-S3 N16R8 reçue a été essayée : 16 Mo de flash, 8 Mo de PSRAM et une LED RGB intégrée. Elle est reconnue sur COM4 via un pont USB-série CH343 ; MicroPython 1.29.0 avec PSRAM octale est installé et son démarrage est vérifié.

## Panier Amazon

| Article | Quantité achetée dans le panier | Variante et contenu retenus | Prix de la ligne |
| --- | --- | --- | ---: |
| SCHDRA, fil souple | 1 kit | Cuivre étamé multibrins, PVC, 22 AWG / 0,34 mm², six couleurs de 4 m : 24 m | 13,09 € |
| AUKENIEN, assortiment BJT | 1 kit | 250 transistors TO-92, 25 de chaque référence : 2N2222, 2N2907, 2N3904, 2N3906, A1015, BC327, BC337, C1815, S8050, S8550 | 8,99 € |
| RUNCCI-YUN, kit de prototypage | 1 kit | 19 plaques FR4 double face, pas de 2,54 mm, avec barrettes et borniers ; 82 pièces accessoires compris | 12,98 € |
| HUAREW, breadboards et Dupont | 1 kit | Breadboards de 400 et 830 points, Dupont mâle–mâle, mâle–femelle et femelle–femelle | Environ 15 € ; prix exact non recopié |
| Fil rigide | 1 kit | Cuivre étamé monobrin, PVC, 22 AWG / 0,35 mm², sept couleurs de 5 m : 35 m | 18,98 € |
| AYWHP, cartes ESP32-S3 | 2 lots de deux | DevC-1 N16R8 : quatre cartes au total, sans antenne externe | 33,98 € (2 × 16,99 €) |
| TOWOT, flux liquide | 1 flacon | 30 ml, colophane, annoncé pour électronique et sans nettoyage | 9,99 € |

Total Amazon annoncé par l’utilisateur : environ **113 €**. Les lignes dont le prix est recopié totalisent **98,01 €**, hors kit HUAREW. Avec ce kit à 15 €, le total serait 113,01 € ; à 14,99 €, il serait 113,00 €. Le prix exact du kit n’est pas déduit comme un fait.

Le kit RUNCCI-YUN comprend, selon la description transmise :

- Six plaques 20 × 80 mm, six 30 × 70 mm, trois 40 × 60 mm, trois 50 × 70 mm et une 70 × 90 mm.
- Huit borniers à vis deux pôles et six trois pôles, pas de 5,08 mm.
- Huit barrettes mâles droites de 40 broches, huit autres barrettes mâles de 40 broches dont la forme reste à vérifier, et huit barrettes femelles de 40 broches ; pas de 2,54 mm.
- Vingt-cinq capuchons de cavalier.

Pour le kit HUAREW reçu, le titre indique deux breadboards ; la photo semblait en montrer davantage selon l’utilisateur. Leur nombre exact reste à vérifier. Les 120 câbles évoqués sont à vérifier dans le contenu livré, ainsi que leur répartition et leur longueur.

Les headers des cartes ESP32 semblent déjà soudés selon les observations de l’utilisateur ; confirmer sur la variante reçue. Vérifier également l’antenne intégrée et le marquage N16R8.

## Sélection AliExpress conservée

- **Cinq boutons** : anneau tricolore RGB, finition « Alumina (Black) », éclairage 3–6 V, 25 mm, contact momentané 1NO. L’anode commune et le brochage annoncés par un commentaire restent à vérifier sur les pièces reçues.
- **Un lot de 100 MOSFET annoncé AO3400 / AO3400A / A09T**, format SOT-23, pour compléter le stock. La description mélange les références et les mentions de fabricant ; les caractéristiques des exemplaires livrés restent à vérifier.

Budget communiqué : environ **23 € d’articles + 7 € de port = 30 €**. Vérifier le récapitulatif final, y compris les éventuels frais d’import, avant de considérer ce montant comme le coût payé.

Le lot Amazon de 50 MOSFET à 6 € a été remplacé dans la sélection par ce lot AliExpress ; il n’entre pas dans le panier Amazon final recopié.

Budget global des deux paniers : environ **143 €**, hors support de soudure déjà commandé séparément et sous réserve du récapitulatif final AliExpress.

## Ajout au panier : détection sonore (15 octobre 2026)

- **Un lot de cinq modules GY-MAX4466**, intitulé communiqué : « GY-MAX4466 Electret Lot de 5 amplificateurs de microphone avec contrôle de gain réglable pour Arduino ».
- Prix communiqué : **8 € le lot**, soit 1,60 € par module. Après l’ajout au panier, l’utilisateur annonce qu’il passe commande ; finalisation et réception non confirmées. Ces 8 € ne sont pas inclus dans les totaux historiques ci-dessus.
- Ce choix remplace la piste du lot DollaTek de trois modules MAX4466. Prévoir un module par boîtier équipé ; les autres serviront aux essais, à la réserve ou à d’autres projets.
- Le module complet comprend le microphone électret, son amplificateur et le potentiomètre de gain. Raccordement envisagé : **3,3 V, GND et OUT vers une entrée ADC libre de l’ESP32-S3** ; la broche reste à choisir. Utiliser les fils et breadboards déjà disponibles. Vérifier le brochage des modules reçus.
- Le gain et le seuil seront ajustés avec des appels depuis le sol et aux distances d’usage, puis avec le microphone dans le boîtier final. La portée n’est pas encore validée.

Pour le boîtier, aucun joint ni aucune membrane spécialisée n’est retenu à l’achat à ce stade. Le ruban EPDM esnado 6 × 2 mm, rouleau de 10 m à 8,95 € affichés, et le silicone RTV neutre ont été envisagés puis laissés de côté pour la première version. La fiche EPDM transmise ne confirme pas les cellules fermées. Un film plastique fin devant le micro reste une piste d’essai, sans choix définitif.

Les décisions de détection et de conception du boîtier sont détaillées dans [SPECIFICATION.md](SPECIFICATION.md#détection-sonore-en-complément-du-bouton-15-octobre-2026).

## Retour sonore : réutilisation des speakers PC (15 octobre 2026)

L’utilisateur possède des petits speakers de carte mère : capsule noire à deux fils rouge/noir, connecteur « SPEAKER » à quatre emplacements dont deux câblés. L’exemple donné est « CABLEPELADO Mini Haut-parleur pour Carte Mère / Buzzer Statut PC / 11 cm / 4 broches » ; c’est une référence de comparaison, pas un achat annoncé. Leur réutilisation est retenue pour commencer par des séries de bips, avec de petites mélodies envisagées ensuite par variation de fréquence si les exemplaires sont passifs. La photo et le titre commercial ne suffisent pas à établir qu’ils sont piézoélectriques.

Prévoir une commande par **un BC337 supplémentaire par boîtier**, avec résistance de base et protection adaptée au transducteur. Pour un modèle électromagnétique, prévoir une diode de roue libre. Tension, courant, valeurs et schéma seront déterminés au montage ; aucun essai du speaker sur ESP32 n’est encore réalisé. Les transistors et résistances sont déjà en stock ; aucun autre buzzer ni amplificateur audio n’est retenu à l’achat.

Le lot de **1N5818 traversantes** ci-dessous est commandé pour la roue libre du speaker électromagnétique ([fiche de la famille 1N5817/18/19](https://www.vishay.com/docs/88525/1n5817.pdf)). La gaine thermorétractable est déjà disponible : aucun achat nécessaire. La visserie et les entretoises attendront les dimensions du boîtier.

### Lot de 20 diodes 1N5818 commandé le 16 octobre 2026

- **20 diodes Schottky 1N5818, 1 A / 30 V**, boîtier axial DO-41 (DO-204AL).
- Prix communiqué : **5 € avec livraison Prime offerte**.
- Commande confirmée par l’utilisateur le **16 octobre** ; livraison annoncée pour **mardi 20 octobre 2026**, réception non confirmée.
- Deux exemplaires prévus pour les deux speakers, le reste pour les essais et le stock. Le raccordement sera validé lors du montage.

Ce lot remplace le kit de 100 diodes initialement ajouté au panier à 5 € : celui-ci annonçait finalement 6 € de port et une livraison en novembre, il n’est donc plus retenu. Les autres assortiments et le lot de 150 diodes 1N5819 discutés ne sont pas retenus non plus.

Les micros à 8 € et le lot de diodes commandé à 5 € représentent **13 € d’ajouts annoncés**, sans frais de port pour les diodes ; ils ne sont pas intégrés aux totaux historiques des paniers initiaux. Le statut des micros reste celui indiqué dans leur section.

## Matériel déjà disponible et outil reçu

- Stock de résistances et de condensateurs ; l’utilisateur utilise depuis plusieurs années ses assortiments existants.
- Fils déjà disponibles, complétés par les deux nouveaux lots.
- Boutons-poussoirs et LED RGB déjà en stock, utilisables pour le prototype sur breadboard avant réception des boutons métalliques. Identifier le contact des boutons et le type exact des LED : anode commune, cathode commune ou LED adressable ; ne pas leur appliquer automatiquement le câblage du bouton AliExpress.
- Speakers de carte mère à deux fils déjà disponibles, retenus pour le retour sonore ; voir la section ci-dessus. Quantité disponible non précisée.
- Chargeurs USB et câbles existants ; garder au moins un câble permettant les données pour programmer et dépanner.
- Poste à souder, ancienne bobine de fil à souder, tresse, pompe à dessouder et différentes pannes. L’âge seul ne motive pas le remplacement du fil ; état, alliage et qualité du mouillage à vérifier lors d’un essai.
- Gaine thermorétractable déjà disponible, confirmé le 15 octobre.
- Support PCB Goobay avec repose-fer : reçu selon la confirmation globale du 15 octobre. Rotation à 360°, bras coulissants, serrage à ressort ; largeur annoncée de 18 cm et hauteur de pièce de 13 cm pour une rotation complète.

La disponibilité d’un multimètre, d’une pince coupante et d’un outil à dénuder reste à confirmer ; aucun achat supplémentaire n’est déduit de cette note.

## Affectation prévue

Deux ESP32 équiperont le lit et la salle de bains ; un troisième servira au développement et le quatrième restera en réserve. Les trois boutons supplémentaires et les composants excédentaires complètent le stock pour d’autres pièces ou projets.

Pour les deux premiers boîtiers, prévoir **six BC337**, trois par éclairage RGB, avec les résistances adaptées après mesure. Les MOSFET ne sont pas nécessaires à cette première réalisation.

La commande des deux speakers ajouterait **deux BC337**, soit huit au total pour les deux boîtiers avec leurs voyants RGB ; ces transistors peuvent être pris dans le kit existant.

Les plaques 30 × 70 mm peuvent servir au circuit de commande avec l’ESP32 fixé séparément. Les formats 50 × 70 mm ou 70 × 90 mm donnent davantage de place pour un montage regroupé ; décider après réception et mesure des cartes. Les barrettes femelles pourront rendre les ESP32 démontables.

Tester les circuits sur breadboard avant leur transfert sur une plaque soudée. Le support de soudure maintient la plaque ; les composants doivent aussi être retenus avant de la retourner.

## Démarrage avant réception des boutons AliExpress

Le [test d’entrée et de sortie dans Wokwi](wokwi-test/README.md) a été validé par l’utilisateur le 12 octobre : LED RGB et bouton fonctionnels après correction des contacts du bouton. Cette validation concerne le simulateur, pas les composants physiques encore à monter.

Le matériel Amazon est reçu. Le prototype utilise déjà un ESP32, un bouton-poussoir du stock sur GPIO12 et la LED RGB intégrée sur GPIO48. Appui, confirmation Pushbullet et accès au portail par maintien à la mise sous tension sont validés sur cette carte. Le remplacement provisoire concerne l’interface physique ; les fonctions cibles restent celles de la spec.

Le 15 octobre, l’utilisateur donne un retour positif sur la version avec respiration des voyants. Le réglage d’intensité est reporté à la réception des boutons RGB. L’usage de la LED de carte principalement pour la configuration est une piste à reprendre plus tard ; aucune modification du pilotage actuel n’est décidée.

1. Vérifier le démarrage de l’ESP32, sa mémoire et sa connexion au Wi-Fi.
2. Identifier les composants du stock et tester séparément le contact du bouton et chaque couleur, avec le câblage et les résistances adaptés à la LED utilisée.
3. Valider un appui bref pour demander de l’aide, les relances et la confirmation Pushbullet globale. Les essais doivent être clairement identifiés comme TEST.
4. Ajouter l’annulation par maintien de dix secondes, puis vérifier l’arrêt des relances et l’information des proches.
5. À réception AliExpress, vérifier le bouton métallique et adapter le raccordement des LED ; conserver le comportement déjà testé. Valider ensuite la force d’appui et la fixation mécanique.

La LED RGB du stock ne sert pas à valider l’effort d’appui, l’étanchéité ou la tenue mécanique du bouton définitif. Les MOSFET AliExpress ne sont pas un préalable au démarrage du prototype.

Les exigences fonctionnelles et les vérifications avant usage restent décrites dans [SPECIFICATION.md](SPECIFICATION.md). Aucun schéma définitif ni programme embarqué n’est ajouté par cette note.
