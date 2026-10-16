"""Presence HTTPS facultative. Aucun secret Pushbullet/Wi-Fi n'est transmis.

DNS UDP, TCP et TLS non bloquants ; abandon du suivi aux gestes et a Pushbullet.
Les instantanes en attente sont remplaces par le plus recent, pas empiles.
"""
import json
import os
import time
import struct
import binascii
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio
from pushbullet_reel import maintenant_ms, ecart_ms, charger_certificats, lire_reponse_http

VERSION = "MP-20261016-PRESENCE"
PRESENCE_MS = 600_000
CALME_MS = 2_000


def valider_configuration(c):
    url = getattr(c, "DASHBOARD_URL", "")
    identifiant = getattr(c, "DASHBOARD_APPAREIL_ID", "")
    cle = getattr(c, "DASHBOARD_CLE", "")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("DASHBOARD_URL doit utiliser HTTPS.")
    hote = url[8:].rstrip("/")
    if not hote or len(hote) > 253 or any(x not in "abcdefghijklmnopqrstuvwxyz0123456789-." for x in hote):
        raise ValueError("DASHBOARD_URL doit contenir uniquement le nom du site HTTPS.")
    if (not isinstance(identifiant, str) or len(identifiant) != 36 or
            any(identifiant[n] != "-" for n in (8, 13, 18, 23)) or
            any(x not in "0123456789abcdefABCDEF-" for x in identifiant)):
        raise ValueError("DASHBOARD_APPAREIL_ID invalide.")
    if not isinstance(cle, str) or not cle.startswith("cw_") or len(cle) != 46 or any(
            x not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for x in cle[3:]):
        raise ValueError("DASHBOARD_CLE invalide.")
    return hote


def instantane(boitier, session, sequence, secondes, version_python):
    etat = {"REPOS": "repos", "ATTENTE": "en_attente", "SANS_CONFIRMATION": "en_attente",
            "CONFIRMEE": "confirmee", "ANNULEE": "annulee"}[boitier.etat]
    if boitier.etat == "REPOS" and boitier.dernier_resultat == (boitier.demande, "ANNULEE"):
        etat = "annulee"
    wifi = getattr(boitier, "qualite_wifi", None)
    return {"session": session, "sequence": sequence, "state": etat,
            "uptime_seconds": min(4294967295, max(0, int(secondes))),
            "firmware_version": VERSION, "micropython_version": version_python[:64],
            "wifi_rssi": getattr(wifi, "rssi", None),
            "request_id": "%s-%d" % (session, boitier.demande) if boitier.demande else None}


def saut_nom(paquet, position):
    for _ in range(128):
        if position >= len(paquet):
            raise ValueError("DNS incomplet")
        longueur = paquet[position]
        if longueur & 0xC0 == 0xC0:
            if position + 1 >= len(paquet):
                raise ValueError("DNS incomplet")
            return position + 2
        if longueur & 0xC0:
            raise ValueError("Nom DNS invalide")
        position += 1
        if not longueur:
            return position
        position += longueur
    raise ValueError("Nom DNS trop long")


def lire_dns(paquet, identifiant):
    if len(paquet) < 12 or paquet[:2] != identifiant:
        raise ValueError("Reponse DNS invalide")
    _, flags, questions, reponses, _, _ = struct.unpack("!HHHHHH", paquet[:12])
    if flags & 0x8000 == 0 or flags & 0x020F or questions != 1 or reponses > 64:
        raise ValueError("Reponse DNS refusee")
    position = saut_nom(paquet, 12) + 4
    for _ in range(reponses):
        position = saut_nom(paquet, position)
        if position + 10 > len(paquet):
            raise ValueError("DNS incomplet")
        genre, classe, ttl, longueur = struct.unpack("!HHIH", paquet[position:position + 10])
        position += 10
        if position + longueur > len(paquet):
            raise ValueError("DNS incomplet")
        if genre == 1 and classe == 1 and longueur == 4:
            return ".".join(str(x) for x in paquet[position:position + 4]), min(300_000, max(1000, ttl * 1000))
        position += longueur
    raise ValueError("Pas d'adresse DNS IPv4")


