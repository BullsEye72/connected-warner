# Réactivité pendant les communications

## Décision actuelle : couleur fixe pendant les communications

Les traces ultérieures de l’utilisateur en version `MP-HTTPS-20261012-3` confirment que la connexion est réutilisée et que le OK est accepté. Elles mesurent une pause de 7 679 ms à la première négociation TLS, puis des pauses de 270 à 694 ms pendant les réponses. L’utilisateur a choisi de stabiliser le voyant avant les communications et de reprendre les animations après.

La version locale `MP-HTTPS-20261012-4` ajoute, avec `main.py`, un cyan fixe pendant les requêtes HTTPS. La boucle des commandes dispose de vingt millisecondes pour poser le PWM avant les opérations potentiellement bloquantes ; le drapeau est ensuite retiré après succès, erreur ou annulation. Les états et les temporisations restent inchangés. Le rendu Wokwi est à vérifier avec ces deux fichiers, et la réactivité des boutons reste à mesurer : la stabilisation du voyant ne rend pas TLS interruptible. Cinq tests supplémentaires passent, soit 113 au total. Aucun portage C++ n’est décidé.

## Constat du 12 octobre 2026

L’aller-retour Pushbullet réel fonctionne dans Wokwi : vérification du compte avec HTTP 200, réponse OK autorisée et passage à CONFIRMEE. Cependant, l’utilisateur observe une longue pause du voyant à la ligne « envoi HTTPS et negociation TLS », y compris après la proposition de réutiliser la connexion. La correction ne peut donc pas être considérée comme suffisante.

La réutilisation réduit le nombre de connexions lorsqu’elle fonctionne. Elle ne rend pas une nouvelle négociation TLS interruptible par la machine à états. Il reste à relever si « connexion HTTPS reutilisee » apparaît et les mesures « Pause de la boucle » ; la ligne actuelle ne distingue pas à elle seule attente réseau et calcul cryptographique.

## Exigence

Le traitement d’AIDE, du maintien d’annulation, des états et du voyant doit continuer pendant la résolution DNS, la connexion TCP, la négociation TLS, la lecture HTTP et les reconnexions. Cible initiale à mesurer : lecture des boutons toutes les 10 à 20 ms et anti-rebond de 30 ms. Aucun compteur de notifications acceptées ne doit progresser sur une simple mise en file ou un échec réseau.

Le clignotement doit continuer pendant ces essais, mais ce seul constat ne suffit pas : vérifier aussi qu’un appui bref est enregistré et qu’un maintien de dix secondes est traité pendant une communication lente. La transmission de l’annulation peut attendre la fin ou l’échec d’une requête déjà engagée ; son état local et la suspension des relances doivent être immédiats.

## Limites de la version MicroPython standard

Le transport actuel repose sur asyncio et partage sa boucle avec les boutons et la LED. Certaines opérations natives peuvent monopoliser cette boucle. L’implémentation ESP32 v1.28.0 active un verrou global Python (GIL), et les threads Python sont créés sur le même cœur que la tâche MicroPython. L’implémentation TLS appelle mbedTLS dans les lectures et écritures. Ajouter simplement un thread Python ne suffit donc pas à garantir l’indépendance des boutons pendant un calcul TLS natif.

Sources primaires : [asyncio et DNS bloquant](https://docs.micropython.org/en/latest/library/asyncio.html), [configuration ESP32 et GIL](https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/mpconfigport.h), [création des threads](https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/mpthreadport.c), [appels TLS natifs](https://github.com/micropython/micropython/blob/v1.28.0/extmod/modtls_mbedtls.c).

## Option proposée : C++/Arduino avec tâches FreeRTOS séparées

Conserver le matériel, les broches, les couleurs, les gestes et les messages TEST. Une tâche traite uniquement les entrées, la machine à états et le voyant. Une tâche réseau distincte prend en charge Wi-Fi, NTP, DNS, TLS et Pushbullet. Sur l’ESP32-S3 à deux cœurs, affecter ces tâches à des cœurs distincts ; les communications passent par des files bornées, sans attente réseau dans la tâche des boutons.

Les commandes et résultats portent l’identifiant du cycle : ignorer les confirmations d’un cycle annulé ou remplacé. Prévoir une annulation prioritaire, l’échec de mise en file, une file pleine et les résultats incertains des POST. Le réseau ne commande jamais directement les GPIO ni les états. La validation du certificat et du nom d’hôte reste obligatoire.

Sources : [tâches et affinité des cœurs ESP32-S3](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/freertos_idf.html). Cette organisation évite de dépendre du partage de l’interpréteur Python ; la latence doit néanmoins être mesurée dans Wokwi puis sur les cartes reçues.

Si cette option est retenue, commencer par un test limité : bouton et animation actifs pendant une vraie négociation HTTPS, ainsi qu’une tâche réseau volontairement lente. Reporter ensuite la machine à états déjà validée et vérifier les annulations, relances, confirmations et reprises de réseau. Une migration C++ implique de revoir ultérieurement l’OTA prévue pour des fichiers Python : elle deviendrait une mise à jour du firmware compilé.

## Si MicroPython reste requis

Continuer le diagnostic avec les traces de réutilisation et les pauses mesurées. Pour garantir une séparation équivalente, envisager un module réseau natif dans un firmware MicroPython personnalisé, ou un contrôleur réseau distinct. Ce sont des changements d’architecture ; ils ne sont pas encore développés. Ne pas présenter un simple timer, un thread Python ou une augmentation du délai HTTP comme une correction démontrée.

## État

L’utilisateur a répondu à la question de langage par un lien vers la documentation uasyncio v1.14. Ce lien n’est pas une autorisation de portage C++ ; on poursuit d’abord le diagnostic MicroPython. Les traces qu’il fournit montrent une nouvelle ouverture TCP/TLS à chaque GET, sans mention de réutilisation. Elles ne permettent pas d’établir si l’ancienne version est encore utilisée, si le serveur demande une fermeture ou si le transport est abandonné pour une autre raison.

La recommandation immédiate de changer de langage était prématurée : l’étape identifiée et les limites du modèle d’exécution ne prouvent pas à elles seules la cause précise ni qu’aucune correction MicroPython ne soit possible.

`pushbullet_reel.py` affiche désormais l’identifiant `MP-HTTPS-20261012-2`, les propriétés non sensibles de cadrage de la réponse (fermeture, présence de longueur, blocs), la raison d’abandon ou la conservation de connexion, et la durée de l’appel synchrone `Stream.write()` lorsqu’il prend au moins 250 ms. L’implémentation asyncio v1.28.0 tente une écriture immédiate du flux dans cette méthode avant son `drain()`, qui est lui une coroutine. Source : [Stream.write et drain](https://github.com/micropython/micropython/blob/v1.28.0/extmod/asyncio/stream.py). La documentation [uasyncio v1.14 fournie](https://docs.micropython.org/en/v1.14/library/uasyncio.html) décrit bien la concurrence des tâches, mais n’établit pas la réactivité d’un appel TLS natif particulier.

Aucun portage C++ ou firmware personnalisé n’a été effectué. La version locale MicroPython et ses 95 tests sont conservés ; les deux nouveaux tests portent sur la confidentialité du diagnostic de fermeture et la mesure d’une écriture synchrone. La dernière instrumentation est à recopier dans Wokwi ; le gel pendant TLS reste non résolu et le diagnostic exact est attendu.
