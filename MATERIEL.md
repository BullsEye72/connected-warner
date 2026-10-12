# Matériel retenu pour les prototypes et le stock

Mise à jour : 12 octobre 2026.

Cette liste reprend les choix communiqués par l’utilisateur. Le support de soudure Goobay est annoncé comme commandé sur Amazon. Pour les autres articles, elle décrit le panier retenu ; les commandes et les réceptions restent à renseigner.

Livraisons annoncées le 12 octobre : Amazon livre rapidement selon l’utilisateur, sans date précise communiquée ; AliExpress indique une arrivée entre le **20 et le 23 octobre 2026**. Les réceptions ne sont pas encore confirmées.

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

Pour le kit HUAREW, le titre indique deux breadboards ; la photo semble en montrer davantage selon l’utilisateur. Confirmer leur nombre à réception. Les 120 câbles évoqués sont à vérifier dans le contenu livré, ainsi que leur répartition et leur longueur.

Les headers des cartes ESP32 semblent déjà soudés selon les observations de l’utilisateur ; confirmer sur la variante reçue. Vérifier également l’antenne intégrée et le marquage N16R8.

## Sélection AliExpress conservée

- **Cinq boutons** : anneau tricolore RGB, finition « Alumina (Black) », éclairage 3–6 V, 25 mm, contact momentané 1NO. L’anode commune et le brochage annoncés par un commentaire restent à vérifier sur les pièces reçues.
- **Un lot de 100 MOSFET annoncé AO3400 / AO3400A / A09T**, format SOT-23, pour compléter le stock. La description mélange les références et les mentions de fabricant ; les caractéristiques des exemplaires livrés restent à vérifier.

Budget communiqué : environ **23 € d’articles + 7 € de port = 30 €**. Vérifier le récapitulatif final, y compris les éventuels frais d’import, avant de considérer ce montant comme le coût payé.

Le lot Amazon de 50 MOSFET à 6 € a été remplacé dans la sélection par ce lot AliExpress ; il n’entre pas dans le panier Amazon final recopié.

Budget global des deux paniers : environ **143 €**, hors support de soudure déjà commandé séparément et sous réserve du récapitulatif final AliExpress.

## Matériel déjà disponible et outil commandé

- Stock de résistances et de condensateurs ; l’utilisateur utilise depuis plusieurs années ses assortiments existants.
- Fils déjà disponibles, complétés par les deux nouveaux lots.
- Boutons-poussoirs et LED RGB déjà en stock, utilisables pour le prototype sur breadboard avant réception des boutons métalliques. Identifier le contact des boutons et le type exact des LED : anode commune, cathode commune ou LED adressable ; ne pas leur appliquer automatiquement le câblage du bouton AliExpress.
- Buzzers de PC présentés comme piézo : type, tension et courant à identifier avant utilisation.
- Chargeurs USB et câbles existants ; garder au moins un câble permettant les données pour programmer et dépanner.
- Poste à souder, étain, tresse, pompe à dessouder et différentes pannes.
- Support PCB Goobay avec repose-fer : commande Amazon confirmée par l’utilisateur. Rotation à 360°, bras coulissants, serrage à ressort ; largeur annoncée de 18 cm et hauteur de pièce de 13 cm pour une rotation complète.

La disponibilité d’un multimètre, d’une pince coupante et d’un outil à dénuder reste à confirmer ; aucun achat supplémentaire n’est déduit de cette note.

## Affectation prévue

Deux ESP32 équiperont le lit et la salle de bains ; un troisième servira au développement et le quatrième restera en réserve. Les trois boutons supplémentaires et les composants excédentaires complètent le stock pour d’autres pièces ou projets.

Pour les deux premiers boîtiers, prévoir **six BC337**, trois par éclairage RGB, avec les résistances adaptées après mesure. Les MOSFET ne sont pas nécessaires à cette première réalisation.

Les plaques 30 × 70 mm peuvent servir au circuit de commande avec l’ESP32 fixé séparément. Les formats 50 × 70 mm ou 70 × 90 mm donnent davantage de place pour un montage regroupé ; décider après réception et mesure des cartes. Les barrettes femelles pourront rendre les ESP32 démontables.

Tester les circuits sur breadboard avant leur transfert sur une plaque soudée. Le support de soudure maintient la plaque ; les composants doivent aussi être retenus avant de la retourner.

## Démarrage avant réception des boutons AliExpress

Le [test d’entrée et de sortie dans Wokwi](wokwi-test/README.md) a été validé par l’utilisateur le 12 octobre : LED RGB et bouton fonctionnels après correction des contacts du bouton. Cette validation concerne le simulateur, pas les composants physiques encore à monter.

Dès réception du matériel Amazon, utiliser un ESP32, un bouton-poussoir du stock et une LED RGB séparée pour représenter un boîtier. Le remplacement provisoire concerne l’interface physique ; les fonctions cibles restent celles de la spec.

1. Vérifier le démarrage de l’ESP32, sa mémoire et sa connexion au Wi-Fi.
2. Identifier les composants du stock et tester séparément le contact du bouton et chaque couleur, avec le câblage et les résistances adaptés à la LED utilisée.
3. Valider un appui bref pour demander de l’aide, les relances et la confirmation Pushbullet globale. Les essais doivent être clairement identifiés comme TEST.
4. Ajouter l’annulation par maintien de dix secondes, puis vérifier l’arrêt des relances et l’information des proches.
5. À réception AliExpress, vérifier le bouton métallique et adapter le raccordement des LED ; conserver le comportement déjà testé. Valider ensuite la force d’appui et la fixation mécanique.

La LED RGB du stock ne sert pas à valider l’effort d’appui, l’étanchéité ou la tenue mécanique du bouton définitif. Les MOSFET AliExpress ne sont pas un préalable au démarrage du prototype.

Les exigences fonctionnelles et les vérifications avant usage restent décrites dans [SPECIFICATION.md](SPECIFICATION.md). Aucun schéma définitif ni programme embarqué n’est ajouté par cette note.
