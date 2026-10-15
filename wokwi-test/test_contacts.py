import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from contacts import valider_contacts, contacts_configuration
from pushbullet_reel import ApiErreur, LectureDifferee, ReseauReel, SuiviGroupe
from main import Boitier, ATTENTE, CONFIRMEE, REPOS, SANS_CONFIRMATION, VIOLET


CONTACTS = [{"nom": "Alice", "email": "alice@example.com", "actif": True},
            {"nom": "Bob", "email": "bob@example.com", "actif": True}]


def ok(email="bob@example.com", created=101, body="OK"):
    return {"iden": "ok1", "active": True, "type": "note", "created": created,
            "receiver_iden": "boitier", "sender_iden": "id-" + email,
            "sender_email": email, "direction": "incoming", "body": body}


class ContactsTests(unittest.TestCase):
    def test_normalise_rejette_doublons_limites_et_aucun_actif(self):
        self.assertEqual(valider_contacts([{"email": " ALICE@example.com "}])[0]["email"], "alice@example.com")
        for liste in ([], "alice@example.com", CONTACTS * 2,
                      [{"email": "a@example.com", "actif": False}],
                      [{"email": "a@example.com", "actif": "oui"}],
                      [{"email": "a@b@c"}], [{"email": "a\n@example.com"}],
                      [{"email": "a@example.com", "nom": "a" * 41}],
                      [{"email": "a@example.com", "nom": "a\nb"}],
                      [{"email": str(i) + "@example.com"} for i in range(9)]):
            with self.subTest(liste=liste), self.assertRaises(ValueError):
                valider_contacts(liste)

    def test_ancien_email_utilisable_et_liste_prioritaire(self):
        c = SimpleNamespace(DESTINATAIRE_EMAIL="ancien@example.com")
        self.assertEqual(contacts_configuration(c)[0]["email"], "ancien@example.com")
        c.DESTINATAIRES = CONTACTS
        self.assertEqual(contacts_configuration(c), CONTACTS)

    def groupe(self, liste=None):
        g = SuiviGroupe(valider_contacts(liste or CONTACTS), "Lit", "SESSION")
        g.identifier({"iden": "boitier", "email": "boitier@example.com"})
        g.ouvrir(1)
        g.accepte(1, {"iden": "push1", "created": 100, "receiver_iden": "id-alice@example.com"}, "alice@example.com")
        return g

    def test_premier_ok_de_tout_contact_actif_ferme_le_groupe(self):
        g = self.groupe()
        # Bob est autorise, meme si sa notification n'a pas encore ete acceptee.
        self.assertEqual(g.examiner(ok()), 1)
        self.assertTrue(g.terminee(1))
        self.assertIsNone(g.date_lecture())
        self.assertIsNone(g.examiner(ok("alice@example.com")))

    def test_contact_inconnu_inactif_ancien_ok_et_mauvais_code_ignores(self):
        for push in (ok("inconnu@example.com"), ok(created=99), ok(body="OK AUTRE-1")):
            with self.subTest(push=push):
                self.assertIsNone(self.groupe().examiner(push))
        liste = [CONTACTS[0], dict(CONTACTS[1], actif=False)]
        self.assertIsNone(self.groupe(liste).examiner(ok()))

    def test_ok_code_et_nouvel_incident_independant(self):
        g = self.groupe()
        self.assertEqual(g.examiner(ok(body="ok session-1")), 1)
        g.ouvrir(2)
        g.accepte(2, {"iden": "push2", "created": 200}, "alice@example.com")
        self.assertIsNone(g.examiner(ok(created=201)))  # Meme OK deja utilise.
        nouveau = dict(ok(created=201), iden="ok2", body="OK")
        self.assertEqual(g.examiner(nouveau), 2)

    def test_annonce_aux_autres_actifs_avec_nom_configure_et_reference(self):
        liste = CONTACTS + [{"nom": "Inactif", "email": "off@example.com", "actif": False}]
        g = self.groupe(liste)
        self.assertEqual(g.messages_confirmation(1), [])
        self.assertEqual(g.examiner(dict(ok(), sender_name="Nom non fiable")), 1)
        messages = g.messages_confirmation(1)
        self.assertEqual([m["email"] for m in messages], ["alice@example.com"])
        self.assertIn("Bob a répondu OK", messages[0]["body"])
        self.assertIn("SESSION-1", messages[0]["body"])
        self.assertIn("Lit", messages[0]["title"])
        self.assertIsNone(g.examiner(dict(ok("alice@example.com"), iden="ok2")))
        self.assertEqual(g.messages_confirmation(1), messages)

    def test_contact_unique_ne_se_notifie_pas_et_reponses_rejetees_sans_annonce(self):
        g = self.groupe([CONTACTS[0]])
        self.assertIsNone(g.examiner(ok()))
        self.assertEqual(g.messages_confirmation(1), [])
        self.assertEqual(g.examiner(ok("alice@example.com")), 1)
        self.assertEqual(g.messages_confirmation(1), [])


class TransportGroupeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.horloge = [0]
        self.patch = patch("pushbullet_reel.maintenant_ms", side_effect=lambda: self.horloge[0])
        self.patch.start()
        self.r = object.__new__(ReseauReel)
        r = self.r
        r.c = SimpleNamespace(INTERVALLE_RELANCE_MS=10_000)
        r.suivi = SuiviGroupe(CONTACTS, "Lit", "SESSION")
        r.suivi.identifier({"iden": "boitier", "email": "boitier@example.com"})
        r.journal = lambda message: None
        r.wifi = r.pushbullet = r.pret = True
        r.wlan = SimpleNamespace(isconnected=lambda: True)
        r.erreur_permanente = False
        r.pause_depuis, r.pause_ms = None, 0
        r.resultats, r.confirmations = [], []
        r.annonces = []
        r.en_cours = r.tache_envoi = None
        self.appels = []
        r.api = AsyncMock(side_effect=self.api)
        self.b = Boitier(lambda message: None, lambda a, b: a - b, r)

    async def asyncTearDown(self):
        if self.r.tache_envoi is not None and not self.r.tache_envoi.done():
            self.r.tache_envoi.cancel()
            try:
                await self.r.tache_envoi
            except asyncio.CancelledError:
                pass
        self.patch.stop()

    async def api(self, methode, chemin, charge):
        self.appels.append(charge)
        return {"iden": "push" + str(len(self.appels)), "created": 100 + self.horloge[0] // 1000,
                "receiver_iden": "id-" + charge["email"]}

    async def avancer(self, t, appui=False):
        self.horloge[0] = t
        self.b.actualiser(t, appui, False)
        tache = self.r.tache_envoi
        if tache is not None:
            await tache
            self.b.actualiser(t + 40, False, False)

    async def test_envoi_a_chacun_puis_un_ok_arrete_toutes_les_relances(self):
        await self.avancer(0, True)
        self.assertEqual([a["email"] for a in self.appels], [c["email"] for c in CONTACTS])
        self.assertEqual(self.b.envois, 1)
        self.r.confirmations.append(self.r.suivi.examiner(ok()))
        await self.avancer(100)
        self.assertEqual(self.b.etat, CONFIRMEE)
        await self.avancer(20_000)
        self.assertEqual(len(self.appels), 2)

    async def confirmer_par_lecture(self):
        await self.avancer(0, True)
        self.r.api = AsyncMock(return_value={"pushes": [ok(), ok("alice@example.com")]})
        await self.r.lire_reponses()
        self.assertEqual(self.r.confirmations, [1])
        self.assertEqual(len(self.r.annonces), 1)
        # La lecture ne fait aucun POST d'annonce et livre d'abord le vert.
        self.r.api.assert_awaited_once()
        await self.avancer(100)
        self.assertEqual(self.b.etat, CONFIRMEE)

    async def test_annonce_en_fond_une_fois_sans_compter_comme_alerte(self):
        await self.confirmer_par_lecture()
        self.r.api = AsyncMock(return_value={"iden": "annonce1"})
        await self.r.annoncer_confirmation()
        await self.r.annoncer_confirmation()
        self.r.api.assert_awaited_once()
        appel = self.r.api.call_args
        self.assertEqual(appel.args[:2], ("POST", "pushes"))
        self.assertEqual(appel.args[2]["email"], "alice@example.com")
        self.assertEqual(appel.kwargs, {"fond": True})
        self.assertEqual(self.b.envois, 1)
        self.assertEqual(self.b.etat, CONFIRMEE)

    async def test_echec_annonce_ne_reessaie_pas_et_conserve_confirmation(self):
        await self.confirmer_par_lecture()
        self.r.api = AsyncMock(side_effect=ApiErreur("resultat incertain", True))
        await self.r.annoncer_confirmation()
        await self.r.annoncer_confirmation()
        self.r.api.assert_awaited_once()
        self.assertEqual(self.b.etat, CONFIRMEE)
        self.assertEqual(self.r.annonces, [])

    async def test_geste_differe_annonce_et_nouveau_cycle_garde_ancienne_reference(self):
        await self.confirmer_par_lecture()
        self.r.api = AsyncMock(side_effect=LectureDifferee())
        with self.assertRaises(LectureDifferee):
            await self.r.annoncer_confirmation()
        self.assertEqual(len(self.r.annonces), 1)
        self.r.suivi.ouvrir(2)
        self.r.api = AsyncMock(return_value={"iden": "annonce1"})
        await self.r.annoncer_confirmation()
        self.assertIn("SESSION-1", self.r.api.call_args.args[2]["body"])
        self.assertFalse(self.r.suivi.terminee(2))

    async def test_echec_un_destinataire_n_empeche_pas_les_autres_annonces(self):
        await self.confirmer_par_lecture()
        self.r.annonces.append(dict(self.r.annonces[0], email="carol@example.com"))
        self.r.api = AsyncMock(side_effect=[OSError("prive"), {"iden": "annonce2"}])
        await self.r.annoncer_confirmation()
        await self.r.annoncer_confirmation()
        self.assertEqual(self.r.api.await_count, 2)
        self.assertEqual(self.r.annonces, [])
        self.assertEqual(self.b.etat, CONFIRMEE)

    async def test_echec_independant_reessai_seulement_du_contact_en_echec(self):
        original = self.api
        async def premier_echec(m, p, charge):
            if charge["email"] == "bob@example.com" and not any(a["email"] == charge["email"] for a in self.appels):
                self.appels.append(charge)
                raise OSError("ne pas afficher ce detail")
            return await original(m, p, charge)
        self.r.api.side_effect = premier_echec
        await self.avancer(0, True)
        self.assertEqual(self.b.envois, 1)
        await self.avancer(2000)
        self.assertEqual([a["email"] for a in self.appels], ["alice@example.com", "bob@example.com", "bob@example.com"])
        self.assertEqual(self.b.envois, 1)
        self.assertEqual([e["compteur"] for e in self.r.suivi.etats(1).values()], [1, 1])
        for i in range(1, 5):
            await self.avancer(i * 10_000)
            if i == 4:
                self.assertEqual(self.b.etat, ATTENTE)  # Bob n'a encore que 4 acceptations.
            await self.avancer(i * 10_000 + 2000)
        self.assertEqual(self.b.etat, SANS_CONFIRMATION)
        self.assertEqual([e["compteur"] for e in self.r.suivi.etats(1).values()], [5, 5])
        await self.avancer(100_000)
        self.assertEqual(len(self.appels), 11)  # Dix acceptations et un echec.

    async def test_contact_refuse_ne_bloque_pas_les_autres(self):
        original = self.api
        async def refuser(m, p, charge):
            if charge["email"] == "alice@example.com":
                self.appels.append(charge)
                raise ApiErreur("HTTP 400", statut=400)
            return await original(m, p, charge)
        self.r.api.side_effect = refuser
        await self.avancer(0, True)
        self.assertEqual(self.b.envois, 1)
        self.assertTrue(self.r.suivi.etats(1)["alice@example.com"]["bloque"])
        await self.avancer(10_000)
        self.assertEqual([a["email"] for a in self.appels].count("alice@example.com"), 1)
        self.assertEqual([a["email"] for a in self.appels].count("bob@example.com"), 2)

    async def test_annulation_partielle_ne_renvoie_pas_aux_contacts_deja_annules(self):
        await self.avancer(0, True)
        original = self.api
        echoue = [False]
        async def annuler(m, p, charge):
            if "ANNULATION" in charge["title"] and charge["email"] == "bob@example.com" and not echoue[0]:
                echoue[0] = True
                self.appels.append(charge)
                raise ApiErreur("indisponible", True)
            return await original(m, p, charge)
        self.r.api.side_effect = annuler
        self.b.annuler()
        await self.avancer(10_000)
        self.assertEqual(self.b.annulations_a_transmettre, [1])
        await self.avancer(12_000)
        self.assertEqual(self.b.annulations_a_transmettre, [])
        self.assertEqual(self.b.etat, REPOS)
        annulations = [a["email"] for a in self.appels if "ANNULATION" in a["title"]]
        self.assertEqual(annulations, ["alice@example.com", "bob@example.com", "bob@example.com"])

    async def test_ok_pendant_diffusion_empeche_les_contacts_suivants(self):
        original = self.api
        async def confirmer(m, p, charge):
            reponse = await original(m, p, charge)
            def livrer_ok():
                self.r.confirmations.append(self.r.suivi.examiner(ok("alice@example.com")))
            asyncio.get_running_loop().call_soon(livrer_ok)
            return reponse
        self.r.api.side_effect = confirmer
        await self.avancer(0, True)
        self.assertEqual(len(self.appels), 1)
        self.assertEqual(self.b.etat, CONFIRMEE)

    async def test_aucun_contact_accepte_reste_violet_sans_faux_compteur(self):
        self.r.api.side_effect = ApiErreur("HTTP 400", statut=400)
        await self.avancer(0, True)
        self.assertEqual(self.b.envois, 0)
        self.assertEqual(self.b.couleur(0), VIOLET)
        await self.avancer(5000)
        self.assertEqual(self.r.api.await_count, 2)

    async def test_interruption_pendant_post_annule_seulement_le_contact_possible(self):
        async def bloquer(m, p, charge):
            self.appels.append(charge)
            await asyncio.Event().wait()
        self.r.api.side_effect = bloquer
        self.assertTrue(self.r.commencer("AIDE", 1, 0))
        tache = self.r.tache_envoi
        await asyncio.sleep(0)
        self.r.interrompre_aide()
        await tache
        self.assertEqual(self.r.resultats, [])
        self.r.api.side_effect = self.api
        self.horloge[0] = 2000
        self.assertTrue(self.r.commencer("ANNULATION", 1, 2000))
        await self.r.tache_envoi
        self.assertEqual([a["email"] for a in self.appels], ["alice@example.com", "alice@example.com"])

    def activer_api(self, reponses):
        del self.r.api
        self.r.c.DELAI_HTTP_MS = 1000
        self.r.c.DELAI_CONNEXION_MS = 1000
        self.r.verrou = asyncio.Lock()
        self.r.https = AsyncMock(side_effect=reponses)

    async def test_http_400_sur_un_contact_ne_bloque_pas_le_post_suivant(self):
        self.activer_api([(400, {}, {}), (200, {}, {"iden": "b", "created": 100})])
        await self.avancer(0, True)
        self.assertFalse(self.r.erreur_permanente)
        self.assertEqual(self.r.https.await_count, 2)
        self.assertEqual(self.b.envois, 1)

    async def test_http_401_arrete_le_groupe_et_signale_jeton_refuse(self):
        self.activer_api([(401, {}, {})])
        await self.avancer(0, True)
        self.assertTrue(self.r.erreur_permanente)
        self.assertEqual(self.r.https.await_count, 1)
        self.assertEqual(self.b.envois, 0)

    async def test_http_429_reporte_aussi_les_contacts_non_encore_servis(self):
        self.activer_api([(429, {"retry-after": "30"}, {}),
                         (200, {}, {"iden": "a", "created": 130}),
                         (200, {}, {"iden": "b", "created": 130})])
        await self.avancer(0, True)
        self.assertTrue(self.r.en_pause())
        self.assertEqual(self.b.envois, 0)
        await self.avancer(29_000)
        self.assertEqual(self.r.https.await_count, 1)
        self.r.pret = True  # Verification du compte reussie a la reprise.
        await self.avancer(30_000)
        self.assertEqual(self.r.https.await_count, 3)
        self.assertEqual([e["compteur"] for e in self.r.suivi.etats(1).values()], [1, 1])
