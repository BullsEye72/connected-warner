import unittest
from unittest.mock import patch

import main as simulation


class MachineEtatsTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.b = simulation.Boitier(self.logs.append, lambda a, b: a - b)

    def aide(self, t=0):
        self.b.actualiser(t, True, False)
        self.b.actualiser(t + 40, False, False)

    def test_demande_immediate_persistante_et_sans_doublons(self):
        self.b.actualiser(0, True, False)
        self.assertEqual((self.b.demande, self.b.envois), (1, 1))
        self.b.actualiser(40, False, False)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.aide(100)
        self.assertEqual((self.b.demande, self.b.envois), (1, 1))

    def test_cinq_notifications_puis_attente_de_confirmation_tardive(self):
        self.aide()
        for t in (5_000, 10_000, 15_000, 20_000, 25_000):
            self.b.actualiser(t, False, False)
        self.assertEqual(self.b.envois, 5)
        self.assertEqual(self.b.etat, simulation.SANS_CONFIRMATION)
        self.b.actualiser(30_000, False, True)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)
        self.b.actualiser(100_000, False, False)
        self.assertEqual(self.b.envois, 5)

    def test_validation_arrete_les_relances_et_donne_le_vert(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(200, False, False)
        self.b.actualiser(10_000, False, False)
        self.assertEqual(self.b.envois, 1)
        self.assertEqual(self.b.couleur(10_000), (0, 255, 0))

    def test_validation_deja_maintenue_ne_confirme_pas_nouvelle_demande(self):
        self.b.actualiser(0, False, True)
        self.b.actualiser(100, True, True)
        self.assertEqual(self.b.etat, simulation.ATTENTE)

    def test_premier_appui_long_ne_declenche_pas_annulation(self):
        self.b.actualiser(0, True, False)
        self.b.actualiser(11_000, True, False)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertFalse(self.b.annulation_armee)

    def test_annulation_seulement_apres_dix_secondes_et_une_seule_fois(self):
        self.aide()
        self.b.actualiser(100, True, False)
        self.assertEqual(self.b.couleur(100), simulation.ORANGE)
        self.b.actualiser(10_099, True, False)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.b.actualiser(10_100, True, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))
        self.b.actualiser(15_100, True, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.demande, 1)
        self.assertEqual(self.b.envois, 1)
        self.assertEqual(sum("tout va bien" in log for log in self.logs), 1)
        self.assertEqual(self.b.couleur(15_100), (0, 0, 255))

    def test_relachement_avant_seuil_interrompt_annulation(self):
        self.aide()
        self.b.actualiser(100, True, False)
        self.b.actualiser(9_100, False, False)
        self.b.actualiser(10_100, False, False)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertIsNone(self.b.dernier_resultat)
        self.assertEqual(self.b.envois, 1)

    def test_annulation_possible_apres_confirmation(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(140, False, False)
        self.b.actualiser(200, True, False)
        self.b.actualiser(10_200, True, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))
        self.assertEqual(self.b.envois, 1)

    def test_annulation_prioritaire_sur_validation_et_relance(self):
        self.aide()
        self.b.actualiser(100, True, False)
        self.b.actualiser(10_100, True, True)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))
        self.assertEqual(self.b.envois, 1)

    def test_nouveau_cycle_apres_annulation(self):
        self.aide()
        self.b.actualiser(100, True, False)
        self.b.actualiser(10_100, True, False)
        self.b.actualiser(10_140, False, False)
        self.b.actualiser(10_200, True, False)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual((self.b.demande, self.b.envois), (2, 1))

    def test_retour_au_repos_par_bouton_simule_apres_confirmation(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(140, False, False)
        self.b.actualiser(200, False, True)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.couleur(200), (0, 0, 255))
        self.b.actualiser(240, False, False)
        self.aide(300)
        self.assertEqual(self.b.demande, 2)

    def test_relance_au_franchissement_du_compteur_de_temps(self):
        periode = 1 << 30
        ecart = lambda a, b: ((a - b + periode // 2) % periode) - periode // 2
        b = simulation.Boitier(self.logs.append, ecart)
        b.actualiser(periode - 100, True, False)
        b.actualiser(periode - 60, False, False)
        b.actualiser(4_900, False, False)
        self.assertEqual(b.envois, 2)

    def test_aucune_relance_pendant_le_geste_annulation(self):
        self.aide()
        self.b.actualiser(4_999, True, False)
        for t in (5_000, 10_000, 14_998):
            self.b.actualiser(t, True, False)
            self.assertEqual(self.b.etat, simulation.ATTENTE)
            self.assertEqual(self.b.envois, 1)
        self.b.actualiser(14_999, True, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.envois, 1)

    def test_relances_reprennent_sans_rafale_apres_geste_interrompu(self):
        self.aide()
        self.b.actualiser(4_000, True, False)
        self.b.actualiser(13_000, False, False)
        self.b.actualiser(17_999, False, False)
        self.assertEqual(self.b.envois, 1)
        self.b.actualiser(18_000, False, False)
        self.assertEqual(self.b.envois, 2)

    def test_retour_bleu_dix_minutes_apres_confirmation(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(600_099, False, False)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)
        self.b.actualiser(600_100, False, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.couleur(600_100), (0, 0, 255))
        self.assertEqual(self.b.dernier_resultat, (1, simulation.CONFIRMEE))
        self.aide(600_200)
        self.assertEqual((self.b.demande, self.b.envois), (2, 1))

    def test_pas_de_retour_repos_pour_demande_sans_reponse(self):
        self.aide()
        for t in (5_000, 10_000, 15_000, 20_000, 900_000):
            self.b.actualiser(t, False, False)
        self.assertEqual(self.b.etat, simulation.SANS_CONFIRMATION)
        self.b.actualiser(900_100, False, True)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)

    def test_delai_retour_repos_n_interrompt_pas_annulation(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(599_000, True, False)
        self.b.actualiser(600_100, True, False)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)
        self.b.actualiser(609_000, True, False)
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))
        self.assertEqual(self.b.etat, simulation.REPOS)

    def test_retour_repos_au_franchissement_du_compteur(self):
        periode = 1 << 30
        ecart = lambda a, b: ((a - b + periode // 2) % periode) - periode // 2
        b = simulation.Boitier(self.logs.append, ecart)
        b.actualiser(periode - 300, True, False)
        b.actualiser(periode - 200, False, True)
        b.actualiser(599_799, False, False)
        self.assertEqual(b.etat, simulation.CONFIRMEE)
        b.actualiser(599_800, False, False)
        self.assertEqual(b.etat, simulation.REPOS)

    def test_validation_tardive_apres_annulation_ignoree(self):
        self.aide()
        self.b.actualiser(100, True, False)
        self.b.actualiser(10_100, True, False)
        self.b.actualiser(10_200, False, True)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))

    def test_orange_clignotant_et_orange_fixe_pendant_maintien(self):
        self.aide()
        self.assertEqual(self.b.couleur(400), (255, 80, 0))
        self.assertEqual(self.b.couleur(500), (0, 0, 0))
        self.b.actualiser(600, True, False)
        self.assertEqual(self.b.couleur(600), (255, 80, 0))
        self.assertEqual(self.b.couleur(1_500), (255, 80, 0))

    def test_appui_bref_apres_confirmation_cree_nouvelle_demande(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(140, False, False)
        self.b.actualiser(200, True, False)
        self.assertEqual((self.b.demande, self.b.envois), (1, 1))
        self.b.actualiser(240, False, False)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual((self.b.demande, self.b.envois), (2, 1))
        self.assertIsNone(self.b.confirmee_depuis)
        self.b.actualiser(5_240, False, False)
        self.assertEqual(self.b.envois, 2)

    def test_appui_bref_apres_plafond_recommence_cinq_envois(self):
        self.aide()
        for t in (5_000, 10_000, 15_000, 20_000):
            self.b.actualiser(t, False, False)
        self.b.actualiser(21_000, True, False)
        self.b.actualiser(21_040, False, False)
        self.assertEqual((self.b.demande, self.b.envois), (2, 1))
        for t in (26_040, 31_040, 36_040, 41_040, 46_040):
            self.b.actualiser(t, False, False)
        self.assertEqual(self.b.envois, 5)
        self.assertEqual(self.b.etat, simulation.SANS_CONFIRMATION)

    def test_appui_long_apres_plafond_annule_sans_nouvelle_alerte(self):
        self.aide()
        for t in (5_000, 10_000, 15_000, 20_000):
            self.b.actualiser(t, False, False)
        self.b.actualiser(21_000, True, False)
        self.b.actualiser(31_000, True, False)
        self.b.actualiser(31_100, False, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual((self.b.demande, self.b.envois), (1, 5))
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))

    def test_relachement_au_seuil_annule_sans_relancer(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(140, False, False)
        self.b.actualiser(200, True, False)
        self.b.actualiser(10_200, False, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual((self.b.demande, self.b.envois), (1, 1))
        self.assertEqual(self.b.dernier_resultat, (1, simulation.ANNULEE))

    def test_ok_pendant_geste_commence_en_attente_ne_relance_pas(self):
        self.aide()
        self.b.actualiser(100, True, False)
        self.b.actualiser(200, True, True)
        self.b.actualiser(240, False, False)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)
        self.assertEqual(self.b.demande, 1)

    def test_ok_simultane_a_relance_ne_confirme_pas_nouveau_cycle(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(140, False, False)
        self.b.actualiser(200, True, False)
        self.b.actualiser(240, False, True)
        self.b.actualiser(300, False, True)
        self.assertEqual(self.b.etat, simulation.ATTENTE)
        self.assertEqual(self.b.demande, 2)
        self.b.actualiser(340, False, False)
        self.b.actualiser(400, False, True)
        self.assertEqual(self.b.etat, simulation.CONFIRMEE)

    def test_nouvelle_demande_relancee_peut_etre_annulee(self):
        self.aide()
        self.b.actualiser(100, False, True)
        self.b.actualiser(140, False, False)
        self.aide(200)
        self.b.actualiser(300, True, False)
        self.b.actualiser(10_300, True, False)
        self.assertEqual(self.b.etat, simulation.REPOS)
        self.assertEqual(self.b.dernier_resultat, (2, simulation.ANNULEE))
        self.assertEqual(self.b.envois, 1)

    def test_relance_breve_au_franchissement_du_compteur(self):
        periode = 1 << 30
        ecart = lambda a, b: ((a - b + periode // 2) % periode) - periode // 2
        b = simulation.Boitier(self.logs.append, ecart)
        b.actualiser(periode - 300, True, False)
        b.actualiser(periode - 200, False, True)
        b.actualiser(periode - 100, True, False)
        b.actualiser(20, False, False)
        self.assertEqual(b.etat, simulation.ATTENTE)
        self.assertEqual((b.demande, b.envois), (2, 1))

    def test_anti_rebond_ne_produit_pas_de_faux_appuis(self):
        class Pin:
            niveau = 1
            def value(self):
                return self.niveau

        pin = Pin()
        bouton = simulation.Bouton(pin, 0)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            pin.niveau = 0
            self.assertFalse(bouton.lire(5))
            pin.niveau = 1
            self.assertFalse(bouton.lire(10))
            pin.niveau = 0
            self.assertFalse(bouton.lire(15))
            self.assertFalse(bouton.lire(44))
            self.assertTrue(bouton.lire(45))
            pin.niveau = 1
            self.assertTrue(bouton.lire(50))
            self.assertFalse(bouton.lire(80))


class VoyantTests(unittest.TestCase):
    def test_cyan_fixe_pendant_envoi_puis_reprise_du_clignotement(self):
        reseau = simulation.ReseauSimule(lambda message: None, lambda a, b: a - b, latence_ms=100)
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b, reseau)
        b.actualiser(0, True, False)
        self.assertEqual(b.couleur(0), simulation.CYAN)
        self.assertEqual(b.couleur(90), simulation.CYAN)
        b.actualiser(100, False, False)
        self.assertFalse(reseau.communication_en_cours)
        self.assertEqual(b.couleur(200), simulation.ORANGE)
        self.assertEqual(b.couleur(500), (0, 0, 0))

    def test_cyan_ne_modifie_pas_etat_confirme(self):
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        b.actualiser(0, True, False)
        b.actualiser(40, False, True)
        self.assertEqual(b.etat, simulation.CONFIRMEE)
        b.reseau.en_cours = {"nature": "LECTURE"}
        self.assertEqual(b.couleur(100), simulation.CYAN)
        self.assertEqual(b.etat, simulation.CONFIRMEE)
        b.reseau.en_cours = None
        self.assertEqual(b.couleur(100), (0, 255, 0))

    def test_vert_puis_repos_commande_effectivement_le_pwm_bleu(self):
        class Sortie:
            def __init__(self):
                self.valeurs = []
            def duty_u16(self, valeur):
                self.valeurs.append(valeur)

        sorties = [Sortie(), Sortie(), Sortie()]
        voyant = simulation.VoyantRGB(sorties)
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        b.actualiser(0, True, False)
        b.actualiser(40, False, True)
        voyant.afficher_etat(b, 40)
        self.assertEqual([s.valeurs[-1] for s in sorties], [0, 65535, 0])
        b.actualiser(600_040, False, False)
        voyant.afficher_etat(b, 600_040)
        self.assertEqual([s.valeurs[-1] for s in sorties], [0, 0, 65535])

    def test_pwm_inchange_non_reprogramme_a_chaque_boucle(self):
        class Sortie:
            def __init__(self):
                self.appels = 0
            def duty_u16(self, valeur):
                self.appels += 1

        sorties = [Sortie(), Sortie(), Sortie()]
        voyant = simulation.VoyantRGB(sorties)
        for _ in range(100):
            voyant.afficher((0, 0, 255))
        self.assertEqual([s.appels for s in sorties], [1, 1, 1])


if __name__ == "__main__":
    unittest.main()
