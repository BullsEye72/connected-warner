# Prototype des boutons d’aide

Le panier retenu et le matériel disponible sont recensés dans [MATERIEL.md](MATERIEL.md).

Le [prototype MicroPython Wokwi](wokwi-test/README.md) contient un premier test de bouton et de couleurs validé par l’utilisateur, puis une machine à états avec modes réseau simulé et réel. Le mode réel utilise un jeton temporaire à renseigner dans `configuration.py`, envoie des messages TEST à un destinataire et lit les réponses OK autorisées. Deux interrupteurs à glissière commandent les coupures sur GPIO13 et GPIO14. La commande PWM est centralisée ; le voyant passe au cyan fixe avant les communications et reprend ensuite la couleur de l’état. Cent treize tests locaux passent. Les traces Wokwi de l’utilisateur valident la lecture HTTPS authentifiée, la réutilisation de connexion et la reconnaissance du OK ; son retour après l’ajout du cyan est positif. Les pauses TLS peuvent encore retarder la lecture des boutons et restent à mesurer sur carte.

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

La page doit rester ouverte pour les relances et la confirmation distante. La simulation d’alimentation agit sur chacun des deux boutons. Une réponse déjà envoyée pendant que son boîtier est débranché peut être retrouvée après rebranchement. Les demandes ne survivent pas au rechargement. La mémoire après coupure et les boutons physiques ESP32 constituent les prochaines étapes.

La confirmation par un compte distinct nécessite Pushbullet des deux côtés ; une simple réponse à l’email de repli n’est pas traitée par cette page. Une nouvelle demande créée après cette mise à jour est nécessaire : les notifications de l’ancienne version ne contiennent pas le code de confirmation.

Documentation officielle : https://docs.pushbullet.com/
