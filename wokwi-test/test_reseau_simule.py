import unittest

import main as simulation


class FauxReseauTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.ecart = lambda a, b: a - b
        self.reseau = simulation.ReseauSimule(self.logs.append, self.ecart, latence_ms=500)
        self.b = simulation.Boitier(self.logs.append, self.ecart, self.reseau)

    def pas(self, t, aide=False, ok=False, wifi=None, pushbullet=None):
        self.b.actualiser(t, aide, ok, wifi, pushbullet)

    def demander(self):
        self.pas(0, aide=True)
        self.pas(40)
        self.pas(500)

    def test_acceptation_differee_et_un_seul_envoi_en_cours(self):
        self.pas(0, aide=True)
        self.assertEqual(self.b.envois, 0)
        for t in (40, 100, 499):
            self.pas(t)
        self.assertEqual(self.b.tentatives, 1)
        self.pas(500)
        self.assertEqual(self.b.envois, 1)
        self.assertEqual(self.reseau.messages, [("AIDE", 1)])

    def test_aide_hors_ligne_reste_locale_puis_part_a_reconnexion(self):
        self.reseau.configurer(wifi=False)
        self.pas(0, aide=True)
        self.pas(20_000)
        self.assertEqual((self.b.envois, self.b.tentatives), (0, 0))
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual(self.b.couleur(0), simulation.VIOLET)
        self.reseau.configurer(wifi=True)
        self.pas(20_100)
        self.assertEqual(self.b.tentatives, 1)
        self.pas(20_600)
        self.assertEqual(self.b.envois, 1)

    def test_pushbullet_indisponible_malgre_wifi(self):
        self.reseau.configurer(pushbullet=False)
        self.pas(0, aide=True)
        self.pas(40)
        self.assertEqual(self.b.envois, 0)
        self.reseau.configurer(pushbullet=True)
        self.pas(100)
        self.pas(600)
        self.assertEqual(self.b.envois, 1)

    def test_coupure_pendant_requete_ne_consomme_pas_notification(self):
        self.pas(0, aide=True)
        self.reseau.configurer(wifi=False)
        self.pas(40)
        self.assertEqual(self.b.envois, 0)
        self.assertEqual(self.reseau.messages, [])
        self.reseau.configurer(wifi=True)
        self.pas(100)
        self.pas(600)
        self.assertEqual((self.b.tentatives, self.b.envois), (2, 1))

    def test_coupure_breve_conserve_echec_de_requete(self):
        self.pas(0, aide=True)
        self.reseau.configurer(wifi=False)
        self.reseau.configurer(wifi=True)
        self.pas(40)
        self.assertEqual(self.b.envois, 0)
        self.pas(1_999)
        self.assertEqual(self.b.tentatives, 1)
        self.pas(2_000)
        self.pas(2_500)
        self.assertEqual(self.b.envois, 1)

    def test_ok_avant_premiere_acceptation_ignore(self):
        self.pas(0, aide=True)
        self.pas(40, ok=True)
        self.pas(500)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.pas(600, ok=True)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)

    def test_ok_proche_attend_reconnexion_du_boitier(self):
        self.demander()
        self.reseau.configurer(wifi=False)
        self.pas(600, ok=True)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual(self.reseau.confirmations, [1])
        self.reseau.configurer(wifi=True)
        self.pas(10_000)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)
        self.assertEqual(self.b.envois, 1)  # OK lu avant la relance devenue due.

    def test_ok_non_depose_si_pushbullet_en_panne(self):
        self.demander()
        self.reseau.configurer(pushbullet=False)
        self.pas(600, ok=True)
        self.reseau.configurer(pushbullet=True)
        self.pas(1_000)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual(self.reseau.confirmations, [])

    def test_annulation_hors_ligne_transmise_une_seule_fois(self):
        self.demander()
        self.reseau.configurer(wifi=False)
        self.pas(600, aide=True)
        self.pas(10_600, aide=True)
        self.pas(10_640)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.annulations_a_transmettre, [1])
        self.reseau.configurer(wifi=True)
        self.pas(11_000)
        self.pas(11_500)
        self.pas(20_000)
        self.assertEqual(self.b.annulations_a_transmettre, [])
        self.assertEqual(self.reseau.messages, [("AIDE", 1), ("ANNULATION", 1)])
        self.assertEqual(self.b.couleur(20_000), (0, 0, 255))

    def test_annulation_avant_toute_tentative_ne_transmet_pas_ancienne_aide(self):
        self.reseau.configurer(wifi=False)
        self.pas(0, aide=True)
        self.pas(40)
        self.pas(100, aide=True)
        self.pas(10_100, aide=True)
        self.pas(10_140)
        self.reseau.configurer(wifi=True)
        self.pas(11_000)
        self.pas(12_000)
        self.assertEqual(self.reseau.messages, [])
        self.assertEqual(self.b.etat, simulation.REPOS)

    def test_annulation_interrompt_requete_simulee_non_acceptee(self):
        self.reseau.latence_ms = 20_000
        self.pas(0, aide=True)
        self.pas(40)
        self.pas(100, aide=True)
        self.pas(10_100, aide=True)
        self.assertIsNone(self.reseau.en_cours)
        self.pas(10_140)
        self.pas(30_140)
        self.assertEqual(self.reseau.messages, [("ANNULATION", 1)])

    def test_ok_ancien_apres_annulation_ne_confirme_pas_nouvelle_demande(self):
        self.demander()
        self.reseau.configurer(wifi=False)
        self.pas(600, ok=True)
        self.pas(700, aide=True)
        self.pas(10_700, aide=True)
        self.pas(10_740)
        self.pas(10_800, aide=True)
        self.pas(10_840)
        self.reseau.configurer(wifi=True)
        self.pas(11_000)
        self.pas(11_500)  # Annulation precedente acceptee, nouvelle aide lancee.
        self.pas(12_000)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual((self.b.demande, self.b.envois), (2, 1))
        self.assertEqual(self.reseau.messages, [("AIDE", 1), ("ANNULATION", 1), ("AIDE", 2)])

    def test_reconnexion_apres_longue_coupure_sans_rafale(self):
        self.demander()
        self.reseau.configurer(wifi=False)
        self.pas(600)
        self.pas(60_000)
        self.reseau.configurer(wifi=True)
        self.pas(60_100)
        self.pas(60_600)
        self.pas(60_601)
        self.assertEqual(self.b.envois, 2)
        self.assertIsNone(self.reseau.en_cours)

    def test_ok_pendant_derniere_requete_garde_confirmation(self):
        self.demander()
        for t in (5_500, 6_000, 11_000, 11_500, 16_500, 17_000):
            self.pas(t)
        self.assertEqual(self.b.envois, 4)
        self.pas(22_000)
        self.pas(22_100, ok=True)
        self.pas(22_500)
        self.assertEqual(self.b.envois, 5)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)

    def test_interrupteurs_imposent_etat_sans_basculer_en_boucle(self):
        self.pas(0, wifi=False, pushbullet=False)
        self.pas(100, wifi=False, pushbullet=False)
        self.assertFalse(self.reseau.wifi)
        self.assertFalse(self.reseau.pushbullet)
        self.pas(200, wifi=True, pushbullet=True)
        self.pas(300, wifi=True, pushbullet=True)
        self.assertTrue(self.reseau.disponible())

    def test_interrupteur_off_au_demarrage_bloque_premier_envoi(self):
        self.pas(0, aide=True, wifi=False, pushbullet=True)
        self.pas(40, wifi=False, pushbullet=True)
        self.assertEqual(self.b.tentatives, 0)
        self.pas(100, wifi=True, pushbullet=True)
        self.pas(600, wifi=True, pushbullet=True)
        self.assertEqual(self.b.envois, 1)


if __name__ == "__main__":
    unittest.main()
