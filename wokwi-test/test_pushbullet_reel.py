import asyncio
from types import SimpleNamespace
from pathlib import Path
import ssl
import sys
import tempfile
import struct
import unittest
from unittest.mock import AsyncMock, patch

from pushbullet_reel import (ApiErreur, ReseauReel, SuiviPushbullet, INACTIVITE_HTTPS_MS,
                             charger_certificats, decrire_erreur_transport,
                             decoder_json_serveur, horodatage_ms,
                             lire_reponse_http, valider_configuration)


class ReponsesTests(unittest.TestCase):
    def setUp(self):
        self.s = SuiviPushbullet("proche@example.com", "Lit", "ABC123")
        self.s.identifier({"iden": "expediteur", "email": "boitier@example.com"})
        self.s.ouvrir(1)
        self.s.accepte(1, {"iden": "alerte1", "created": 100})
        self.ok = {"iden": "reponse1", "active": True, "type": "note", "created": 101,
                   "receiver_iden": "expediteur", "direction": "incoming",
                   "sender_email": "proche@example.com", "body": "  oK  "}

    def test_ok_autorise_insensible_a_la_casse(self):
        self.assertEqual(self.s.examiner(self.ok), 1)
        self.assertIsNone(self.s.examiner(self.ok))

    def test_ok_avec_reference_du_cycle(self):
        self.ok["body"] = "ok abc123-1"
        self.assertEqual(self.s.examiner(self.ok), 1)

    def test_mauvaise_reference_rejetee(self):
        self.ok["body"] = "OK ABC123-2"
        self.assertIsNone(self.s.examiner(self.ok))

    def test_compte_inconnu_ne_confirme_pas(self):
        self.ok["sender_email"] = "inconnu@example.com"
        self.assertIsNone(self.s.examiner(self.ok))

    def test_ancienne_reponse_ne_confirme_pas_nouveau_cycle(self):
        self.s.ouvrir(2)
        self.s.accepte(2, {"iden": "alerte2", "created": 200})
        self.assertIsNone(self.s.examiner(self.ok))

    def test_reponse_deja_utilisee_non_reutilisable(self):
        self.s.examiner(self.ok)
        self.s.ouvrir(2)
        self.s.accepte(2, {"iden": "alerte2", "created": 200})
        self.ok["created"] = 201
        self.assertIsNone(self.s.examiner(self.ok))

    def test_annulation_ne_peut_pas_etre_reactivee(self):
        self.s.fermer(1)
        self.assertIsNone(self.s.examiner(self.ok))

    def test_mauvais_compte_destinataire_rejete(self):
        self.ok["receiver_iden"] = "autre"
        self.assertIsNone(self.s.examiner(self.ok))

    def test_envoi_vers_soi_reponse_self_acceptee(self):
        self.s.destinataire = "boitier@example.com"
        self.ok.update(direction="self", sender_iden="expediteur")
        self.assertEqual(self.s.examiner(self.ok), 1)

    def test_acceptation_sans_date_interdit_confirmation(self):
        self.s.ouvrir(2)
        self.s.accepte(2, {"iden": "alerte2"})
        self.assertIsNone(self.s.date_lecture())
        self.assertIsNone(self.s.examiner(self.ok))

    def test_acceptation_sans_identifiant_est_incertaine(self):
        with self.assertRaises(ApiErreur) as erreur:
            self.s.accepte(1, {"created": 100})
        self.assertTrue(erreur.exception.incertain)

    def test_aide_et_annulation_clairement_marquees_test(self):
        for nature in ("AIDE", "ANNULATION"):
            charge = self.s.charge(nature, 1)
            self.assertIn("TEST", charge["title"])
            self.assertIn("aucune intervention necessaire", charge["body"])
            self.assertEqual(charge["email"], "proche@example.com")

    def test_email_original_autorise_malgre_normalisation_differente(self):
        self.ok["sender_email_normalized"] = "alias@example.com"
        self.assertEqual(self.s.examiner(self.ok), 1)

    def test_destinataire_effectif_identifie_par_reponse_de_envoi(self):
        self.s.accepte(1, {"iden": "alerte2", "created": "100.1", "receiver_iden": "proche"})
        self.ok.update(sender_iden="proche", sender_email="alias@example.com")
        self.assertEqual(self.s.examiner(self.ok), 1)

    def test_identifiant_mauvais_rejete_meme_email_identique(self):
        self.s.accepte(1, {"iden": "alerte2", "created": "100.1", "receiver_iden": "proche"})
        self.ok["sender_iden"] = "inconnu"
        self.assertIsNone(self.s.examiner(self.ok))

    def test_alias_propre_compte_identifie_par_destinataire_effectif(self):
        self.s.accepte(1, {"iden": "alerte2", "created": "100.1", "receiver_iden": "expediteur"})
        self.ok.update(direction="self", sender_iden="expediteur")
        self.assertEqual(self.s.examiner(self.ok), 1)


