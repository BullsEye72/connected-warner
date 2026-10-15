"""Transport de TEST : vrai Wi-Fi, HTTPS et Pushbullet, sans secrets inclus."""
import json
import time
import sys
import journal as diagnostic
from contacts import contacts_configuration
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

HOTE_API = "api.pushbullet.com"
MAX_REPONSE = 96_000
INACTIVITE_HTTPS_MS = 30_000
CACHE_DNS_MS = 300_000
RETENUE_INTERACTION_MS = 2_000  # Lectures OK differees pendant un appui et juste apres.
RETENUE_MAX_MS = 20_000  # Plafond : un bouton bloque n'empeche pas de lire les OK.
CONTROLE_MIN_MS = 5_000  # Verification du compte apres erreur : 5, 10, 20, 40 puis 60 s.
CONTROLE_MAX_MS = 60_000
DELAI_CONNEXION_PAR_DEFAUT_MS = 30_000
VERSION_TRANSPORT = "MP-HTTPS-20261016-JOURNAL"


def maintenant_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.monotonic() * 1000)


def ecart_ms(a, b):
    return time.ticks_diff(a, b) if hasattr(time, "ticks_diff") else a - b


def valider_configuration(c):
    if not isinstance(c.JETON_PUSHBULLET, str) or not c.JETON_PUSHBULLET.strip():
        raise ValueError("Renseigner JETON_PUSHBULLET dans configuration.py.")
    if any(ord(x) < 33 or ord(x) > 126 for x in c.JETON_PUSHBULLET):
        raise ValueError("Jeton invalide : retirer les espaces et retours a la ligne.")
    if not contacts_configuration(c):
        raise ValueError("Renseigner DESTINATAIRES dans configuration.py ou le portail.")
    if c.INTERVALLE_RELANCE_MS < 10_000 or c.INTERVALLE_LECTURE_MS < 5_000:
        raise ValueError("Relances : minimum 10 s ; lecture des OK : minimum 5 s.")
    if not 3_000 <= c.DELAI_HTTP_MS <= 30_000:
        raise ValueError("DELAI_HTTP_MS doit etre compris entre 3000 et 30000.")
    if not 3_000 <= getattr(c, "DELAI_CONNEXION_MS", DELAI_CONNEXION_PAR_DEFAUT_MS) <= 30_000:
        raise ValueError("DELAI_CONNEXION_MS doit etre compris entre 3000 et 30000.")


def encoder_url(texte):
    return "".join(chr(x) if (65 <= x <= 90 or 97 <= x <= 122 or 48 <= x <= 57 or
                            x in (45, 46, 95, 126)) else "%%%02X" % x
                   for x in texte.encode())


def charger_certificats(contexte_tls, fichier):
    try:
        with open(fichier, "rb") as source:
            certificats_ca = source.read()
    except OSError as erreur:
        if erreur.args[0] != 2:
            raise
        try:
            import certificats
        except ImportError:
            raise ValueError("Certificats absents : ajouter ca.pem ou certificats.py au projet Wokwi.")
        certificats_ca = certificats.CA_PEM.encode()
    # MicroPython accepte le PEM en bytes ; CPython interprete les bytes
    # comme du DER et attend une chaine pour le PEM.
    if sys.implementation.name != "micropython":
        certificats_ca = certificats_ca.decode("ascii")
    contexte_tls.load_verify_locations(cadata=certificats_ca)


class ApiErreur(Exception):
    def __init__(self, message, incertain=False, statut=None):
        super().__init__(message)
        self.incertain = incertain
        self.statut = statut


class LectureDifferee(Exception):
    """La prochaine lecture est reportee, ou son cycle n'est plus actif."""


def decrire_erreur_transport(erreur, etape=None):
    """Diagnostic limite aux codes systeme et marqueurs TLS connus."""
    details = [type(erreur).__name__]
    codes = [str(x) for x in erreur.args if isinstance(x, int)]
    if codes:
        details.append("code=" + ",".join(codes))
    # Certains ports MicroPython ne donnent qu'un libelle TLS. Ne jamais
    # recopier un argument arbitraire, qui pourrait contenir un secret.
    marqueurs = ("SSL_CONN_EOF", "CERTIFICATE_VERIFY_FAILED", "CERT_VERIFY_FAILED",
                 "HANDSHAKE_FAILURE", "ECONNRESET", "ETIMEDOUT", "ENOMEM")
    for marqueur in marqueurs:
        if any(isinstance(x, str) and marqueur in x for x in erreur.args):
            details.append(marqueur)
    if etape:
        details.append("etape=" + etape)
    return " ; ".join(details)


def horodatage_ms(valeur):
    """Date serveur en millisecondes entieres, sans calcul flottant."""
    if isinstance(valeur, bool) or not isinstance(valeur, (str, int, float)):
        return None
    texte = str(valeur).lower()
    if not texte or len(texte) > 40:
        return None
    try:
        morceaux = texte.split("e")
        if len(morceaux) > 2:
            return None
        mantisse = morceaux[0]
        exposant = int(morceaux[1]) if len(morceaux) == 2 else 0
        if not -20 <= exposant <= 20 or mantisse.startswith("-") or mantisse.startswith("+"):
            return None
        parties = mantisse.split(".")
        if len(parties) > 2 or not all(p and all("0" <= x <= "9" for x in p) for p in parties):
            return None
        chiffres = "".join(parties)
        decimales = len(parties[1]) if len(parties) == 2 else 0
        puissance = 3 + exposant - decimales
        nombre = int(chiffres)
        resultat = nombre * 10 ** puissance if puissance >= 0 else nombre // 10 ** (-puissance)
        return resultat if 0 < resultat <= 4_102_444_800_000 else None
    except (ValueError, OverflowError):
        return None


