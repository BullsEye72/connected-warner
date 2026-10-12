"""Transport de TEST : vrai Wi-Fi, HTTPS et Pushbullet, sans secrets inclus."""
import json
import time
import sys
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

HOTE_API = "api.pushbullet.com"
MAX_REPONSE = 96_000
INACTIVITE_HTTPS_MS = 30_000
CACHE_DNS_MS = 300_000
VERSION_TRANSPORT = "MP-HTTPS-20261012-4"


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
    adresse = c.DESTINATAIRE_EMAIL.strip()
    if "@" not in adresse or any(x.isspace() for x in adresse):
        raise ValueError("Renseigner DESTINATAIRE_EMAIL dans configuration.py.")
    if c.INTERVALLE_RELANCE_MS < 10_000 or c.INTERVALLE_LECTURE_MS < 5_000:
        raise ValueError("Relances : minimum 10 s ; lecture des OK : minimum 5 s.")
    if not 3_000 <= c.DELAI_HTTP_MS <= 30_000:
        raise ValueError("DELAI_HTTP_MS doit etre compris entre 3000 et 30000.")


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
    def __init__(self, message, incertain=False):
        super().__init__(message)
        self.incertain = incertain


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

    def __init__(self, destinataire, piece, session):
        self.destinataire = destinataire.strip().lower()
        self.piece = piece
        self.session = session
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
            titre = "[TEST AIDE] %s (Wokwi)" % self.piece
            corps = ("TEST - aucune intervention necessaire.\nEssai du bouton : %s.\n"
                     "Reference : %s. Notification %d sur 5.\n\n"
                     "Repondre au compte expediteur : OK\nOu : OK %s") % (
                         self.piece, code, numero, code)
        else:
            titre = "[TEST ANNULATION] %s (Wokwi)" % self.piece
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

    def motif_rejet(self, push):
        demande = self.courante
        etat = self.demandes.get(demande)
        if not etat or etat["terminee"]:
            return "aucune demande active"
        if etat["date"] is None:
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
        if date < etat["date"]:
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

    def examiner(self, push):
        if self.motif_rejet(push) is not None:
            return None
        demande = self.courante
        self.reponses_utilisees.add(push["iden"])
        self.fermer(demande)
        return demande


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
        self.resultats = []
        self.confirmations = []
        self.tache_envoi = None
        self.connexion_depuis = None
        self.dernier_controle = None
        self.dernier_ok = None
        self.verrou = asyncio.Lock()
        self.connexion_https = None
        self.derniere_utilisation_https = None
        self.connexion_perimee = False
        self.adresse_api = None
        self.date_dns = None
        self.suivi = SuiviPushbullet(self.c.DESTINATAIRE_EMAIL, self.c.PIECE,
                                    binascii.hexlify(os.urandom(6)).decode().upper())
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
        if getattr(self.c, "TRACE_HTTPS", True):
            self.journal("[HTTPS] %s %s : %s" % (methode, chemin.split("?", 1)[0], etape))

    async def api(self, methode, chemin, corps=None):
        async with self.verrou:
            if not self.wifi or not self.pushbullet or not self.wlan.isconnected():
                raise ApiErreur("Transmission suspendue avant requete.")
            self.communication_en_cours = True
            try:
                # La boucle des boutons tourne toutes les 5 ms. Lui laisser
                # afficher le cyan AVANT DNS/TLS, meme s'ils bloquent ensuite.
                await asyncio.sleep(0.02)
                statut, entetes, donnees = await asyncio.wait_for(
                    self.https(methode, chemin, corps), self.c.DELAI_HTTP_MS / 1000)
            except asyncio.TimeoutError:
                raise ApiErreur("Delai HTTPS depasse (%d ms) : %s." % (
                    self.c.DELAI_HTTP_MS, getattr(self, "etape_http", "connexion/lecture")),
                    methode == "POST")
            except OSError as erreur:
                raise ApiErreur("Connexion HTTPS indisponible : " + decrire_erreur_transport(
                    erreur, getattr(self, "etape_http", "connexion/lecture")), methode == "POST")
            finally:
                self.communication_en_cours = False
        if statut != 200:
            if statut in (400, 401, 403, 404):
                self.erreur_permanente = True
            if statut == 429:
                try:
                    secondes = int(entetes.get("retry-after", "60"))
                except ValueError:
                    secondes = 60
                self.pause_depuis = maintenant_ms()
                self.pause_ms = max(30, min(3600, secondes)) * 1000
            raise ApiErreur("HTTP %d : transmission non confirmee." % statut,
                            methode == "POST" and statut >= 500)
        return donnees

    def commencer(self, nature, demande, maintenant):
        if not self.disponible() or self.en_cours is not None:
            return False
        if nature == "AIDE":
            self.suivi.ouvrir(demande)
        else:
            self.suivi.fermer(demande)
        requete = {"nature": nature, "demande": demande, "debut": maintenant, "erreur": None}
        self.en_cours = requete
        self.tache_envoi = asyncio.create_task(self.envoyer(requete))
        self.journal("[REEL] Envoi TEST %s, reference %s..." % (nature, self.suivi.code(demande)))
        return True

    async def envoyer(self, requete):
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

    async def lire_reponses(self):
        date = self.suivi.date_lecture()
        if date is None:
            return
        chemin = "pushes?active=true&limit=50&modified_after=%s" % date
        curseur = None
        deja_vus = set()
        for _ in range(20):
            donnees = await self.api("GET", chemin + ("&cursor=" + encoder_url(curseur) if curseur else ""))
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

    async def surveiller_reactivite(self):
        precedent = maintenant_ms()
        while True:
            await asyncio.sleep(0.02)
            maintenant = maintenant_ms()
            pause = ecart_ms(maintenant, precedent)
            if pause >= 250:
                self.journal("[DIAGNOSTIC] Pause de la boucle : %d ms ; etape=%s" % (
                    pause, getattr(self, "etape_http", "preparation du reseau")))
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
                        self.journal("[REEL] Horloge reglee ; verification TLS active.")
                        tm = time.gmtime()
                        self.journal("[REEL] Horloge UTC : %04d-%02d-%02d %02d:%02d:%02d" % tm[:6])
                    if not self.pret and (self.dernier_controle is None or ecart_ms(maintenant, self.dernier_controle) >= 5_000):
                        try:
                            utilisateur = await self.api("GET", "users/me")
                        finally:
                            self.dernier_controle = maintenant_ms()
                        self.suivi.identifier(utilisateur)
                        self.pret = True
                        self.journal("[REEL] Compte Pushbullet verifie ; pret pour AIDE.")
                    if self.pret and self.suivi.date_lecture() is not None and (
                            self.dernier_ok is None or ecart_ms(maintenant, self.dernier_ok) >= self.c.INTERVALLE_LECTURE_MS):
                        try:
                            await self.lire_reponses()
                        finally:
                            # Cinq secondes APRES la lecture, meme si elle
                            # dure plus longtemps que l'intervalle prevu.
                            self.dernier_ok = maintenant_ms()
            except Exception as erreur:
                self.pret = False
                self.journal("[REEL] " + (str(erreur) if isinstance(erreur, ApiErreur) else
                             "Connexion/lecture indisponible : " + decrire_erreur_transport(erreur)))
                await asyncio.sleep(5)
            await asyncio.sleep(0.1)