class DatesServeurTests(unittest.TestCase):
    def test_date_texte_et_notation_scientifique_sans_float(self):
        for texte in ("1791793324.56789", "1.79179332456789e9", "1791793324567.89e-3"):
            self.assertEqual(horodatage_ms(texte), 1_791_793_324_567)

    def test_dates_invalides_refusees(self):
        for valeur in (None, True, False, {}, "nan", "inf", "-100", "100e10000", "1.2.3", "", "0"):
            self.assertIsNone(horodatage_ms(valeur))

    def test_dates_json_preservees_sans_modifier_texte_message(self):
        contenu = b'{"created":1791793324.56789,"modified":1.791793325012e9,"body":"\\\"created\\\":1791793000.01","valeur":"created"}'
        resultat = decoder_json_serveur(contenu)
        self.assertEqual(resultat["created"], "1791793324.56789")
        self.assertEqual(resultat["modified"], "1.791793325012e9")
        self.assertEqual(resultat["body"], '"created":1791793000.01')
        self.assertEqual(resultat["valeur"], "created")

    def test_json_incomplet_rejete(self):
        with self.assertRaises(ApiErreur):
            decoder_json_serveur(b'{"body":"incomplet')

    def test_messages_avec_antislash_guillemets_et_unicode_intacts(self):
        import json
        for corps in ('un antislash \\', '\\\\"created":12.3', 'éclair "created":12.3',
                      'fin \\"', 'avant "modified" après'):
            objet = {"body": corps, "created": 1791793350, "autre": [corps, {"modified": 100}]}
            resultat = decoder_json_serveur(json.dumps(objet).encode())
            self.assertEqual(resultat["body"], corps)
            self.assertEqual(resultat["autre"][0], corps)
            self.assertEqual(resultat["created"], "1791793350")
            self.assertEqual(resultat["autre"][1]["modified"], "100")

    def test_ok_recent_reconnu_meme_si_float32_arrondirait_alerte_vers_futur(self):
        alerte = "1791793350.56789"
        approximation = struct.unpack("f", struct.pack("f", float(alerte)))[0]
        self.assertGreater(approximation, float(alerte) + 1)
        suivi = SuiviPushbullet("proche@example.com", "Lit", "DATE")
        suivi.identifier({"iden": "expediteur", "email": "boitier@example.com"})
        suivi.ouvrir(1)
        suivi.accepte(1, {"iden": "aide", "created": alerte})
        self.assertEqual(suivi.date_lecture(), 1_791_793_349)
        self.assertIsInstance(suivi.date_lecture(), int)
        ancien = {"iden": "ancien", "active": True, "type": "note",
                  "created": "1791793350.566", "receiver_iden": "expediteur",
                  "direction": "incoming", "sender_email": "proche@example.com", "body": "ok"}
        self.assertIsNone(suivi.examiner(ancien))
        nouveau = dict(ancien, iden="recent", created="1791793351.001")
        self.assertEqual(suivi.examiner(nouveau), 1)

    def test_exactitude_date_alerte_et_ok_depuis_json_http(self):
        suivi = SuiviPushbullet("proche@example.com", "Lit", "JSON")
        suivi.identifier({"iden": "expediteur", "email": "boitier@example.com"})
        suivi.ouvrir(1)
        suivi.accepte(1, decoder_json_serveur(b'{"iden":"aide","created":1791793324.56789}'))
        reponse = decoder_json_serveur(b'{"iden":"ok","active":true,"type":"note","created":1791793325.001,"receiver_iden":"expediteur","direction":"incoming","sender_email":"proche@example.com","body":"OK"}')
        self.assertEqual(suivi.examiner(reponse), 1)


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def lire(self, contenu, diagnostic=None):
        lecteur = asyncio.StreamReader()
        lecteur.feed_data(contenu)
        lecteur.feed_eof()
        return await lire_reponse_http(lecteur, diagnostic)

    async def test_reponse_avec_longueur(self):
        statut, _, donnees = await self.lire(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')
        self.assertEqual((statut, donnees), (200, {}))

    async def test_reponse_decoupee_en_blocs(self):
        _, _, donnees = await self.lire(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n1\r\n{\r\n1\r\n}\r\n0\r\n\r\n')
        self.assertEqual(donnees, {})

    async def test_corps_tronque_ne_devient_pas_acceptation(self):
        with self.assertRaises(asyncio.IncompleteReadError):
            await self.lire(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n{}')

    async def test_erreur_401_sans_afficher_ni_parser_corps(self):
        statut, _, donnees = await self.lire(b'HTTP/1.1 401 Unauthorized\r\nContent-Length: 3\r\n\r\nxxx')
        self.assertEqual((statut, donnees), (401, {}))

    async def test_corps_trop_grand_rejete(self):
        with self.assertRaises(ApiErreur):
            await self.lire(b'HTTP/1.1 200 OK\r\nContent-Length: 9999999\r\n\r\n')

    async def test_diagnostic_identifie_les_etapes_sans_contenu_prive(self):
        etapes = []
        await self.lire(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}', etapes.append)
        self.assertEqual(etapes, ["lecture du statut HTTP", "lecture des entetes (HTTP 200)",
                                 "lecture du corps HTTP"])

    async def test_deux_reponses_apres_blocs_et_trailers(self):
        lecteur = asyncio.StreamReader()
        lecteur.feed_data(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n'
                          b'2\r\n{}\r\n0\r\nX-Test: fin\r\n\r\n'
                          b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')
        lecteur.feed_eof()
        for _ in range(2):
            self.assertEqual((await lire_reponse_http(lecteur))[2], {})

    async def test_fin_blocs_incomplete_ne_permet_pas_reutilisation(self):
        with self.assertRaisesRegex(ApiErreur, "Fin de reponse"):
            await self.lire(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n0\r\n')

    async def test_http_10_fermeture_par_defaut(self):
        _, entetes, _ = await self.lire(b'HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\n{}')
        self.assertEqual(entetes["connection"], "close")


class TransportTests(unittest.IsolatedAsyncioTestCase):
    def transport(self):
        r = object.__new__(ReseauReel)
        r.journal = lambda message: None
        r.suivi = SuiviPushbullet("proche@example.com", "Lit", "SESSION")
        r.resultats = []
        r.confirmations = []
        r.en_cours = None
        r.pret = True
        r.tache_envoi = None
        r.disponible = lambda: True
        r.api = AsyncMock(return_value={"iden": "push", "created": 100})
        return r

    async def test_envoi_accepte_produit_un_resultat(self):
        r = self.transport()
        self.assertTrue(r.commencer("AIDE", 1, 0))
        await r.tache_envoi
        resultat = r.resultat(1)
        self.assertTrue(resultat["accepte"])
        self.assertIsNone(r.en_cours)
        self.assertIsNone(r.resultat(2))

    async def test_echec_de_transport_signale_incertitude(self):
        r = self.transport()
        r.api.side_effect = OSError("detail non affiche")
        r.commencer("AIDE", 1, 0)
        await r.tache_envoi
        resultat = r.resultat(1)
        self.assertFalse(resultat["accepte"])
        self.assertIn("incertain", resultat["erreur"])
        self.assertNotIn("detail non affiche", resultat["erreur"])

    async def test_annulation_avant_demarrage_tache_ne_bloque_pas_file(self):
        r = self.transport()
        r.commencer("AIDE", 1, 0)
        tache = r.tache_envoi
        r.interrompre_aide()
        self.assertIsNone(r.en_cours)
        try:
            await tache
        except asyncio.CancelledError:
            pass
        self.assertEqual(r.resultats, [])
        self.assertTrue(r.commencer("ANNULATION", 1, 1))
        await r.tache_envoi
        self.assertTrue(r.resultat(2)["accepte"])

    async def test_bouton_v_ne_fabrique_pas_de_confirmation(self):
        r = self.transport()
        r.simuler_ok(1)
        self.assertEqual(r.confirmations, [])

    async def test_rejet_ok_diagnostique_sans_message_prive(self):
        r = self.transport()
        r.suivi.identifier({"iden": "expediteur", "email": "boitier@example.com"})
        r.suivi.ouvrir(1)
        r.suivi.accepte(1, {"iden": "aide", "created": "1791793350.56789"})
        r.api.return_value = {"pushes": [{"iden": "ok", "active": True, "type": "note",
                                        "created": "1791793351.001", "receiver_iden": "expediteur",
                                        "sender_email": "prive@example.com", "direction": "incoming",
                                        "body": "ok", "title": "titre prive"}]}
        messages = []
        r.journal = messages.append
        await r.lire_reponses()
        self.assertEqual(r.confirmations, [])
        diagnostic = "\n".join(messages)
        self.assertIn("1 textes OK", diagnostic)
        self.assertIn("expediteur ou sens du message non autorise", diagnostic)
        self.assertNotIn("prive", diagnostic)
        chemin = r.api.call_args.args[1]
        self.assertIn("modified_after=1791793349", chemin)

    async def test_ok_reconnu_depuis_page_de_dates_exactes(self):
        r = self.transport()
        r.suivi.identifier({"iden": "expediteur", "email": "boitier@example.com"})
        r.suivi.ouvrir(1)
        r.suivi.accepte(1, {"iden": "aide", "created": "1791793350.56789", "receiver_iden": "proche"})
        r.api.return_value = decoder_json_serveur(b'{"pushes":[{"iden":"ok","active":true,"type":"note","created":1791793351.001,"receiver_iden":"expediteur","sender_iden":"proche","direction":"incoming","body":"ok"}]}')
        await r.lire_reponses()
        self.assertEqual(r.confirmations, [1])

    async def test_401_bloque_envois_et_429_respecte_pause(self):
        r = self.transport()
        del r.api
        r.c = SimpleNamespace(DELAI_HTTP_MS=1000)
        r.verrou = asyncio.Lock()
        r.wifi = r.pushbullet = True
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        r.erreur_permanente = False
        r.https = AsyncMock(return_value=(401, {}, {}))
        with self.assertRaises(ApiErreur):
            await r.api("POST", "pushes", {})
        self.assertTrue(r.erreur_permanente)
        r.https.return_value = (429, {"retry-after": "120"}, {})
        with self.assertRaises(ApiErreur):
            await r.api("GET", "pushes")
        self.assertEqual(r.pause_ms, 120_000)
        self.assertTrue(r.en_pause())


    async def test_delai_depasse_precise_etape_et_incertitude_post(self):
        r = self.transport()
        del r.api
        r.c = SimpleNamespace(DELAI_HTTP_MS=1000)
        r.verrou = asyncio.Lock()
        r.wifi = r.pushbullet = True
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        r.etape_http = "envoi HTTPS et negociation TLS"
        r.https = AsyncMock(side_effect=asyncio.TimeoutError)
        for methode in ("GET", "POST"):
            with self.assertRaisesRegex(ApiErreur, "negociation TLS") as erreur:
                await r.api(methode, "users/me")
            self.assertEqual(erreur.exception.incertain, methode == "POST")


    async def test_oserror_precise_code_etape_et_incertitude_sans_secret(self):
        r = self.transport()
        del r.api
        r.c = SimpleNamespace(DELAI_HTTP_MS=1000)
        r.verrou = asyncio.Lock()
        r.wifi = r.pushbullet = True
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        r.etape_http = "envoi HTTPS et negociation TLS"
        r.https = AsyncMock(side_effect=OSError(-12345, "secret-test"))
        for methode in ("GET", "POST"):
            with self.assertRaises(ApiErreur) as resultat:
                await r.api(methode, "users/me")
            self.assertIn("code=-12345", str(resultat.exception))
            self.assertIn("negociation TLS", str(resultat.exception))
            self.assertNotIn("secret-test", str(resultat.exception))
            self.assertEqual(resultat.exception.incertain, methode == "POST")

    async def test_indicateur_communication_visible_avant_https_et_efface_apres(self):
        r = self.transport()
        del r.api
        r.c = SimpleNamespace(DELAI_HTTP_MS=1000)
        r.verrou = asyncio.Lock()
        r.wifi = r.pushbullet = True
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        rendu = []

        async def affichage_avant_reseau(duree):
            rendu.append(r.communication_en_cours)

        async def https(methode, chemin, corps):
            self.assertEqual(rendu, [True])
            self.assertTrue(r.communication_en_cours)
            return 200, {}, {}

        r.https = https
        with patch("pushbullet_reel.asyncio.sleep", new=AsyncMock(side_effect=affichage_avant_reseau)):
            await r.api("GET", "pushes")
        self.assertFalse(r.communication_en_cours)

    async def test_indicateur_efface_apres_echec_ou_annulation(self):
        for erreur in (OSError(104), asyncio.TimeoutError(), asyncio.CancelledError()):
            r = self.transport()
            del r.api
            r.c = SimpleNamespace(DELAI_HTTP_MS=1000)
            r.verrou = asyncio.Lock()
            r.wifi = r.pushbullet = True
            r.wlan = SimpleNamespace(isconnected=lambda: True)
            r.https = AsyncMock(side_effect=erreur)
            with self.assertRaises((ApiErreur, asyncio.CancelledError)):
                await r.api("GET", "pushes")
            self.assertFalse(r.communication_en_cours)

    async def test_pwm_cyan_pose_avant_appel_bloquant_puis_retour_bleu(self):
        import time
        import main as simulation
        r = self.transport()
        del r.api
        r.c = SimpleNamespace(DELAI_HTTP_MS=1000)
        r.verrou = asyncio.Lock()
        r.wifi = r.pushbullet = True
        r.communication_en_cours = False
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b, r)

        class Sortie:
            valeur = 0
            def duty_u16(self, valeur):
                self.valeur = valeur

        sorties = [Sortie(), Sortie(), Sortie()]
        voyant = simulation.VoyantRGB(sorties)

        async def boucle_voyant():
            while True:
                voyant.afficher_etat(b, 0)
                await asyncio.sleep(0.005)

        async def https(methode, chemin, corps):
            self.assertEqual([s.valeur for s in sorties], [0, 65535, 65535])
            # Simuler un appel natif qui retient l'interpreteur. Le PWM
            # deja pose ne depend pas du passage suivant dans la boucle.
            time.sleep(0.04)
            self.assertEqual([s.valeur for s in sorties], [0, 65535, 65535])
            return 200, {}, {}

        r.https = https
        tache = asyncio.create_task(boucle_voyant())
        try:
            await r.api("GET", "pushes")
            await asyncio.sleep(0.01)
            self.assertEqual([s.valeur for s in sorties], [0, 0, 65535])
        finally:
            tache.cancel()
            try:
                await tache
            except asyncio.CancelledError:
                pass

    async def test_fermeture_ne_masque_pas_erreur_de_negociation(self):
        r = self.transport()
        r.c = SimpleNamespace(JETON_PUSHBULLET="secret-test", TRACE_HTTPS=False)
        r.tls = object()
        lecteur = SimpleNamespace()
        ecrivain = SimpleNamespace(write=lambda contenu: None,
                                  drain=AsyncMock(side_effect=OSError(-12345, "secret-test")),
                                  close=lambda: (_ for _ in ()).throw(OSError(9)))
        r.ouvrir_https = AsyncMock(return_value=(lecteur, ecrivain))
        with self.assertRaises(OSError) as resultat:
            await r.https("GET", "users/me")
        self.assertEqual(resultat.exception.args[0], -12345)


class ConnexionPersistanteTests(unittest.IsolatedAsyncioTestCase):
    def transport(self, contenu):
        r = object.__new__(ReseauReel)
        r.c = SimpleNamespace(JETON_PUSHBULLET="secret-test", TRACE_HTTPS=False)
        r.journal = lambda message: None
        lecteur = asyncio.StreamReader()
        lecteur.feed_data(contenu)
        lecteur.feed_eof()
        ecrivain = SimpleNamespace(write=lambda contenu: None, drain=AsyncMock(),
                                  close=lambda: None, wait_closed=AsyncMock())
        r.ouvrir_https = AsyncMock(return_value=(lecteur, ecrivain))
        return r, ecrivain

    async def test_deux_get_ne_negocient_tls_qu_une_fois(self):
        reponse = b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}'
        r, ecrivain = self.transport(reponse * 2)
        await r.https("GET", "users/me")
        await r.https("GET", "pushes")
        self.assertEqual(r.ouvrir_https.await_count, 1)
        self.assertEqual(ecrivain.drain.await_count, 2)
        self.assertEqual(ecrivain.wait_closed.await_count, 0)

    async def test_fermeture_demandee_par_serveur_respectee(self):
        r, ecrivain = self.transport(b'HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 2\r\n\r\n{}')
        await r.https("GET", "users/me")
        self.assertIsNone(r.connexion_https)
        self.assertEqual(ecrivain.wait_closed.await_count, 1)

    async def test_reponse_sans_longueur_ne_conserve_pas_connexion(self):
        r, _ = self.transport(b'HTTP/1.1 200 OK\r\n\r\n{}')
        await r.https("GET", "users/me")
        self.assertIsNone(r.connexion_https)

    async def test_annulation_envoi_ferme_flux_sans_reessai_post(self):
        r, ecrivain = self.transport(b'')
        ecrivain.drain.side_effect = asyncio.CancelledError
        with self.assertRaises(asyncio.CancelledError):
            await r.https("POST", "pushes", {})
        self.assertIsNone(r.connexion_https)
        self.assertEqual(ecrivain.wait_closed.await_count, 1)
        self.assertEqual(r.ouvrir_https.await_count, 1)

    async def test_reponse_tronquee_ferme_flux_sans_reessai_post(self):
        r, ecrivain = self.transport(b'HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\n{}')
        with self.assertRaises(asyncio.IncompleteReadError):
            await r.https("POST", "pushes", {})
        self.assertIsNone(r.connexion_https)
        self.assertEqual(ecrivain.wait_closed.await_count, 1)
        self.assertEqual(r.ouvrir_https.await_count, 1)

    async def test_connexion_inactive_ou_wifi_change_est_remplacee(self):
        for perimee in (False, True):
            r, ecrivain = self.transport(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')
            ancien = SimpleNamespace(close=lambda: None, wait_closed=AsyncMock())
            r.connexion_https = (None, ancien)
            r.connexion_perimee = perimee
            r.derniere_utilisation_https = 1
            with patch("pushbullet_reel.maintenant_ms", return_value=INACTIVITE_HTTPS_MS + 2):
                await r.https("GET", "users/me")
            self.assertEqual(ancien.wait_closed.await_count, 1)
            self.assertEqual(r.ouvrir_https.await_count, 1)
            self.assertEqual(ecrivain.wait_closed.await_count, 0)

    async def test_cache_dns_garde_nom_hote_pour_tls(self):
        r, _ = self.transport(b'')
        del r.ouvrir_https
        r.tls = object()
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("192.0.2.1", 443))]) as dns, \
                patch("pushbullet_reel.asyncio.open_connection", new=AsyncMock()) as ouvrir:
            await r.ouvrir_https()
            await r.ouvrir_https()
        self.assertEqual(dns.call_count, 1)
        self.assertEqual(ouvrir.await_count, 2)
        ouvrir.assert_awaited_with("192.0.2.1", 443, ssl=r.tls, server_hostname="api.pushbullet.com")

    async def test_diagnostic_explique_fermeture_sans_entetes_prives(self):
        r, _ = self.transport(b'HTTP/1.1 200 OK\r\nConnection: close\r\n'
                              b'X-Prive: secret-test\r\nContent-Length: 2\r\n\r\n{}')
        r.c.TRACE_HTTPS = True
        messages = []
        r.journal = messages.append
        await r.https("GET", "pushes?cursor=secret-test")
        traces = "\n".join(messages)
        self.assertIn("fermeture=True ; longueur=True ; blocs=False", traces)
        self.assertIn("serveur demande Connection: close", traces)
        self.assertNotIn("secret-test", traces)

    async def test_diagnostic_mesure_ecriture_synchrone_tls(self):
        r, _ = self.transport(b'HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\n{}')
        messages = []
        r.journal = messages.append
        with patch("pushbullet_reel.maintenant_ms", side_effect=[0, 0, 650, 650]):
            await r.https("GET", "pushes")
        self.assertTrue(any("Appel TLS write sans await : 650 ms" in x for x in messages))


class BoucleReseauTests(unittest.IsolatedAsyncioTestCase):
    async def test_intervalle_ok_compte_apres_fin_lecture_lente(self):
        r = object.__new__(ReseauReel)
        r.c = SimpleNamespace(INTERVALLE_LECTURE_MS=5000)
        r.wifi = r.pushbullet = r.pret = r.horloge_prete = True
        r.erreur_permanente = False
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        r.en_pause = lambda: False
        r.suivi = SimpleNamespace(date_lecture=lambda: 100)
        r.dernier_ok = None
        horloge = [0]
        pauses = [0]

        async def lire_lentement():
            horloge[0] += 6000

        async def dormir(duree):
            pauses[0] += 1
            horloge[0] += 1000
            if pauses[0] == 2:
                raise asyncio.CancelledError

        r.lire_reponses = AsyncMock(side_effect=lire_lentement)
        with patch("pushbullet_reel.maintenant_ms", side_effect=lambda: horloge[0]), \
                patch("pushbullet_reel.asyncio.sleep", new=AsyncMock(side_effect=dormir)):
            with self.assertRaises(asyncio.CancelledError):
                await r.boucle_reseau()
        self.assertEqual(r.lire_reponses.await_count, 1)
        self.assertEqual(r.dernier_ok, 6000)

    async def test_diagnostic_pause_signale_seuil_uniquement(self):
        for pause, nombre_attendu in ((30, 0), (500, 1)):
            r = object.__new__(ReseauReel)
            r.etape_http = "envoi HTTPS et negociation TLS"
            messages = []
            r.journal = messages.append
            with patch("pushbullet_reel.maintenant_ms", side_effect=[0, pause]), \
                    patch("pushbullet_reel.asyncio.sleep", new=AsyncMock(
                        side_effect=[None, asyncio.CancelledError])):
                with self.assertRaises(asyncio.CancelledError):
                    await r.surveiller_reactivite()
            self.assertEqual(len(messages), nombre_attendu)
            if nombre_attendu:
                self.assertIn("500 ms", messages[0])
                self.assertIn("negociation TLS", messages[0])

    async def test_arret_reseau_ferme_la_connexion(self):
        r = object.__new__(ReseauReel)
        r.tache_envoi = None
        r.surveiller_reactivite = AsyncMock()
        r.boucle_reseau = AsyncMock(side_effect=asyncio.CancelledError)
        r.fermer_https = AsyncMock()
        with self.assertRaises(asyncio.CancelledError):
            await r.boucle()
        r.fermer_https.assert_awaited_once()


class DiagnosticTests(unittest.TestCase):
    def test_oserror_libelle_tls_connu_seulement(self):
        diagnostic = decrire_erreur_transport(OSError("SSL_CONN_EOF secret-test"))
        self.assertIn("SSL_CONN_EOF", diagnostic)
        self.assertNotIn("secret-test", diagnostic)

    def test_arguments_inconnus_non_recopies(self):
        self.assertEqual(decrire_erreur_transport(OSError("secret-test")), "OSError")


class CertificatsTests(unittest.TestCase):
    def test_certificats_pem_charges_depuis_fichier(self):
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        charger_certificats(contexte, str(Path(__file__).parent / "ca.pem"))
        self.assertEqual(contexte.cert_store_stats()["x509_ca"], 15)

    def test_module_python_utilise_si_pem_absent(self):
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with tempfile.TemporaryDirectory() as dossier:
            charger_certificats(contexte, str(Path(dossier) / "absent.pem"))
        self.assertEqual(contexte.cert_store_stats()["x509_ca"], 15)

    def test_message_explicite_si_deux_sources_absentes(self):
        contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with tempfile.TemporaryDirectory() as dossier, patch.dict(sys.modules, {"certificats": None}):
            with self.assertRaisesRegex(ValueError, "ajouter ca.pem ou certificats.py"):
                charger_certificats(contexte, str(Path(dossier) / "absent.pem"))


class ConfigurationTests(unittest.TestCase):
    def test_jeton_vide_refuse_sans_message_reel(self):
        with self.assertRaisesRegex(ValueError, "JETON_PUSHBULLET"):
            valider_configuration(SimpleNamespace(JETON_PUSHBULLET=""))

    def test_jeton_avec_injection_entete_refuse(self):
        with self.assertRaisesRegex(ValueError, "Jeton invalide"):
            valider_configuration(SimpleNamespace(JETON_PUSHBULLET="test\r\nSecret: exemple"))


if __name__ == "__main__":
    unittest.main()