def decoder_json_serveur(contenu):
    """Preserver les nombres created/modified AVANT le json.loads float32."""
    texte = contenu.decode()
    segments = []
    dernier = 0
    i = 0
    while i < len(texte):
        debut = texte.find('"', i)
        if debut < 0:
            break
        i = debut + 1
        while True:
            i = texte.find('"', i)
            if i < 0:
                raise ApiErreur("JSON serveur incomplet.")
            k = i - 1
            while k > debut and texte[k] == "\\":
                k -= 1
            if (i - 1 - k) % 2 == 0:
                break
            i += 1
        i += 1
        if texte[debut:i] not in ('"created"', '"modified"'):
            continue
        j = i
        while j < len(texte) and texte[j] in " \t\r\n":
            j += 1
        if j >= len(texte) or texte[j] != ":":
            continue
        j += 1
        while j < len(texte) and texte[j] in " \t\r\n":
            j += 1
        k = j
        while k < len(texte) and texte[k] in "0123456789.eE+-":
            k += 1
        if k > j:
            segments.append(texte[dernier:j])
            segments.append('"' + texte[j:k] + '"')
            dernier = k
            i = k
    segments.append(texte[dernier:])
    return json.loads("".join(segments))


async def lire_reponse_http(lecteur, diagnostic=None):
    if diagnostic:
        diagnostic("lecture du statut HTTP")
    ligne = await lecteur.readline()
    morceaux = ligne.split()
    if len(morceaux) < 2 or not morceaux[0].startswith(b"HTTP/"):
        raise ApiErreur("Reponse HTTP invalide.")
    statut = int(morceaux[1])
    version_http = morceaux[0]
    if diagnostic:
        diagnostic("lecture des entetes (HTTP %d)" % statut)
    entetes = {}
    taille = len(ligne)
    while True:
        ligne = await lecteur.readline()
        taille += len(ligne)
        if taille > 16_384 or not ligne:
            raise ApiErreur("Entetes HTTP incomplets ou trop longs.")
        if ligne in (b"\r\n", b"\n"):
            break
        cle, valeur = ligne.decode().split(":", 1)
        entetes[cle.strip().lower()] = valeur.strip()
    if version_http != b"HTTP/1.1":
        entetes.setdefault("connection", "close")
    contenu = bytearray()
    if diagnostic:
        diagnostic("lecture du corps HTTP")
    if "chunked" in entetes.get("transfer-encoding", "").lower():
        while True:
            longueur = int((await lecteur.readline()).split(b";", 1)[0].strip(), 16)
            if longueur == 0:
                # Consommer aussi la fin des blocs et les eventuels trailers.
                # Sinon la prochaine reponse sur cette connexion commencerait
                # par une ligne vide provenant de la reponse precedente.
                while True:
                    ligne = await lecteur.readline()
                    taille += len(ligne)
                    if not ligne or taille > 16_384:
                        raise ApiErreur("Fin de reponse HTTP incomplete ou trop longue.")
                    if ligne in (b"\r\n", b"\n"):
                        break
                break
            if longueur < 0 or len(contenu) + longueur > MAX_REPONSE:
                raise ApiErreur("Reponse HTTP trop grande.")
            contenu.extend(await lecteur.readexactly(longueur))
            if await lecteur.readexactly(2) != b"\r\n":
                raise ApiErreur("Bloc HTTP invalide.")
    elif "content-length" in entetes:
        longueur = int(entetes["content-length"])
        if not 0 <= longueur <= MAX_REPONSE:
            raise ApiErreur("Reponse HTTP trop grande.")
        contenu.extend(await lecteur.readexactly(longueur))
    else:
        while True:
            morceau = await lecteur.read(1024)
            if not morceau:
                break
            contenu.extend(morceau)
            if len(contenu) > MAX_REPONSE:
                raise ApiErreur("Reponse HTTP trop grande.")
    # Les erreurs HTTP ne necessitent pas de lire/afficher leur contenu prive.
    donnees = decoder_json_serveur(contenu) if contenu and statut == 200 else {}
    return statut, entetes, donnees