async def resoudre(hote, serveur):
    import socket
    identifiant = os.urandom(2)
    question = b"".join(bytes([len(partie)]) + partie.encode() for partie in hote.split(".")) + b"\0\0\1\0\1"
    paquet = identifiant + b"\1\0\0\1\0\0\0\0\0\0" + question
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    try:
        sock.connect((serveur, 53))
        sock.send(paquet)
        while True:
            try:
                reponse = sock.recv(4096)
                if reponse[:2] == identifiant:
                    return lire_dns(reponse, identifiant)
            except OSError as erreur:
                if erreur.args[0] not in (11, 35, 10035):
                    raise
            await asyncio.sleep(0.01)
    finally:
        sock.close()


class LecteurTLS:
    def __init__(self, sock, suivi=None):
        self.sock, self.tampon, self.suivi = sock, b"", suivi

    async def read(self, n):
        if self.tampon:
            resultat, self.tampon = self.tampon[:n], self.tampon[n:]
            return resultat
        return await self.lire_socket(n)

    async def lire_socket(self, n):
        while True:
            debut = maintenant_ms()
            try:
                contenu = self.sock.read(min(n, 1024))
                if contenu is not None:
                    return contenu
            except OSError as erreur:
                if erreur.args[0] not in (11, 35, 10035):
                    raise
            finally:
                if self.suivi is not None:
                    self.suivi.pas_max_ms = max(self.suivi.pas_max_ms, ecart_ms(maintenant_ms(), debut))
            await asyncio.sleep(0.01)

    async def readexactly(self, n):
        while len(self.tampon) < n:
            contenu = await self.lire_socket(n - len(self.tampon))
            if not contenu:
                raise ValueError("HTTP incomplet")
            self.tampon += contenu
        resultat, self.tampon = self.tampon[:n], self.tampon[n:]
        return resultat

    async def readline(self):
        while b"\n" not in self.tampon:
            contenu = await self.lire_socket(512)
            if not contenu:
                resultat, self.tampon = self.tampon, b""
                return resultat
            self.tampon += contenu
            if len(self.tampon) > 8192:
                raise ValueError("Ligne HTTP trop longue")
        fin = self.tampon.index(b"\n") + 1
        resultat, self.tampon = self.tampon[:fin], self.tampon[fin:]
        return resultat


class TransportHTTPS:
    def __init__(self, c, wlan):
        import ssl
        self.c, self.wlan = c, wlan
        self.hote = valider_configuration(c)
        self.tls = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.tls.verify_mode = ssl.CERT_REQUIRED
        charger_certificats(self.tls, c.FICHIER_CA)
        self.adresse = self.date_dns = None
        self.ttl_ms = 0
        self.pas_max_ms = 0

    async def envoyer(self, rapport):
        import socket
        import select
        if self.adresse is None or ecart_ms(maintenant_ms(), self.date_dns) >= self.ttl_ms:
            self.adresse, self.ttl_ms = await resoudre(self.hote, self.wlan.ifconfig()[3])
            self.date_dns = maintenant_ms()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setblocking(False)
        poll = select.poll()
        try:
            try:
                sock.connect((self.adresse, 443))
            except OSError as erreur:
                if erreur.args[0] not in (11, 36, 115, 10035, 10036):
                    raise
            poll.register(sock, select.POLLOUT | select.POLLERR | select.POLLHUP)
            while not poll.poll(0):
                await asyncio.sleep(0.01)
            poll.unregister(sock)
            sock = self.tls.wrap_socket(sock, server_hostname=self.hote, do_handshake_on_connect=False)
            sock.setblocking(False)
            contenu = json.dumps(rapport).encode()
            entetes = ("POST /api/devices/%s/heartbeat HTTP/1.1\r\nHost: %s\r\nAuthorization: Bearer %s\r\n"
                       "Content-Type: application/json\r\nAccept: application/json\r\nAccept-Encoding: identity\r\n"
                       "Connection: close\r\nContent-Length: %d\r\n\r\n") % (
                           self.c.DASHBOARD_APPAREIL_ID, self.hote, self.c.DASHBOARD_CLE, len(contenu))
            donnees = entetes.encode() + contenu
            position = 0
            while position < len(donnees):
                debut = maintenant_ms()
                try:
                    n = sock.write(memoryview(donnees)[position:position + 1024])
                    if n:
                        position += n
                except OSError as erreur:
                    if erreur.args[0] not in (11, 35, 10035):
                        raise
                self.pas_max_ms = max(self.pas_max_ms, ecart_ms(maintenant_ms(), debut))
                await asyncio.sleep(0.01)
            return await lire_reponse_http(LecteurTLS(sock, self))
        finally:
            sock.close()


