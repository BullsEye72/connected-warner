# Profil du premier essai physique : aucune notification reelle.
# Copier en configuration_privee.py pour les reglages personnels.
MODE_RESEAU = "simule"
PLATEFORME = "ESP32"
GPIO_RGB_CARTE = 48  # Bleu confirme sur la carte recue le 14 octobre 2026.
LUMINOSITE_RGB_CARTE = 32  # 0..255, sans changer les intensites du voyant externe.
RESPIRATION_VOYANTS = True
PERIODE_RESPIRATION_BLEU_MS = 10_000  # Cycle complet : 5 s descendant + 5 s montant.
PERIODE_RESPIRATION_VERT_MS = 4_000  # Vert = aide confirmee, pas traitement en cours.
INTENSITE_BLEU_REPOS = 64  # Maximum 1..255 avant luminosite carte : ici 8/255 sur NeoPixel.
INTENSITE_VERT_CONFIRME = 96  # Ici 12/255 sur NeoPixel ; minimum a 20 % du maximum.
VOYANT_BOUTON_ACTIF = False  # True apres validation du montage RGB externe.
ENTREES_TEST_ACTIVES = False  # Pas d'interrupteurs Wokwi sur la carte physique.
WATCHDOG_MS = 0  # Permet d'arreter le programme pendant les premiers essais.
PORTAIL_WIFI_ACTIF = True  # Bouton principal 3 s pendant le blanc au demarrage.
SURVEILLANCE_WIFI_REELLE = True  # Connexion et RSSI, meme avec Pushbullet simule.
SEUIL_WIFI_FAIBLE_DBM = -75  # Seuil d'essai, retour normal a -70 dBm.

# Preparation sonore : laisser False jusqu'au raccordement des adaptateurs
# d'acquisition du niveau et de sortie speaker, apres validation du montage.
# Aucun GPIO n'est reserve. Ces drapeaux seuls n'activent pas le materiel.
DETECTION_SONORE_ACTIVE = False
BIPS_ACTIFS = False
SON_SEUIL_HAUT = 12000  # Amplitude relative 0..65535, valeurs NON etalonnees.
SON_SEUIL_BAS = 6000
SON_NOMBRE_EVENEMENTS = 3
SON_FENETRE_MS = 15000
SON_DUREE_MIN_MS = 60
SON_RETOUR_BAS_MS = 80
SON_PAUSE_MICRO_MS = 300

# A renseigner localement avant un essai reel Pushbullet.
JETON_PUSHBULLET = ""
DESTINATAIRE_EMAIL = ""
DESTINATAIRES = []  # [{"nom": "Paul", "email": "paul@example.com", "actif": True}]
# La liste enregistree dans le portail prime ; l'ancien email reste un secours.
PIECE = "Lit"
SSID = ""
MOT_DE_PASSE_WIFI = ""
INTERVALLE_RELANCE_MS = 120_000
INTERVALLE_LECTURE_MS = 10_000
DELAI_HTTP_MS = 12_000
DELAI_CONNEXION_MS = 30_000
FICHIER_CA = "ca.pem"

# Suivi facultatif : copier les quatre lignes creees dans les details du boitier.
DASHBOARD_ACTIF = False
DASHBOARD_URL = "https://connected-warner.vercel.app"
DASHBOARD_APPAREIL_ID = "aefc072a-e80d-4969-9589-52e925164de1"
DASHBOARD_CLE = ""