class SuiviPushbullet:
    """Reponses autorisees, dates serveur, codes uniques et OK deja consommes."""

    def __init__(self, destinataire, piece, session, plateforme="Wokwi"):
        self.destinataire = destinataire.strip().lower()
        self.piece = piece
        self.session = session
        self.plateforme = plateforme
        self.utilisateur = None
        self.email_expediteur = ""
        self.destinataire_iden = None
        self.courante = None
        self.demandes = {}
        self.reponses_utilisees = set()

    def identifier(self, utilisateur):
        if not utilisateur.get("iden") or not utilisateur.get("email"):
            raise ApiErreur("Identite Pushbullet incomplete.")
        self.utilisateur = utilisateur["iden"]
        self.email_expediteur = utilisateur["email"].lower()

    def ouvrir(self, demande):
        self.courante = demande
        if demande not in self.demandes:
            self.demandes[demande] = {"date": None, "compteur": 0, "terminee": False}

    def fermer(self, demande):
        if demande in self.demandes:
            self.demandes[demande]["terminee"] = True

    def code(self, demande):
        return "%s-%d" % (self.session, demande)

    def accepte(self, demande, reponse):
        if not reponse.get("iden"):
            raise ApiErreur("Acceptation sans identifiant : resultat incertain.", True)
        etat = self.demandes[demande]
        etat["compteur"] += 1
        date = horodatage_ms(reponse.get("created"))
        if date is not None and etat["date"] is None:
            etat["date"] = date
        # Le destinataire effectif est fourni par la reponse TLS verifiee du
        # POST adresse a l'email configure. Eviter les ambiguities d'alias.
        destinataire = reponse.get("receiver_iden")
        if isinstance(destinataire, str) and destinataire:
            self.destinataire_iden = destinataire

    def charge(self, nature, demande):
        code = self.code(demande)
        if nature == "AIDE":
            numero = self.demandes[demande]["compteur"] + 1
            titre = "[TEST AIDE] %s (%s)" % (self.piece, self.plateforme)
            corps = ("TEST - aucune intervention necessaire.\nEssai du bouton : %s.\n"
                     "Reference : %s. Notification %d sur 5.\n\n"
                     "Repondre au compte expediteur : OK\nOu : OK %s") % (
                         self.piece, code, numero, code)
        else:
            titre = "[TEST ANNULATION] %s (%s)" % (self.piece, self.plateforme)
            corps = ("TEST - aucune intervention necessaire.\n%s - reference %s.\n"
                     "Demande annulee : Tout compte fait, tout va bien.") % (self.piece, code)
        return {"type": "note", "email": self.destinataire, "title": titre, "body": corps}

    def date_lecture(self):
        etat = self.demandes.get(self.courante)
        if etat and not etat["terminee"] and etat["date"] is not None:
            # Une seconde de recouvrement ; la comparaison created precise
            # rejette quand meme les anciens OK. Jamais de float dans l'URL.
            return max(0, (etat["date"] - 1000) // 1000)
        return None

    def motif_rejet(self, push, date_minimale=None):
        demande = self.courante
        etat = self.demandes.get(demande)
        if not etat or etat["terminee"]:
            return "aucune demande active"
        date_alerte = date_minimale if date_minimale is not None else etat["date"]
        if date_alerte is None:
            return "date de l'alerte absente"
        if not push.get("iden"):
            return "identifiant absent"
        if push["iden"] in self.reponses_utilisees:
            return "OK deja utilise"
        if not push.get("active") or push.get("type") != "note":
            return "message supprime ou autre type"
        if push.get("receiver_iden") != self.utilisateur:
            return "OK adresse a un autre compte"
        date = horodatage_ms(push.get("created"))
        if date is None:
            return "date du OK invalide"
        if date < date_alerte:
            return "OK anterieur a cette alerte"
        if (self.destinataire == self.email_expediteur or
                (self.destinataire_iden is not None and self.destinataire_iden == self.utilisateur)):
            autorise = push.get("direction") == "self" and push.get("sender_iden") == self.utilisateur
        elif self.destinataire_iden is not None:
            autorise = push.get("direction") == "incoming" and push.get("sender_iden") == self.destinataire_iden
        else:
            adresses = (push.get("sender_email_normalized"), push.get("sender_email"))
            autorise = push.get("direction") == "incoming" and any(
                isinstance(email, str) and email.strip().lower() == self.destinataire for email in adresses)
        if not autorise:
            return "expediteur ou sens du message non autorise"
        texte = push.get("body")
        if not isinstance(texte, str):
            return "texte du OK absent"
        if texte.strip().upper() not in ("OK", "OK " + self.code(demande).upper()):
            return "texte ou reference differente"
        return None

    def examiner(self, push, date_minimale=None):
        if self.motif_rejet(push, date_minimale) is not None:
            return None
        demande = self.courante
        self.reponses_utilisees.add(push["iden"])
        self.fermer(demande)
        return demande


class SuiviGroupe:
    """Un suivi autorise par destinataire, avec une reference commune."""

    def __init__(self, contacts, piece, session, plateforme="ESP32"):
        self.contacts = [c for c in contacts if c["actif"]]
        self.suivis = {c["email"]: SuiviPushbullet(c["email"], piece, session, plateforme)
                       for c in self.contacts}
        self.courante = None
        self.repondants = {}

    def identifier(self, utilisateur):
        for suivi in self.suivis.values():
            suivi.identifier(utilisateur)

    def ouvrir(self, demande):
        self.courante = demande
        for suivi in self.suivis.values():
            suivi.ouvrir(demande)
            etat = suivi.demandes[demande]
            for cle, valeur in (("dernier_envoi", None), ("dernier_essai", None),
                                ("bloque", False), ("a_pu_recevoir", False),
                                ("annulation_acceptee", False), ("erreur", None), ("incertain", False)):
                if cle not in etat:
                    etat[cle] = valeur

    def fermer(self, demande):
        for suivi in self.suivis.values():
            suivi.fermer(demande)

    def code(self, demande):
        return next(iter(self.suivis.values())).code(demande)

    def etats(self, demande):
        return {email: s.demandes[demande] for email, s in self.suivis.items() if demande in s.demandes}

    def terminee(self, demande):
        etats = self.etats(demande)
        return bool(etats) and all(e["terminee"] for e in etats.values())

    def compteur_max(self, demande):
        valeurs = [e["compteur"] for e in self.etats(demande).values()]
        return max(valeurs) if valeurs else 0

    def plafond_atteint(self, demande):
        etats = self.etats(demande)
        return bool(etats) and any(e["compteur"] for e in etats.values()) and all(
            e["compteur"] >= 5 or e["bloque"] for e in etats.values())

    def cibles(self, nature, demande, maintenant, intervalle):
        resultat = []
        etats = self.etats(demande)
        for contact in self.contacts:
            email = contact["email"]
            if email not in etats:
                continue
            etat = etats[email]
            if etat["bloque"]:
                continue
            if nature == "AIDE":
                if etat["terminee"] or etat["compteur"] >= 5:
                    continue
                dernier = etat["dernier_envoi"]
                if dernier is not None and ecart_ms(maintenant, dernier) < intervalle:
                    continue
            elif not etat["a_pu_recevoir"] or etat["annulation_acceptee"]:
                continue
            essai = etat["dernier_essai"]
            if essai is None or ecart_ms(maintenant, essai) >= 2000:
                resultat.append(email)
        return resultat

    def annulation_terminee(self, demande):
        return all(not e["a_pu_recevoir"] or e["annulation_acceptee"] or e["bloque"]
                   for e in self.etats(demande).values())

    def charge(self, nature, demande, email):
        return self.suivis[email].charge(nature, demande)

    def accepte(self, demande, reponse, email):
        self.suivis[email].accepte(demande, reponse)

    def date_lecture(self):
        dates = [s.date_lecture() for s in self.suivis.values() if s.date_lecture() is not None]
        return min(dates) if dates else None

    def motif_rejet(self, push):
        dates = [e["date"] for e in self.etats(self.courante).values() if e["date"] is not None]
        date = min(dates) if dates else None
        motifs = [s.motif_rejet(push, date) for s in self.suivis.values()]
        return None if None in motifs else "aucun contact autorise pour cette demande"

    def examiner(self, push):
        dates = [e["date"] for e in self.etats(self.courante).values() if e["date"] is not None]
        date = min(dates) if dates else None
        for contact in self.contacts:
            suivi = self.suivis[contact["email"]]
            demande = suivi.examiner(push, date)
            if demande is not None:
                self.repondants[demande] = contact
                self.fermer(demande)
                return demande
        return None

    def messages_confirmation(self, demande):
        repondant = self.repondants.get(demande)
        if repondant is None:
            return []
        suivi = self.suivis[repondant["email"]]
        return [{"type": "note", "email": contact["email"],
                 "title": "[TEST REPONSE] %s (%s)" % (suivi.piece, suivi.plateforme),
                 "body": ("TEST - aucune intervention necessaire.\n%s - reference %s.\n"
                          "C’est bon, %s a répondu OK.\nLes relances sont arrêtées.") % (
                              suivi.piece, suivi.code(demande), repondant["nom"])}
                for contact in self.contacts if contact["email"] != repondant["email"]]


async def synchroniser_horloge():
    """NTP public avant TLS ; attente UDP bornee, pas de secret transmis."""
    import socket
    import struct
    from machine import RTC
    adresse = socket.getaddrinfo("pool.ntp.org", 123, 0, socket.SOCK_DGRAM)[0][-1]
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    try:
        sock.connect(adresse)
        paquet = bytearray(48)
        paquet[0] = 0x23
        sock.send(paquet)
        debut = maintenant_ms()
        while ecart_ms(maintenant_ms(), debut) < 5_000:
            try:
                reponse = sock.recv(48)
            except OSError as erreur:
                if erreur.args[0] not in (11, 35, 10035):
                    raise
                await asyncio.sleep(0.05)
                continue
            if len(reponse) < 48 or reponse[0] & 7 != 4 or reponse[1] == 0:
                raise ApiErreur("Reponse NTP invalide.")
            secondes = struct.unpack("!I", reponse[40:44])[0]
            delta = 3155673600 if time.gmtime(0)[0] == 2000 else 2208988800
            tm = time.gmtime(secondes - delta)
            if not 2025 <= tm[0] <= 2100:
                raise ApiErreur("Date NTP invalide.")
            RTC().datetime((tm[0], tm[1], tm[2], tm[6], tm[3], tm[4], tm[5], 0))
            return
        raise ApiErreur("Delai NTP depasse.")
    finally:
        sock.close()


class ReseauReel:
    reel = True

    def __init__(self, configuration, journal=print):
        import network
        import ssl
        import os
        import binascii
        self.c = configuration
        self.journal = journal
        self.journal("[REEL] Transport %s ; asyncio ; connexion HTTPS persistante." % VERSION_TRANSPORT)
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.wifi = True
        self.pushbullet = True
        self.pret = False
        self.horloge_prete = False
        self.erreur_permanente = False
        self.pause_depuis = None
        self.pause_ms = 0
        self.en_cours = None
        self.communication_en_cours = False
        self.lecture_de_fond = False
        self.echecs = 0
        self.resultats = []
        self.confirmations = []
        self.annonces = []
        self.tache_envoi = None
        self.connexion_depuis = None
        self.dernier_controle = None
        self.dernier_ok = None
        self.derniere_interaction = None
        self.retenue_depuis = None
        self.verrou = asyncio.Lock()
        self.connexion_https = None
        self.derniere_utilisation_https = None
        self.connexion_perimee = False
        self.adresse_api = None
        self.date_dns = None
        self.suivi = SuiviGroupe(contacts_configuration(self.c), self.c.PIECE,
                                    binascii.hexlify(os.urandom(6)).decode().upper(),
                                    getattr(self.c, "PLATEFORME", "Wokwi"))
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.tls.verify_mode = ssl.CERT_REQUIRED
        charger_certificats(self.tls, self.c.FICHIER_CA)

    def en_pause(self):
        return self.pause_depuis is not None and ecart_ms(maintenant_ms(), self.pause_depuis) < self.pause_ms

    def disponible(self):
        return (self.wifi and self.pushbullet and self.wlan.isconnected() and self.pret and
                not self.erreur_permanente and not self.en_pause())

    def obstacle(self):
        if not self.wifi or not self.wlan.isconnected():
            return "Wi-Fi non connecte"
        if self.erreur_permanente:
            return "configuration ou jeton refuse : corriger puis relancer"
        return "Pushbullet suspendu, verification en cours ou limitation temporaire"

    def configurer(self, wifi=None, pushbullet=None):
        if wifi is not None and wifi != self.wifi:
            self.wifi = wifi
            self.connexion_perimee = True
            self.adresse_api = None
            self.wlan.active(wifi)
            self.connexion_depuis = None
            self.journal("[REEL] Interrupteur Wi-Fi : " + ("ON" if wifi else "OFF"))
        if pushbullet is not None and pushbullet != self.pushbullet:
            self.pushbullet = pushbullet
            self.journal("[REEL] Interrupteur Pushbullet : " + ("ON" if pushbullet else "OFF"))

    async def fermer_https(self, raison="arret ou requete interrompue"):
        connexion = getattr(self, "connexion_https", None)
        self.connexion_https = None
        self.derniere_utilisation_https = None
        if connexion is not None:
            if getattr(getattr(self, "c", None), "TRACE_HTTPS", True):
                self.journal("[HTTPS] Fermeture de la connexion : " + raison)
            try:
                connexion[1].close()
                await asyncio.wait_for(connexion[1].wait_closed(), 1)
            except Exception:
                # Une erreur de fermeture ne masque pas l'erreur initiale.
                pass

    async def ouvrir_https(self):
        import socket
        maintenant = maintenant_ms()
        if (getattr(self, "adresse_api", None) is None or
                ecart_ms(maintenant, self.date_dns) >= CACHE_DNS_MS):
            self.etape_http = "resolution DNS"
            diagnostic.contexte(phase=self.etape_http)
            # Cette resolution reste bloquante dans MicroPython, mais n'est
            # plus repetee a chaque lecture. Conserver le nom pour TLS/SNI.
            self.adresse_api = socket.getaddrinfo(HOTE_API, 443, 0, socket.SOCK_STREAM)[0][-1][0]
            self.date_dns = maintenant_ms()
        return await asyncio.open_connection(self.adresse_api, 443, ssl=self.tls,
                                             server_hostname=HOTE_API)

    async def https(self, methode, chemin, corps=None):
        maintenant = maintenant_ms()
        derniere = getattr(self, "derniere_utilisation_https", None)
        if getattr(self, "connexion_perimee", False):
            await self.fermer_https("changement de Wi-Fi")
        elif derniere is not None and ecart_ms(maintenant, derniere) >= INACTIVITE_HTTPS_MS:
            await self.fermer_https("inactivite de 30 secondes")
        self.connexion_perimee = False
        connexion = getattr(self, "connexion_https", None)
        reutilisee = connexion is not None
        try:
            if not reutilisee:
                self.etape_http = "ouverture TCP/TLS"
                self.tracer_https(methode, chemin, self.etape_http)
                connexion = await self.ouvrir_https()
                self.connexion_https = connexion
            else:
                self.tracer_https(methode, chemin, "connexion HTTPS reutilisee")
            lecteur, ecrivain = connexion
            contenu = json.dumps(corps).encode() if corps is not None else b""
            entetes = ("%s /v2/%s HTTP/1.1\r\nHost: %s\r\nAccess-Token: %s\r\n"
                       "Accept: application/json\r\nAccept-Encoding: identity\r\nConnection: keep-alive\r\n"
                       "Content-Type: application/json\r\nContent-Length: %d\r\n\r\n") % (
                           methode, chemin, HOTE_API, self.c.JETON_PUSHBULLET, len(contenu))
            self.etape_http = "envoi HTTPS" if reutilisee else "envoi HTTPS et negociation TLS"
            self.tracer_https(methode, chemin, self.etape_http)
            debut_ecriture = maintenant_ms()
            ecrivain.write(entetes.encode() + contenu)
            duree_ecriture = ecart_ms(maintenant_ms(), debut_ecriture)
            if duree_ecriture >= 250:
                self.journal("[DIAGNOSTIC] Appel TLS write sans await : %d ms." % duree_ecriture)
            self.etape_http = "attente TLS/drain"
            self.tracer_https(methode, chemin, self.etape_http)
            await ecrivain.drain()
            def progres(etape):
                self.etape_http = etape
                self.tracer_https(methode, chemin, etape)
            reponse = await lire_reponse_http(lecteur, progres)
            entetes_reponse = reponse[1]
            fermeture = "close" in entetes_reponse.get("connection", "").lower()
            longueur_connue = "content-length" in entetes_reponse
            blocs = "chunked" in entetes_reponse.get("transfer-encoding", "").lower()
            self.tracer_https(methode, chemin, "fin HTTP : fermeture=%s ; longueur=%s ; blocs=%s" % (
                fermeture, longueur_connue, blocs))
            if fermeture:
                await self.fermer_https("serveur demande Connection: close (ou HTTP/1.0 sans keep-alive)")
            elif not (longueur_connue or blocs):
                await self.fermer_https("reponse delimitee par fermeture, sans longueur ni blocs")
            else:
                self.derniere_utilisation_https = maintenant_ms()
                self.tracer_https(methode, chemin, "connexion conservee pour la prochaine requete")
            return reponse
        except BaseException:
            # Inclut l'annulation : un flux partiellement lu/ecrit n'est
            # jamais reutilise pour la requete suivante. Pas de POST repete ici.
            await self.fermer_https("erreur ou annulation de la requete")
            raise

    def tracer_https(self, methode, chemin, etape):
        ressource = chemin.split("?", 1)[0]
        diagnostic.contexte(phase=etape, methode=methode,
                             ressource=ressource if ressource in ("pushes", "users/me") else "autre")
        if getattr(self.c, "TRACE_HTTPS", True):
            self.journal("[HTTPS] %s %s : %s" % (methode, chemin.split("?", 1)[0], etape))

    def delai_https_ms(self):
        derniere = getattr(self, "derniere_utilisation_https", None)
        reutilisable = (getattr(self, "connexion_https", None) is not None and
                       not getattr(self, "connexion_perimee", False) and
                       (derniere is None or ecart_ms(maintenant_ms(), derniere) < INACTIVITE_HTTPS_MS))
        if reutilisable:
            return self.c.DELAI_HTTP_MS
        return max(self.c.DELAI_HTTP_MS, getattr(
            self.c, "DELAI_CONNEXION_MS", DELAI_CONNEXION_PAR_DEFAUT_MS))

    async def api(self, methode, chemin, corps=None, fond=False):
        # Cyan pour les envois voulus par l'utilisateur (AIDE, ANNULATION) ;
        # une requete de fond fige seulement l'animation sur la couleur d'etat.
        drapeau = "lecture_de_fond" if fond else "communication_en_cours"
        async with self.verrou:
            if not self.wifi or not self.pushbullet or not self.wlan.isconnected():
                raise ApiErreur("Transmission suspendue avant requete.")
            if fond and self.differer_lecture():
                raise LectureDifferee()

            async def transmettre():
                # Recontroler dans la tache creee par wait_for, apres le
                # passage des boutons pendant la preparation du voyant.
                # Cette garde protege aussi chaque page de reponses.
                if fond:
                    if self.differer_lecture():
                        raise LectureDifferee()
                    self.retenue_depuis = None  # Consommer l'autorisation.
                return await self.https(methode, chemin, corps)

            setattr(self, drapeau, True)
            delai_http = self.c.DELAI_HTTP_MS
            try:
                # La boucle des boutons tourne toutes les 5 ms. Lui laisser
                # poser le voyant AVANT DNS/TLS, meme s'ils bloquent ensuite.
                await asyncio.sleep(0.02)
                delai_http = self.delai_https_ms()
                self.tracer_https(methode, chemin, "budget de la requete : %d ms" % delai_http)
                statut, entetes, donnees = await asyncio.wait_for(
                    transmettre(), delai_http / 1000)
            except asyncio.TimeoutError:
                diagnostic.evenement("http_erreur", classe="TimeoutError")
                raise ApiErreur("Delai HTTPS depasse (%d ms) : %s." % (
                    delai_http, getattr(self, "etape_http", "connexion/lecture")),
                    methode == "POST")
            except OSError as erreur:
                diagnostic.evenement("http_erreur", classe="OSError")
                raise ApiErreur("Connexion HTTPS indisponible : " + decrire_erreur_transport(
                    erreur, getattr(self, "etape_http", "connexion/lecture")), methode == "POST")
            except ApiErreur as erreur:
                diagnostic.evenement("http_erreur", classe="ApiErreur", statut=erreur.statut)
                raise
            finally:
                setattr(self, drapeau, False)
        if statut != 200:
            diagnostic.evenement("http_erreur", classe="HTTP", statut=statut)
            if statut in (401, 403) or (methode != "POST" and statut in (400, 404)):
                self.erreur_permanente = True
            if statut == 429:
                try:
                    secondes = int(entetes.get("retry-after", "60"))
                except ValueError:
                    secondes = 60
                self.pause_depuis = maintenant_ms()
                self.pause_ms = max(30, min(3600, secondes)) * 1000
            raise ApiErreur("HTTP %d : transmission non confirmee." % statut,
                            methode == "POST" and statut >= 500, statut=statut)
        return donnees

    def commencer(self, nature, demande, maintenant):
        if not self.disponible() or self.en_cours is not None:
            return False
        if nature == "AIDE":
            self.suivi.ouvrir(demande)
        else:
            self.suivi.fermer(demande)
        if isinstance(self.suivi, SuiviGroupe):
            cibles = self.suivi.cibles(nature, demande, maintenant, self.c.INTERVALLE_RELANCE_MS)
            if not cibles and not (nature == "ANNULATION" and self.suivi.annulation_terminee(demande)):
                return False
        requete = {"nature": nature, "demande": demande, "debut": maintenant, "erreur": None}
        self.en_cours = requete
        self.tache_envoi = asyncio.create_task(self.envoyer(requete))
        self.journal("[REEL] Envoi TEST %s, reference %s..." % (nature, self.suivi.code(demande)))
        return True

    async def envoyer(self, requete):
        if isinstance(self.suivi, SuiviGroupe):
            await self.envoyer_groupe(requete)
            return
        try:
            donnees = await self.api("POST", "pushes", self.suivi.charge(requete["nature"], requete["demande"]))
            if requete["nature"] == "AIDE":
                self.suivi.accepte(requete["demande"], donnees)
            elif not donnees.get("iden"):
                raise ApiErreur("Annulation sans identifiant : resultat incertain.", True)
            requete["accepte"] = True
            if requete["nature"] == "AIDE" and self.suivi.date_lecture() is None:
                self.journal("[REEL] Alerte acceptee, mais date absente : pas de confirmation distante possible.")
        except asyncio.CancelledError:
            requete["accepte"] = False
            requete["erreur"] = "requete interrompue : resultat incertain"
            self.journal("[REEL] Requete interrompue ; une acceptation reste possible.")
        except Exception as erreur:
            requete["accepte"] = False
            incertain = not isinstance(erreur, ApiErreur) or erreur.incertain
            # Pas de contenu de reponse, d'entete ou de jeton dans les logs.
            requete["erreur"] = (str(erreur) if isinstance(erreur, ApiErreur) else
                                 decrire_erreur_transport(erreur))
            if incertain:
                requete["erreur"] += " ; resultat incertain, doublon possible au reessai"
            self.pret = False
        finally:
            if not requete.get("obsolete"):
                self.resultats.append(requete)

    def doit_envoyer_aide(self, demande, maintenant):
        if not isinstance(self.suivi, SuiviGroupe):
            return True
        if not self.suivi.etats(demande):
            return True
        return bool(self.suivi.cibles("AIDE", demande, maintenant, self.c.INTERVALLE_RELANCE_MS))

    def plafond_atteint(self, demande):
        if isinstance(self.suivi, SuiviGroupe):
            return self.suivi.plafond_atteint(demande)
        return self.suivi.demandes.get(demande, {}).get("compteur", 0) >= 5

    async def envoyer_groupe(self, requete):
        nature, demande = requete["nature"], requete["demande"]
        requete["accepte"] = False
        acceptes, email_courant = 0, None
        try:
            cibles = self.suivi.cibles(nature, demande, maintenant_ms(), self.c.INTERVALLE_RELANCE_MS)
            for email in cibles:
                if (requete.get("obsolete") or (nature == "AIDE" and self.suivi.terminee(demande)) or
                        not self.disponible()):
                    break
                email_courant = email
                etat = self.suivi.etats(demande)[email]
                etat["dernier_essai"] = maintenant_ms()
                if nature == "AIDE":
                    etat["a_pu_recevoir"] = True
                try:
                    donnees = await self.api("POST", "pushes", self.suivi.charge(nature, demande, email))
                    if nature == "AIDE":
                        self.suivi.accepte(demande, donnees, email)
                        etat["dernier_envoi"] = maintenant_ms()
                    elif donnees.get("iden"):
                        etat["annulation_acceptee"] = True
                    else:
                        raise ApiErreur("Annulation sans identifiant : resultat incertain.", True)
                    etat["erreur"], etat["incertain"] = None, False
                    acceptes += 1
                    rang = [c["email"] for c in self.suivi.contacts].index(email) + 1
                    self.journal("[CONTACT %d] %s accepte%s." % (rang, nature,
                                 " (%d/5)" % etat["compteur"] if nature == "AIDE" else ""))
                except asyncio.CancelledError:
                    raise
                except Exception as erreur:
                    etat["incertain"] = not isinstance(erreur, ApiErreur) or erreur.incertain
                    etat["erreur"] = str(erreur) if isinstance(erreur, ApiErreur) else decrire_erreur_transport(erreur)
                    if nature == "AIDE" and not etat["incertain"] and etat["compteur"] == 0:
                        etat["a_pu_recevoir"] = False
                    etat["bloque"] = isinstance(erreur, ApiErreur) and erreur.statut in (400, 404)
                    rang = [c["email"] for c in self.suivi.contacts].index(email) + 1
                    self.journal("[CONTACT %d] %s%s" % (rang, etat["erreur"],
                                 " ; resultat incertain, doublon possible au reessai" if etat["incertain"] else ""))
                    requete["erreur"] = "un ou plusieurs contacts non confirmes"
                email_courant = None
                await asyncio.sleep(0)
            requete["envois"] = self.suivi.compteur_max(demande)
            requete["accepte"] = acceptes > 0 if nature == "AIDE" else self.suivi.annulation_terminee(demande)
            etats = self.suivi.etats(demande)
            requete["contacts"] = [{"email": email, "envois": e["compteur"], "erreur": e["erreur"],
                                    "incertain": e["incertain"], "bloque": e["bloque"],
                                    "annulation_acceptee": e["annulation_acceptee"]} for email, e in etats.items()]
            requete["partiel"] = any(e["erreur"] for e in etats.values())
            self.journal("[REEL] %s : %d acceptation(s) dans ce passage ; %d contact(s) ; %d en echec." % (
                nature, acceptes, len(etats), sum(1 for e in etats.values() if e["erreur"])))
            if not acceptes and cibles and not any(e["bloque"] for e in etats.values()):
                self.pret = False
        except asyncio.CancelledError:
            if email_courant is not None:
                etat = self.suivi.etats(demande)[email_courant]
                etat["incertain"], etat["erreur"] = True, "requete interrompue : resultat incertain"
            requete["erreur"] = "requete interrompue : resultat incertain"
        finally:
            if not requete.get("obsolete"):
                self.resultats.append(requete)

    def resultat(self, maintenant):
        if not self.resultats:
            return None
        resultat = self.resultats.pop(0)
        if self.en_cours is resultat:
            self.en_cours = None
            self.tache_envoi = None
        return resultat

    def interrompre_aide(self):
        self.suivi.fermer(self.suivi.courante)
        if self.en_cours is not None and self.en_cours["nature"] == "AIDE":
            self.en_cours["obsolete"] = True
            self.en_cours = None
            tache = self.tache_envoi
            self.tache_envoi = None
            tache.cancel()
            self.journal("[REEL] Arret local de l'envoi ; une acceptation distante reste possible.")

    def simuler_ok(self, demande):
        self.journal("[REEL] Repondre OK dans Pushbullet. V ne simule aucune confirmation reelle.")

    def lire_ok(self):
        if self.disponible() and self.confirmations:
            return self.confirmations.pop(0)
        return None

    def noter_interaction(self):
        self.derniere_interaction = maintenant_ms()
        # Un appui rend la reprise urgente : pas d'attente d'un long backoff.
        self.echecs = 0

    def delai_controle(self):
        echecs = min(getattr(self, "echecs", 0), 4)
        return min(CONTROLE_MIN_MS << echecs, CONTROLE_MAX_MS)

    def differer_lecture(self):
        """Ne pas figer la boucle sous le doigt : une lecture OK coute une pause
        TLS. Les envois AIDE/ANNULATION, eux, ne sont jamais differes ici."""
        maintenant = maintenant_ms()
        derniere = getattr(self, "derniere_interaction", None)
        if derniere is None or ecart_ms(maintenant, derniere) >= RETENUE_INTERACTION_MS:
            self.retenue_depuis = None
            return False
        if getattr(self, "retenue_depuis", None) is None:
            self.retenue_depuis = maintenant
        if ecart_ms(maintenant, self.retenue_depuis) >= RETENUE_MAX_MS:
            # Garder l'autorisation jusqu'au depart reel : plusieurs gardes
            # successives ne doivent pas recreer une retenue de vingt secondes.
            return False
        return True

    async def lire_reponses(self):
        date = self.suivi.date_lecture()
        if date is None:
            return
        chemin = "pushes?active=true&limit=50&modified_after=%s" % date
        demande_lue = self.suivi.courante
        curseur = None
        deja_vus = set()
        for _ in range(20):
            while True:
                if self.suivi.courante != demande_lue or self.suivi.date_lecture() != date:
                    raise LectureDifferee()  # Le cycle a change ou a ete annule.
                try:
                    donnees = await self.api("GET", chemin + (
                        "&cursor=" + encoder_url(curseur) if curseur else ""), fond=True)
                    break
                except LectureDifferee:
                    # Garder le curseur : recommencer a la premiere page a
                    # chaque geste pourrait empecher d'atteindre un OK plus loin.
                    # Aucun verrou reseau n'est conserve pendant cette attente.
                    await asyncio.sleep(0.1)
            if not isinstance(donnees.get("pushes"), list):
                raise ApiErreur("Liste de reponses invalide.")
            candidats = 0
            rejets = {}
            for push in donnees["pushes"]:
                texte = push.get("body")
                if isinstance(texte, str) and (texte.strip().upper() == "OK" or
                                             texte.strip().upper().startswith("OK ")):
                    candidats += 1
                    motif = self.suivi.motif_rejet(push)
                    if motif is not None:
                        rejets[motif] = rejets.get(motif, 0) + 1
                demande = self.suivi.examiner(push)
                if demande is not None:
                    self.confirmations.append(demande)
                    if isinstance(self.suivi, SuiviGroupe):
                        self.annonces.extend(self.suivi.messages_confirmation(demande))
                    self.journal("[REEL] OK distant autorise pour la reference " + self.suivi.code(demande))
                    return
            self.journal("[OK] Lecture : %d messages ; %d textes OK ; rejets=%s" % (
                len(donnees["pushes"]), candidats,
                ", ".join("%s (%d)" % (motif, nombre) for motif, nombre in rejets.items()) or "aucun"))
            curseur = donnees.get("cursor")
            if not curseur:
                return
            if not isinstance(curseur, str) or curseur in deja_vus:
                raise ApiErreur("Pagination Pushbullet invalide.")
            deja_vus.add(curseur)
        raise ApiErreur("Trop de pages de reponses ; lecture incomplete.")

    async def annoncer_confirmation(self):
        # Le OK est deja remis au boitier : cette information aux proches
        # reste secondaire et ne modifie ni la confirmation ni les compteurs.
        if not self.annonces or self.en_cours is not None or not self.disponible():
            return
        charge = self.annonces[0]
        try:
            donnees = await self.api("POST", "pushes", charge, fond=True)
            if not donnees.get("iden"):
                raise ApiErreur("Annonce sans identifiant : resultat incertain.", True)
            self.journal("[REEL] Reponse du contact annoncee a un autre contact actif.")
        except LectureDifferee:
            raise  # Aucun POST parti : attendre la fin du geste sur le bouton.
        except Exception as erreur:
            # Un seul essai par destinataire ; une erreur peut cacher un POST
            # accepte. Ne pas creer de doublon ni afficher de donnees privees.
            self.journal("[REEL] Annonce de reponse non confirmee (%s) ; OK conserve." %
                         type(erreur).__name__)
        self.annonces.pop(0)

    async def surveiller_reactivite(self):
        precedent = maintenant_ms()
        while True:
            await asyncio.sleep(0.02)
            maintenant = maintenant_ms()
            pause = ecart_ms(maintenant, precedent)
            if pause >= 250:
                self.journal("[DIAGNOSTIC] Pause de la boucle : %d ms ; etape=%s" % (
                    pause, getattr(self, "etape_http", "preparation du reseau")))
                if pause >= 2000:
                    diagnostic.evenement("pause_boucle", duree_ms=pause)
            precedent = maintenant

    async def boucle(self):
        surveillance = asyncio.create_task(self.surveiller_reactivite())
        try:
            await self.boucle_reseau()
        finally:
            surveillance.cancel()
            try:
                await surveillance
            except asyncio.CancelledError:
                pass
            # Annuler l'envoi avant de fermer une connexion partagee avec lui.
            tache = self.tache_envoi
            if tache is not None:
                tache.cancel()
                try:
                    await tache
                except asyncio.CancelledError:
                    pass
            await self.fermer_https()

    async def boucle_reseau(self):
        while True:
            try:
                maintenant = maintenant_ms()
                if not self.wifi:
                    await asyncio.sleep(0.1)
                    continue
                if not self.wlan.isconnected():
                    self.pret = False
                    if self.connexion_depuis is None or ecart_ms(maintenant, self.connexion_depuis) >= 10_000:
                        self.connexion_depuis = maintenant
                        self.wlan.active(True)
                        self.wlan.connect(self.c.SSID, self.c.MOT_DE_PASSE_WIFI)
                        self.journal("[REEL] Connexion a " + self.c.SSID + "...")
                elif self.pushbullet and not self.erreur_permanente and not self.en_pause():
                    self.connexion_depuis = None
                    if not self.horloge_prete:
                        await synchroniser_horloge()
                        self.horloge_prete = True
                        diagnostic.horloge_reglee()
                        self.journal("[REEL] Horloge reglee ; verification TLS active.")
                        tm = time.gmtime()
                        self.journal("[REEL] Horloge UTC : %04d-%02d-%02d %02d:%02d:%02d" % tm[:6])
                    if not self.pret and (self.dernier_controle is None or
                                          ecart_ms(maintenant, self.dernier_controle) >= self.delai_controle()):
                        differee = False
                        try:
                            utilisateur = await self.api("GET", "users/me", fond=True)
                        except LectureDifferee:
                            differee = True
                            raise
                        finally:
                            if not differee:
                                self.dernier_controle = maintenant_ms()
                        self.suivi.identifier(utilisateur)
                        self.pret = True
                        self.echecs = 0
                        self.journal("[REEL] Compte Pushbullet verifie ; pret pour AIDE.")
                    if (self.pret and self.suivi.date_lecture() is not None and (
                            self.dernier_ok is None or ecart_ms(maintenant, self.dernier_ok) >= self.c.INTERVALLE_LECTURE_MS)
                            and not self.differer_lecture()):
                        differee = False
                        try:
                            await self.lire_reponses()
                        except LectureDifferee:
                            differee = True
                            raise
                        finally:
                            # Intervalle compte APRES la lecture, meme si elle
                            # dure plus longtemps que prevu.
                            if not differee:
                                self.dernier_ok = maintenant_ms()
                    elif getattr(self, "annonces", None) and not self.differer_lecture():
                        await self.annoncer_confirmation()
            except LectureDifferee:
                # Pas de panne, de backoff ou de nouveau delai de lecture.
                # La boucle reste vivante et reprend apres le geste.
                pass
            except Exception as erreur:
                self.pret = False
                diagnostic.evenement("http_erreur", classe=type(erreur).__name__,
                                     statut=erreur.statut if isinstance(erreur, ApiErreur) else None)
                # Backoff : chaque essai coute une pause TLS, meme au REPOS.
                self.echecs = getattr(self, "echecs", 0) + 1
                self.journal("[REEL] " + (str(erreur) if isinstance(erreur, ApiErreur) else
                             "Connexion/lecture indisponible : " + decrire_erreur_transport(erreur)) +
                             " ; nouvel essai dans %d s." % (self.delai_controle() // 1000))
                await asyncio.sleep(5)
            await asyncio.sleep(0.1)