class PresenceDashboard:
    def __init__(self, c, boitier, journal_local, transport, journal=print):
        self.c, self.boitier, self.journal_local = c, boitier, journal_local
        self.transport, self.journal = transport, journal
        self.session = binascii.hexlify(os.urandom(12)).decode()
        self.sequence, self.tache = 0, None
        self.envoye, self.voulu = None, None
        self.dernier_succes = self.dernier_essai = None
        self.derniere_activite = maintenant_ms()
        self.reessai_ms, self.echecs, self.suspendu = 0, 0, False
        self.version_python = ".".join(str(x) for x in __import__("sys").implementation.version[:3])

    def actualiser(self, maintenant, aide=False):
        reseau = self.boitier.reseau
        nouveau = (self.boitier.etat, self.boitier.demande, self.boitier.dernier_resultat)
        change = nouveau != self.voulu
        self.voulu = nouveau
        if self.tache is not None and self.tache.done():
            self.tache = None
        priorite = aide or self.boitier.maintien_depuis is not None or bool(self.boitier.annulations_a_transmettre) or (
            reseau.en_cours is not None or getattr(reseau, "communication_en_cours", False) or
            getattr(reseau, "lecture_de_fond", False))
        if priorite:
            self.derniere_activite = maintenant
        if self.tache is not None:
            if priorite or change:
                self.tache.cancel()
            return
        if (self.suspendu or priorite or ecart_ms(maintenant, self.derniere_activite) < CALME_MS or
                not self.transport.wlan.isconnected() or not getattr(reseau, "horloge_prete", False)):
            return
        if self.dernier_essai is not None and ecart_ms(maintenant, self.dernier_essai) < self.reessai_ms:
            return
        if (self.envoye == nouveau and self.dernier_succes is not None and
                ecart_ms(maintenant, self.dernier_succes) < PRESENCE_MS):
            return
        self.sequence += 1
        if self.sequence > 2147483647:
            self.suspendu = True
            return
        rapport = instantane(self.boitier, self.session, self.sequence, self.journal_local.temps(), self.version_python)
        self.dernier_essai = maintenant
        self.tache = asyncio.create_task(self.transmettre(rapport, nouveau))

    async def transmettre(self, rapport, reference):
        try:
            statut, entetes, resultat = await asyncio.wait_for(self.transport.envoyer(rapport), 8)
            if statut == 200 and isinstance(resultat.get("accepted"), bool):
                self.envoye, self.dernier_succes = reference, maintenant_ms()
                self.echecs, self.reessai_ms = 0, 0
                self.journal("[DASHBOARD] Presence transmise (HTTP 200).")
                if self.transport.pas_max_ms >= 50:
                    self.journal("[DASHBOARD DIAGNOSTIC] Plus long pas TLS : %d ms ; a mesurer sur carte." % self.transport.pas_max_ms)
            elif statut in (400, 401, 403, 404, 415):
                self.suspendu = True
                self.journal("[DASHBOARD] Configuration refusee (HTTP %d) ; suivi suspendu jusqu'au redemarrage." % statut)
            else:
                self.echec()
        except asyncio.CancelledError:
            # Le prochain instantane remplace celui-ci ; aucun etat local n'est change.
            self.reessai_ms = 0
        except Exception:
            self.echec()

    def echec(self):
        self.echecs = min(6, self.echecs + 1)
        self.reessai_ms = min(300_000, 15_000 * 2 ** (self.echecs - 1))
        self.journal("[DASHBOARD] Suivi indisponible ; nouvel essai dans %d s." % (self.reessai_ms // 1000))

    def arreter(self):
        if self.tache is not None:
            self.tache.cancel()


def creer_presence(c, boitier, journal_local, journal=print):
    if not getattr(c, "DASHBOARD_ACTIF", False):
        return None
    try:
        valider_configuration(c)
        reseau = boitier.reseau
        if not getattr(reseau, "reel", False):
            raise ValueError("Le suivi necessite le profil reel.")
        return PresenceDashboard(c, boitier, journal_local, TransportHTTPS(c, reseau.wlan), journal)
    except Exception:
        journal("[DASHBOARD] Reglages invalides ; suivi desactive, alertes conservees.")
        return None
