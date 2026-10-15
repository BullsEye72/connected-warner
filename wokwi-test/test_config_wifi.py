import asyncio
import json
import os
from pathlib import Path
import tempfile
import sys
import socket
import struct
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import config_wifi as wifi


class StockageTests(unittest.TestCase):
    def test_conserve_unicode_et_espaces_du_mot_de_passe(self):
        donnees = wifi.valider_identifiants("Maison été", " mot +%& ")
        with tempfile.TemporaryDirectory() as dossier:
            chemin = str(Path(dossier) / "wifi.json")
            wifi.ecrire_atomiquement(chemin, donnees)
            configuration = SimpleNamespace(SSID="ancien", MOT_DE_PASSE_WIFI="ancien")
            self.assertTrue(wifi.charger(configuration, chemin))
            self.assertEqual(configuration.SSID, "Maison été")
            self.assertEqual(configuration.MOT_DE_PASSE_WIFI, " mot +%& ")
            wifi.ecrire_atomiquement(chemin, wifi.valider_identifiants("Nouveau", "abcdefgh"))
            self.assertTrue(wifi.charger(configuration, chemin))
            self.assertEqual(configuration.SSID, "Nouveau")

    def test_echec_de_remplacement_conserve_ancien_fichier(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = str(Path(dossier) / "wifi.json")
            ancien = wifi.valider_identifiants("Ancien", "abcdefgh")
            wifi.ecrire_atomiquement(chemin, ancien)
            with patch.object(os, "replace", side_effect=OSError("echec")):
                with self.assertRaises(OSError):
                    wifi.ecrire_atomiquement(chemin, wifi.valider_identifiants("Nouveau", "ijklmnop"))
            self.assertEqual(json.loads(Path(chemin).read_text()), ancien)
            self.assertFalse(Path(chemin + ".tmp").exists())

    def test_absence_ou_corruption_ne_remplace_pas_la_configuration(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = Path(dossier) / "wifi.json"
            configuration = SimpleNamespace(SSID="ancien", MOT_DE_PASSE_WIFI="abcdefgh")
            self.assertFalse(wifi.charger(configuration, str(chemin)))
            for contenu in ("{", '{}', '{"version":99}', '{"version":1,"ssid":"","mot_de_passe":"abcdefgh"}'):
                chemin.write_text(contenu)
                with patch("builtins.print"):
                    self.assertFalse(wifi.charger(configuration, str(chemin)))
                self.assertEqual(configuration.SSID, "ancien")

    def test_cle_installation_stable_et_protegee(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = str(Path(dossier) / "installation.json")
            a = wifi.identite_installation(b"\x01\x02\x03\x04\x05\x06", chemin)
            self.assertEqual(a[0], "Aide-040506")
            self.assertEqual(len(a[1]), 16)
            self.assertEqual(a, wifi.identite_installation(b"\x01\x02\x03\x04\x05\x06", chemin))

    def test_validation_et_limites_en_octets(self):
        for ssid, mdp in (("", "abcdefgh"), ("é" * 17, "abcdefgh"), ("Maison", "court"),
                          ("Maison", "a" * 64), ("Maison", "abc\x00defgh")):
            with self.assertRaises(ValueError):
                wifi.valider_identifiants(ssid, mdp)
        self.assertEqual(wifi.valider_identifiants("Ouvert", "", True)["mot_de_passe"], "")
        with self.assertRaises(ValueError):
            wifi.valider_identifiants("Maison", "")

    def test_formulaire_preserve_les_caracteres_et_rejette_doublons(self):
        champs = {"ssid": "Maison été", "mot_de_passe": " a+b%&= "}
        self.assertEqual(wifi.decoder_formulaire(urlencode(champs).encode()), champs)
        for corps in (b"a=%", b"a=%GG", b"a=%FF", b"a=1&a=2", b"a"):
            with self.assertRaises(ValueError):
                wifi.decoder_formulaire(corps)

    def test_noms_des_reseaux_ne_peuvent_pas_injecter_du_html(self):
        html = wifi.page("abcdef", ['\"><script>alert(1)</script>']).decode()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn('type="password"', html)

    def test_nom_persistant_charge_la_piece_et_ancien_fichier_la_conserve(self):
        with tempfile.TemporaryDirectory() as dossier:
            chemin = str(Path(dossier) / "wifi.json")
            configuration = SimpleNamespace(SSID="ancien", MOT_DE_PASSE_WIFI="abcdefgh", PIECE="Lit")
            donnees = wifi.valider_identifiants("Maison", "abcdefgh")
            wifi.ecrire_atomiquement(chemin, donnees)
            self.assertTrue(wifi.charger(configuration, chemin))
            self.assertEqual(configuration.PIECE, "Lit")
            donnees["nom_boitier"] = "Salle de bains été"
            donnees["connexion_verifiee"] = False
            wifi.ecrire_atomiquement(chemin, donnees)
            self.assertTrue(wifi.charger(configuration, chemin))
            self.assertEqual(configuration.PIECE, "Salle de bains été")
            from pushbullet_reel import SuiviPushbullet
            suivi = SuiviPushbullet("test@example.com", configuration.PIECE, "TEST", "ESP32")
            suivi.ouvrir(1)
            self.assertIn(configuration.PIECE, suivi.charge("AIDE", 1)["title"])

    def test_nom_valide_et_echappe_sans_modifier_les_options(self):
        self.assertEqual(wifi.valider_nom_boitier("  Lit été  "), "Lit été")
        for nom in ("", "   ", "a" * 41, "Lit\nPapa", "Lit\x00", None):
            with self.assertRaises(ValueError):
                wifi.valider_nom_boitier(nom)
        html = wifi.page("abcdef", ["OPTIONS"], '\"><script>nom</script>').decode()
        self.assertNotIn('<script>nom</script>', html)
        self.assertIn('name="nom_boitier"', html)
        self.assertIn('&lt;script&gt;nom&lt;/script&gt;', html)
        self.assertIn('<option value="OPTIONS">', html)


class Station:
    def __init__(self, connectee=True):
        self.connectee = connectee
        self.parametres = None
        self.coupures = 0
    def disconnect(self):
        self.coupures += 1
    def config(self, **kwargs):
        pass
    def connect(self, ssid, mdp):
        self.parametres = (ssid, mdp)
    def isconnected(self):
        return self.connectee


def question_dns(nom="connectivitycheck.gstatic.com", type_question=1):
    labels = b"".join(bytes((len(partie),)) + partie.encode() for partie in nom.split(".")) + b"\x00"
    return struct.pack("!6H", 1234, 0x0100, 1, 0, 0, 0) + labels + struct.pack("!HH", type_question, 1)


class DNSTests(unittest.TestCase):
    def test_question_ipv4_dirige_vers_le_portail_sans_cache(self):
        question = question_dns()
        reponse = wifi.reponse_dns(question)
        entete = struct.unpack("!6H", reponse[:12])
        self.assertEqual(entete, (1234, 0x8500, 1, 1, 0, 0))
        self.assertEqual(reponse[12:len(question)], question[12:])
        self.assertEqual(struct.unpack("!HHHIH", reponse[len(question):-4]), (0xC00C, 1, 1, 0, 4))
        self.assertEqual(reponse[-4:], b"\xc0\xa8\x04\x01")

    def test_ipv6_et_https_dns_ont_une_reponse_vide_valide(self):
        for type_question in (28, 65):
            question = question_dns(type_question=type_question)
            reponse = wifi.reponse_dns(question)
            self.assertEqual(struct.unpack("!6H", reponse[:12]), (1234, 0x8500, 1, 0, 0, 0))
            self.assertEqual(reponse[12:], question[12:])

    def test_paquets_invalides_sont_ignores_sans_exception(self):
        question = question_dns()
        for paquet in (b"", question[:10], question[:-1],
                       struct.pack("!6H", 1, 0, 1, 0, 0, 0) + b"\xc0\x0c\x00\x01\x00\x01",
                       struct.pack("!6H", 1, 0, 2, 0, 0, 0) + question[12:],
                       struct.pack("!6H", 1, 0x8000, 1, 0, 0, 0) + question[12:]):
            self.assertIsNone(wifi.reponse_dns(paquet))

    def test_long_nom_et_edns_ne_creent_pas_de_reponse_malformee(self):
        question = question_dns(nom="a" * 63 + "." + "b" * 63 + ".local")
        reponse = wifi.reponse_dns(question + b"\x00" * 30)
        self.assertEqual(reponse[12:len(question)], question[12:])
        self.assertEqual(struct.unpack("!H", reponse[10:12])[0], 0)


class DNSUDPTests(unittest.IsolatedAsyncioTestCase):
    async def test_serveur_udp_et_arret_liberent_le_port(self):
        dns = wifi.DNSCaptif("127.0.0.1", 0)
        port = dns.sock.getsockname()[1]
        tache = asyncio.create_task(dns.boucle())
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.setblocking(False)
        try:
            client.sendto(question_dns(), ("127.0.0.1", port))
            limite = time.monotonic() + 2
            while True:
                try:
                    reponse, _ = client.recvfrom(512)
                    break
                except BlockingIOError:
                    if time.monotonic() > limite:
                        self.fail("Aucune reponse DNS")
                    await asyncio.sleep(0.01)
            self.assertEqual(reponse[-4:], b"\xc0\xa8\x04\x01")
            self.assertEqual(dns.requetes, 1)
        finally:
            client.close()
            tache.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await tache
        autre = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            autre.bind(("127.0.0.1", port))
        finally:
            autre.close()


class PortailTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = str(Path(self.dossier.name) / "wifi.json")
        self.station = Station()
        self.portail = wifi.Portail(self.station, token="abcdef", chemin=self.chemin)
        self.serveur = await asyncio.start_server(self.portail.traiter, "127.0.0.1", 0)
        self.port = self.serveur.sockets[0].getsockname()[1]
        self.horloge = patch.multiple(time, ticks_ms=lambda: int(time.monotonic() * 1000),
                                     ticks_diff=lambda a, b: a - b, create=True)
        self.horloge.start()

    async def asyncTearDown(self):
        self.serveur.close()
        await self.serveur.wait_closed()
        if self.portail.tache is not None:
            self.portail.tache.cancel()
            try:
                await self.portail.tache
            except asyncio.CancelledError:
                pass
        self.horloge.stop()
        self.dossier.cleanup()

    async def requete(self, methode="GET", chemin="/", champs=None, host="192.168.4.1"):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        corps = urlencode(champs).encode() if champs is not None else b""
        entetes = (f"{methode} {chemin} HTTP/1.1\r\nHost: {host}\r\n"
                   f"Content-Type: application/x-www-form-urlencoded\r\nContent-Length: {len(corps)}\r\n\r\n").encode()
        writer.write(entetes + corps)
        await writer.drain()
        reponse = await reader.read()
        writer.close()
        await writer.wait_closed()
        return reponse

    async def test_page_et_etat_ne_divulguent_pas_de_mot_de_passe(self):
        reponse = await self.requete()
        self.assertTrue(reponse.startswith(b"HTTP/1.1 200"))
        self.assertIn(b'name="token" value="abcdef"', reponse)
        reponse = await self.requete(chemin="/etat")
        self.assertNotIn(b"mot_de_passe", reponse)

    async def test_detection_android_apple_windows_redirige_vers_ip_locale(self):
        for host, chemin in (("connectivitycheck.gstatic.com", "/generate_204"),
                             ("captive.apple.com", "/hotspot-detect.html"),
                             ("www.msftconnecttest.com", "/connecttest.txt")):
            reponse = await self.requete(chemin=chemin, host=host)
            self.assertTrue(reponse.startswith(b"HTTP/1.1 302"))
            self.assertIn(b"Location: http://192.168.4.1/\r\n", reponse)
            self.assertNotIn(b"abcdef", reponse)

    async def test_detection_sur_ip_locale_redirige_sans_toucher_etat(self):
        reponse = await self.requete(chemin="/generate_204")
        self.assertTrue(reponse.startswith(b"HTTP/1.1 302"))
        self.assertEqual(self.portail.etat, "repos")
        self.assertIsNone(self.station.parametres)
        self.assertTrue((await self.requete(chemin="/favicon.ico")).startswith(b"HTTP/1.1 404"))

    async def test_sonde_http_1_0_redirige_aussi(self):
        reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
        writer.write(b"GET /hotspot-detect.html HTTP/1.0\r\nHost: captive.apple.com\r\n\r\n")
        await writer.drain()
        self.assertTrue((await reader.read()).startswith(b"HTTP/1.1 302"))
        writer.close()
        await writer.wait_closed()

    async def test_post_verifie_la_connexion_puis_enregistre(self):
        reponse = await self.requete("POST", "/wifi", {"token": "abcdef", "ssid": "Maison", "mot_de_passe": " a+b%&= "})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 202"))
        await self.portail.tache
        self.assertEqual(self.portail.etat, "ok")
        self.assertEqual(self.station.parametres, ("Maison", " a+b%&= "))
        self.assertEqual(json.loads(Path(self.chemin).read_text())["mot_de_passe"], " a+b%&= ")

    async def test_echec_wifi_conserve_les_identifiants_precedents(self):
        ancien = wifi.valider_identifiants("Ancien", "abcdefgh")
        wifi.ecrire_atomiquement(self.chemin, ancien)
        self.station.connectee = False
        await self.portail.connecter(wifi.valider_identifiants("Nouveau", "ijklmnop"), delai_ms=0)
        self.assertEqual(self.portail.etat, "non_verifie")
        self.assertEqual(json.loads(Path(self.chemin).read_text()), ancien)

    async def test_enregistrement_non_verifie_explicitement_confirme_et_persistant(self):
        donnees = wifi.valider_identifiants("Absent", "abcdefgh")
        donnees["nom_boitier"] = "Salle de bains"
        self.station.connectee = False
        await self.portail.connecter(donnees, delai_ms=0)
        self.assertFalse(Path(self.chemin).exists())
        statut = json.loads((await self.requete(chemin="/etat")).split(b"\r\n\r\n", 1)[1])
        self.assertNotIn("mot_de_passe", statut)
        self.assertEqual((statut["ssid"], statut["nom_boitier"]), ("Absent", "Salle de bains"))
        reponse = await self.requete("POST", "/enregistrer", {"token": "abcdef", "confirmation": statut["confirmation"]})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 200"))
        sauvegarde = json.loads(Path(self.chemin).read_text())
        self.assertFalse(sauvegarde["connexion_verifiee"])
        self.assertEqual(sauvegarde["nom_boitier"], "Salle de bains")
        configuration = SimpleNamespace(PIECE="Lit")
        self.assertTrue(wifi.charger(configuration, self.chemin))
        self.assertEqual((configuration.SSID, configuration.PIECE), ("Absent", "Salle de bains"))
        self.assertEqual(self.portail.etat, "ok")
        self.assertIsNotNone(self.portail.succes_depuis)

    async def test_force_refuse_avant_echec_avec_mauvais_token_ou_confirmation_ancienne(self):
        reponse = await self.requete("POST", "/enregistrer", {"token": "abcdef", "confirmation": "invalide"})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 409"))
        self.station.connectee = False
        donnees = wifi.valider_identifiants("Absent", "abcdefgh")
        await self.portail.connecter(donnees, delai_ms=0)
        ancienne = self.portail.confirmation
        await self.portail.connecter(donnees, delai_ms=0)
        for token, confirmation, host, code in (("incorrect", self.portail.confirmation, "192.168.4.1", b"403"),
                ("abcdef", ancienne, "192.168.4.1", b"409"),
                ("abcdef", self.portail.confirmation, "autre-site", b"403")):
            reponse = await self.requete("POST", "/enregistrer", {"token": token, "confirmation": confirmation}, host=host)
            self.assertIn(b"HTTP/1.1 " + code, reponse)
        self.assertFalse(Path(self.chemin).exists())

    async def test_echec_stockage_force_conserve_l_ancien_et_ne_redemarre_pas(self):
        ancien = wifi.valider_identifiants("Ancien", "abcdefgh")
        wifi.ecrire_atomiquement(self.chemin, ancien)
        self.station.connectee = False
        await self.portail.connecter(wifi.valider_identifiants("Absent", "ijklmnop"), delai_ms=0)
        with patch.object(wifi, "ecrire_atomiquement", side_effect=OSError("plein")):
            reponse = await self.requete("POST", "/enregistrer", {"token": "abcdef", "confirmation": self.portail.confirmation})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 500"))
        self.assertIsNone(self.portail.succes_depuis)
        self.assertEqual(json.loads(Path(self.chemin).read_text()), ancien)

    async def test_nom_invalide_ne_lance_pas_de_connexion_et_nom_valide_est_sauve(self):
        champs = {"token": "abcdef", "ssid": "Maison", "mot_de_passe": "abcdefgh", "nom_boitier": ""}
        reponse = await self.requete("POST", "/wifi", champs)
        self.assertTrue(reponse.startswith(b"HTTP/1.1 400"))
        self.assertIsNone(self.station.parametres)
        champs["nom_boitier"] = "  Lit été  "
        reponse = await self.requete("POST", "/wifi", champs)
        self.assertTrue(reponse.startswith(b"HTTP/1.1 202"))
        await self.portail.tache
        sauvegarde = json.loads(Path(self.chemin).read_text())
        self.assertEqual(sauvegarde["nom_boitier"], "Lit été")
        self.assertTrue(sauvegarde["connexion_verifiee"])

    async def test_contacts_seuls_conservent_wifi_sans_test_ni_mot_de_passe_renvoye(self):
        contacts = [{"nom": "Alice", "email": "alice@example.com", "actif": True},
                    {"nom": "Bob", "email": "bob@example.com", "actif": False}]
        ancien = wifi.valider_identifiants("Maison", "motsecret")
        ancien["connexion_verifiee"] = True
        wifi.ecrire_atomiquement(self.chemin, ancien)
        reponse = await self.requete("POST", "/contacts", {"token": "abcdef", "nom_boitier": "Lit", "contacts": json.dumps(contacts)})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 200"))
        self.assertIsNone(self.station.parametres)
        self.assertNotIn(b"motsecret", reponse)
        sauvegarde = json.loads(Path(self.chemin).read_text())
        self.assertEqual((sauvegarde["ssid"], sauvegarde["mot_de_passe"]), ("Maison", "motsecret"))
        self.assertTrue(sauvegarde["connexion_verifiee"])
        self.assertEqual(sauvegarde["contacts"], contacts)
        profil = SimpleNamespace()
        self.assertTrue(wifi.charger(profil, self.chemin))
        self.assertEqual(profil.DESTINATAIRES, contacts)

    async def test_contacts_refuses_si_aucun_wifi_ou_liste_invalide_et_csrf_protege(self):
        valides = [{"nom": "Alice", "email": "alice@example.com", "actif": True}]
        champs = {"token": "abcdef", "nom_boitier": "Lit", "contacts": json.dumps(valides)}
        reponse = await self.requete("POST", "/contacts", champs)
        self.assertTrue(reponse.startswith(b"HTTP/1.1 400"))
        ancien = wifi.valider_identifiants("Maison", "motsecret")
        wifi.ecrire_atomiquement(self.chemin, ancien)
        for liste in ([], valides * 2, [dict(valides[0], actif=False)]):
            champs["contacts"] = json.dumps(liste)
            reponse = await self.requete("POST", "/contacts", champs)
            self.assertTrue(reponse.startswith(b"HTTP/1.1 400"))
            self.assertEqual(json.loads(Path(self.chemin).read_text()), ancien)
        champs.update(token="incorrect", contacts=json.dumps(valides))
        self.assertTrue((await self.requete("POST", "/contacts", champs)).startswith(b"HTTP/1.1 403"))
        champs["token"] = "abcdef"
        self.assertTrue((await self.requete("POST", "/contacts", champs, host="autre-site")).startswith(b"HTTP/1.1 403"))

    async def test_liste_et_nom_sauves_avec_wifi_et_apres_confirmation_non_verifiee(self):
        contacts = [{"nom": "Alice", "email": "alice@example.com", "actif": True}]
        self.station.connectee = False
        donnees = wifi.valider_identifiants("Absent", "abcdefgh")
        donnees.update(nom_boitier="Lit", contacts=contacts)
        await self.portail.connecter(donnees, delai_ms=0)
        reponse = await self.requete("POST", "/enregistrer", {"token": "abcdef", "confirmation": self.portail.confirmation})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 200"))
        self.assertEqual(json.loads(Path(self.chemin).read_text())["contacts"], contacts)

    async def test_liste_maximale_depasse_ancien_budget_http_et_reste_acceptee(self):
        contacts = [{"nom": "Famille " + str(i) + "é" * 25, "email": (str(i) + "a" * 100) + "@example.com", "actif": True} for i in range(8)]
        champs = {"token": "abcdef", "ssid": "Maison", "mot_de_passe": "abcdefgh", "nom_boitier": "Lit", "contacts": json.dumps(contacts)}
        self.assertGreater(len(urlencode(champs)), 1024)
        reponse = await self.requete("POST", "/wifi", champs)
        self.assertTrue(reponse.startswith(b"HTTP/1.1 202"))
        await self.portail.tache
        self.assertEqual(len(json.loads(Path(self.chemin).read_text())["contacts"]), 8)

    async def test_contact_ne_peut_pas_injecter_un_script_dans_la_page(self):
        contacts = [{"nom": "</script><script>alert(1)</script>", "email": "alice@example.com", "actif": True}]
        html = wifi.page("abcdef", [], "Lit", contacts).decode()
        self.assertNotIn("</script><script>alert(1)</script>", html)
        self.assertIn('id="contacts-seuls"', html)
        self.assertIn('\\u003c/script>', html)


    async def test_echec_stockage_n_annonce_pas_un_succes(self):
        with patch.object(wifi, "ecrire_atomiquement", side_effect=OSError("disque plein")):
            await self.portail.connecter(wifi.valider_identifiants("Maison", "abcdefgh"))
        self.assertEqual(self.portail.etat, "erreur")
        self.assertIsNone(self.portail.succes_depuis)

    async def test_token_et_host_invalides_ne_lancent_pas_de_connexion(self):
        for token, host in (("incorrect", "192.168.4.1"), ("abcdef", "autre-site")):
            reponse = await self.requete("POST", "/wifi", {"token": token, "ssid": "Maison", "mot_de_passe": "abcdefgh"}, host)
            self.assertTrue(reponse.startswith(b"HTTP/1.1 403"))
        self.assertIsNone(self.portail.tache)
        self.assertIsNone(self.station.parametres)

    async def test_connexion_en_cours_rejette_un_second_post(self):
        self.portail.etat = "connexion"
        reponse = await self.requete("POST", "/wifi", {"token": "abcdef", "ssid": "Maison", "mot_de_passe": "abcdefgh"})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 409"))
        self.assertIsNone(self.portail.tache)

    async def test_requetes_malformees_et_trop_grandes(self):
        for requete in (b"GET / HTTP/1.1\r\nHost: " + b"a" * 4100 + b"\r\n\r\n",
                        ("POST /wifi HTTP/1.1\r\nHost: 192.168.4.1\r\nContent-Length: %d\r\n\r\n" % (wifi.MAX_CORPS + 1)).encode(),
                        b"POST /wifi HTTP/1.1\r\nHost: 192.168.4.1\r\nTransfer-Encoding: chunked\r\n\r\n"):
            reader, writer = await asyncio.open_connection("127.0.0.1", self.port)
            writer.write(requete)
            await writer.drain()
            self.assertTrue((await reader.read()).startswith(b"HTTP/1.1 400"))
            writer.close()
            await writer.wait_closed()

    async def test_preconnexions_du_navigateur_ne_bloquent_pas_la_page(self):
        connexions = []
        try:
            for _ in range(3):
                connexions.append(await asyncio.open_connection("127.0.0.1", self.port))
            await asyncio.sleep(0.01)
            reponse = await self.requete()
            self.assertTrue(reponse.startswith(b"HTTP/1.1 200"))
            self.assertEqual(self.portail.requetes, 1)
        finally:
            for _, writer in connexions:
                writer.close()
                await writer.wait_closed()

    async def test_diagnostic_d_erreur_ne_journalise_pas_le_corps(self):
        with patch("builtins.print") as journal:
            reponse = await self.requete("POST", "/wifi", {"token": "abcdef", "ssid": "Maison", "mot_de_passe": "secret"})
        self.assertTrue(reponse.startswith(b"HTTP/1.1 400"))
        self.assertEqual(self.portail.erreurs, 1)
        self.assertNotIn("secret", str(journal.call_args_list))


class GesteAssociationTests(unittest.IsolatedAsyncioTestCase):
    async def verifier_geste(self, intervals):
        horloge = [0]
        class Pin:
            IN, PULL_UP = 0, 1
            def __init__(self, *args):
                self.gpio = args[0]
            def value(self):
                if self.gpio != 12:
                    raise AssertionError("Le portail doit utiliser le bouton principal, pas BOOT")
                return 0 if any(debut <= horloge[0] < fin for debut, fin in intervals) else 1
        async def avancer(secondes):
            horloge[0] += round(secondes * 1000)
        class Voyant:
            def afficher(self, couleur):
                self.couleur = couleur
        voyant = Voyant()
        with patch.dict(sys.modules, {"machine": SimpleNamespace(Pin=Pin)}), \
             patch.multiple(time, ticks_ms=lambda: horloge[0], ticks_diff=lambda a, b: a - b, create=True), \
             patch.object(asyncio, "sleep", side_effect=avancer), \
             patch.object(wifi, "ouvrir_portail", new_callable=unittest.mock.AsyncMock) as ouvrir, \
             patch("builtins.print"):
            await wifi.demander_portail(SimpleNamespace(), voyant)
            return ouvrir.await_count, horloge[0]

    async def test_aucun_appui_reprend_apres_quatre_secondes(self):
        ouvert, duree = await self.verifier_geste([])
        self.assertEqual(ouvert, 0)
        self.assertEqual(duree, 4000)

    async def test_appui_bref_n_ouvre_pas_le_portail(self):
        ouvert, duree = await self.verifier_geste([(500, 800)])
        self.assertEqual(ouvert, 0)
        self.assertEqual(duree, 4000)

    async def test_appui_long_dans_la_fenetre_ouvre_le_portail(self):
        ouvert, duree = await self.verifier_geste([(500, 4000)])
        self.assertEqual(ouvert, 1)
        self.assertEqual(duree, 3500)

    async def test_bouton_maintenu_des_la_mise_sous_tension_ouvre_le_portail(self):
        ouvert, duree = await self.verifier_geste([(0, 10_000)])
        self.assertEqual(ouvert, 1)
        self.assertEqual(duree, 3000)

    async def test_appuis_separes_ne_cumulent_pas_les_durees(self):
        ouvert, duree = await self.verifier_geste([(0, 1500), (2000, 3500)])
        self.assertEqual(ouvert, 0)
        self.assertEqual(duree, 4000)

    async def test_appui_commence_en_fin_de_fenetre_peut_se_terminer(self):
        ouvert, duree = await self.verifier_geste([(3500, 7000)])
        self.assertEqual(ouvert, 1)
        self.assertEqual(duree, 6500)


if __name__ == "__main__":
    unittest.main()
