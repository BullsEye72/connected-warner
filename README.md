# Prototype des boutons d’aide

Le [dashboard web](dashboard/README.md) est une application Next.js déployable
sur Vercel avec `dashboard` comme **Root Directory**. L'accès privé utilise
Google via Supabase ; une installation héberge un seul logement partagé dans
PostgreSQL. Le premier compte l'administre ; les suivants attendent son approbation
pour le consulter. La [configuration Supabase et Google](dashboard/README.md) et les
migrations SQL sont nécessaires. L'aperçu fictif reste accessible sur `/demo`.
L'API de présence et le module ESP32 sont prêts : après la deuxième migration,
créer une clé dans les détails du boîtier, la copier dans le profil privé et
transférer le programme. Le 16 octobre, le boîtier réel transmet sa première
présence avec une réponse HTTP 200 après correction de la connexion TCP ESP32.

Le panier retenu et le matériel disponible sont recensés dans [MATERIEL.md](MATERIEL.md).

Le 15 octobre, une [détection de sons forts répétés](SPECIFICATION.md#détection-sonore-en-complément-du-bouton-15-octobre-2026)
est envisagée pour demander de l’aide après une chute sans pouvoir atteindre le
bouton. Un lot de cinq modules GY-MAX4466 à 8 € est ajouté au panier. Le 16 octobre,
la logique de détection et son intégration au cycle d’aide sont préparées et
testées sur des niveaux simulés ; l’acquisition du micro reste à raccorder.
Les [décisions pour le boîtier](SPECIFICATION.md#boîtier--protection-simple-et-disposition-15-octobre-2026)
prévoient une fermeture à rebord, sans joint requis pour la première version,
un micro latéral et aucune ouverture sous la face posée sur le meuble ou le sol.

Un [retour sonore](SPECIFICATION.md#retour-sonore-des-demandes-15-octobre-2026)
est également prévu avec les speakers PC déjà en stock : séries de bips d’abord,
puis éventuellement de petites mélodies. La prise en compte locale et le `OK`
distant auront des signaux distincts ; le microphone ignorera les sons du boîtier.
Le séquenceur de bips est testé avec une sortie simulée ; la sortie physique
reste à raccorder. Les deux fonctions sont désactivées par défaut, sans broche
réservée. L’utilisateur annonce la commande des micros.

Une carte physique AYWHP ESP32-S3 N16R8 est maintenant reçue : MicroPython
1.29.0 avec PSRAM octale est installé et sa console répond sur COM4. Le
[profil carte et transfert MicroPico](carte/README.md) prépare les fichiers pour
VS Code. La LED RGB intégrée peut refléter la couleur du voyant du bouton ;
son cycle rouge/vert/bleu sur GPIO48 et l’appui bref sur le poussoir physique
GPIO12–GND sont validés par l’utilisateur, qui observe le rouge clignotant après
les relances simulées sans confirmation, puis valide l’annulation par maintien
de dix secondes et le retour au bleu. Le montage du voyant externe reste
à valider avant activation des sorties PWM.

Le [portail Wi-Fi local](carte/README.md#configuration-wi-fi-depuis-le-téléphone)
est activable en maintenant le bouton principal pendant trois secondes au
démarrage, jusqu’au blanc clignotant. Il vérifie puis
enregistre le réseau depuis une page sur téléphone. L’ouverture de la page, l’enregistrement
du réseau et sa reconnexion après redémarrage logiciel sont vérifiés.
Le portail ajoute le DNS local et les redirections permettant au téléphone de
proposer la page comme sur un Wi-Fi public ; l’utilisateur valide ce parcours
sur son téléphone. La reconfiguration se fait avec le gros bouton maintenu à
la mise sous tension, hors demande d’aide car le prototype conserve encore ses
demandes en RAM. Le portail permet aussi de nommer le boîtier et, après échec du
test, de confirmer une préconfiguration pour un réseau absent. Le geste de
configuration n’envoie aucune alerte d’aide.
L’utilisateur valide ce geste sur carte, avec blanc clignotant et portail accessible.

Sur carte, une connexion Wi-Fi absente donne du violet clignotant ; un signal
faible donne deux éclats violets sur le bleu au repos. La coupure et la reconnexion
réelles sont vérifiées, le rendu faible est essayé avec une valeur simulée.
Le bleu respire doucement sur dix secondes et le vert confirmé sur quatre secondes,
avec des maxima réduits et réglables pour l’essai nocturne. Les 258 tests locaux
passent. Le profil privé est maintenant en mode Pushbullet
réel : la carte vérifie le compte avec HTTPS (HTTP 200), sans notification au
démarrage. L’utilisateur valide l’aller-retour physique bouton → notification
TEST reçue → OK reconnu → voyant vert.

Le premier `OK` d’un contact actif arrête les relances et prévient les autres
contacts actifs : « C’est bon, [nom du contact] a répondu OK », avec boîtier et
référence. Cette note est envoyée en fond et son échec ne retire pas le vert.

La carte conserve désormais un [journal local des incidents](carte/README.md#journal-des-incidents) :
redémarrages et causes, derniers états et phase réseau en mémoire RTC, erreurs
techniques et points d’activité. Deux fichiers de 32 Kio sont récupérables par
USB avec `carte/lire_journal.py`. L’essai réel confirme la conservation de la
dernière phase après watchdog ; les essais volontaires sont comptés séparément.

Le [prototype MicroPython Wokwi](wokwi-test/README.md) contient un premier test de bouton et de couleurs validé par l’utilisateur, puis une machine à états avec modes réseau simulé et réel. Le mode réel utilise un jeton temporaire à renseigner dans `configuration.py`, envoie des messages TEST à un destinataire et lit les réponses OK autorisées. Deux interrupteurs à glissière commandent les coupures sur GPIO13 et GPIO14. La commande PWM est centralisée ; le voyant passe au cyan fixe pendant les envois AIDE/ANNULATION, garde la couleur de l’état sans clignoter pendant les lectures de fond, puis reprend son animation. Les gestes sur AIDE restent prioritaires sur les lectures réseau de fond, et un appui bref pendant une pause TLS est mémorisé. Un watchdog matériel redémarre la carte si la boucle des boutons reste bloquée soixante secondes. Cent trente-huit tests locaux passent. Les traces Wokwi de l’utilisateur valident la lecture HTTPS authentifiée, la réutilisation de connexion et la reconnaissance du OK ; son retour après l’ajout du cyan est positif. Les pauses TLS peuvent encore retarder la lecture des boutons et restent à mesurer sur carte.

La cible matérielle et les évolutions prévues sont décrites dans [SPECIFICATION.md](SPECIFICATION.md) : envoi à plusieurs proches avec confirmation globale par le premier `OK`, dashboard et signal de présence toutes les dix minutes, annulation par appui long de dix secondes, mises à jour OTA et vérifications du bouton RGB à anode commune. Ces fonctions supplémentaires ne sont pas encore intégrées au prototype ; il sélectionne actuellement un seul destinataire à la fois.

Ouvrir `pushbullet-boutons.html` par double-clic dans Chrome, Edge ou Firefox. Cette version envoie de véritables notifications Pushbullet. La simulation précédente reste dans `simulation-boutons.html`.

1. Sur https://www.pushbullet.com/#settings/account, créer un Access Token.
2. Coller ce jeton dans le champ de la page locale, puis cliquer sur « Vérifier le compte ». Cette vérification n’envoie aucun message.
3. Choisir tous les appareils du compte, un appareil précis ou l’adresse du compte Pushbullet d’un proche.
4. Appuyer sur Lit ou Salle de bains. Vérifier la réception sur le destinataire. Chaque notification porte la mention TEST et précise qu’aucune intervention n’est nécessaire.
5. Depuis le téléphone, envoyer une note Pushbullet contenant simplement `OK` : cela confirme toutes les demandes en cours. La casse et les espaces autour sont ignorés (`ok`, `Ok` et ` OK ` sont acceptés). Avec le même compte, l’envoyer vers le PC ou tous les appareils. Avec le compte d’un proche, répondre au compte expéditeur, indiqué dans la notification. Les voyants concernés passent au vert après réception et les relances s’arrêtent. Pour confirmer une seule demande, `OK CODE` reste disponible avec les huit caractères de sa notification.

La page vérifie les réponses toutes les cinq secondes lorsqu’une demande attend confirmation et que son boîtier est alimenté dans la simulation. La réponse doit être reçue sur le compte connecté. Pour un `OK` global, l’expéditeur doit correspondre à un destinataire autorisé pour au moins une demande en cours (même compte ou compte d’un proche) ; il peut alors confirmer toutes les demandes du logement déjà envoyées avant sa réponse, même si leurs destinataires diffèrent. Une réponse avec code confirme uniquement la demande correspondante et vérifie son destinataire. Lire, masquer ou supprimer la notification ne confirme rien. Une réponse ancienne ou déjà utilisée ne confirme pas une nouvelle demande. Les réponses peuvent être détectées même une fois le plafond des cinq notifications atteint.

« Terminer l’essai sur ce PC » reste disponible pour arrêter les essais manuellement. Cet arrêt local laisse le voyant bleu, avec une mention explicite d’absence de confirmation distante. La réponse du téléphone seule donne le voyant vert.

Le jeton reste en mémoire dans l’onglet. Il n’est ni intégré au fichier, ni enregistré dans le navigateur. Ne pas le coller dans le chat. « Effacer le jeton » arrête les relances et déconnecte la page. Fermer ou recharger la page efface la configuration.

Le réglage par défaut est cinq envois au total : le premier immédiatement, puis quatre relances espacées de deux minutes après acceptation de l’envoi précédent par Pushbullet. Cela correspond approximativement à 0, 2, 4, 6 et 8 minutes, hors délais réseau. Une option permet de désactiver les relances pour un essai à envoi unique. Une confirmation arrête les relances suivantes. Après le cinquième envoi sans confirmation, la demande reste en attente et la page continue à rechercher la réponse ; elle affiche explicitement que les relances sont terminées.

Les appuis répétés pendant un même essai ne créent pas d’autres notifications. En cas de résultat incertain, la page propose une reprise manuelle pour éviter de masquer le risque de doublon. Une requête déjà partie peut aboutir même si l’onglet interrompt son attente. Un changement du réglage de relance s’applique aux nouvelles demandes, pas à celles déjà lancées.

Avec une adresse de destinataire, Pushbullet utilise son compte s’il est disponible ; autrement, le service peut envoyer un email. Un succès de l’API signifie une acceptation par Pushbullet, pas une preuve de lecture ou de réception sur un téléphone.

La page doit rester ouverte pour les relances et la confirmation distante. La simulation d’alimentation agit sur chacun des deux boutons. Une réponse déjà envoyée pendant que son boîtier est débranché peut être retrouvée après rebranchement. Les demandes ne survivent pas au rechargement. Sur carte, la perte des demandes au redémarrage est acceptée par l’utilisateur le 15 octobre : le boîtier revient au repos et un nouvel appui permet de refaire une demande. Les réglages Wi-Fi et le nom restent enregistrés ; la persistance des incidents n’est pas prévue.

La confirmation par un compte distinct nécessite Pushbullet des deux côtés ; une simple réponse à l’email de repli n’est pas traitée par cette page. Une nouvelle demande créée après cette mise à jour est nécessaire : les notifications de l’ancienne version ne contiennent pas le code de confirmation.

Documentation officielle : https://docs.pushbullet.com/
