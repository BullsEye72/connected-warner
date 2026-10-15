# A renseigner dans Wokwi. Ne pas coller le jeton dans la conversation.
# "simule" retrouve le faux reseau ; "reel" active de vrais messages TEST.
MODE_RESEAU = "reel"
JETON_PUSHBULLET = ""
DESTINATAIRE_EMAIL = ""  # Adresse de TON compte destinataire pour cet essai.
PIECE = "Lit"
SSID = "Wokwi-GUEST"
MOT_DE_PASSE_WIFI = ""
INTERVALLE_RELANCE_MS = 120_000  # Cinq envois maximum, premiere tentative immediate.
INTERVALLE_LECTURE_MS = 10_000  # Chaque lecture fige la boucle ; rester sous 30 s (connexion conservee).
DELAI_HTTP_MS = 12_000
DELAI_CONNEXION_MS = 30_000  # Premiere connexion et reconnexions TLS, budget total de la requete.
FICHIER_CA = "ca.pem"

# Logique sonore prete pour essais injectes ; adaptateurs materiels a raccorder.
DETECTION_SONORE_ACTIVE = False
BIPS_ACTIFS = False
