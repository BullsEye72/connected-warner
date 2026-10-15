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

    def test_appuis_brefs_repetes_ne_retardent_pas_les_relances(self):
        self.aide()
        for t in (1_000, 3_000, 4_500):
            self.aide(t)
        self.assertEqual(self.b.envois, 1)
        self.b.actualiser(5_000, False, False)
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

    class PinIrq:
        IRQ_FALLING = 2
        niveau = 1
        def value(self):
            return self.niveau
        def irq(self, trigger, handler):
            self.handler = handler
        def front(self):
            self.handler(self)

    def test_appui_bref_complet_pendant_pause_est_rapporte(self):
        pin = self.PinIrq()
        bouton = simulation.Bouton(pin, 0, memoriser=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            self.assertFalse(bouton.lire(5))
            pin.front()  # Appui puis relachement pendant 700 ms de TLS.
            self.assertTrue(bouton.lire(705))
            self.assertTrue(bouton.lire(710))
            self.assertFalse(bouton.lire(735))

    def test_geste_initial_ignore_puis_nouvel_appui_declenche_aide(self):
        pin = self.PinIrq()
        pin.niveau = 0
        bouton = simulation.Bouton(pin, 0, memoriser=True, ignorer_appui_initial=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            for t in (40, 10_000, 300_000):
                pin.front()
                self.b.actualiser(t, bouton.lire(t), False)
                self.assertEqual(self.b.etat, simulation.REPOS)
                self.assertEqual(self.b.envois, 0)
            pin.niveau = 1
            self.assertFalse(bouton.lire(300_010))
            pin.niveau = 0  # Rebond : ne pas armer le bouton.
            self.assertFalse(bouton.lire(300_020))
            pin.niveau = 1
            self.assertFalse(bouton.lire(300_030))
            self.assertFalse(bouton.lire(300_060))
            pin.niveau = 0
            pin.front()
            self.assertFalse(bouton.lire(300_070))
            self.b.actualiser(300_100, bouton.lire(300_100), False)
            self.assertEqual(self.b.etat, simulation.ATTENTE)
            self.assertEqual(self.b.envois, 1)

    def test_bouton_relache_au_demarrage_accepte_le_premier_appui(self):
        pin = self.PinIrq()
        bouton = simulation.Bouton(pin, 0, ignorer_appui_initial=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            pin.niveau = 0
            self.assertFalse(bouton.lire(10))
            self.assertTrue(bouton.lire(40))

    def test_front_hors_pause_reste_soumis_a_l_anti_rebond(self):
        pin = self.PinIrq()
        bouton = simulation.Bouton(pin, 0, memoriser=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            pin.front()  # Parasite bref : la boucle tournait normalement.
            self.assertFalse(bouton.lire(5))
            self.assertFalse(bouton.lire(40))

    def test_rebonds_du_relachement_pendant_pause_ignores(self):
        pin = self.PinIrq()
        bouton = simulation.Bouton(pin, 0, memoriser=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            pin.niveau = 0
            bouton.lire(5)
            self.assertTrue(bouton.lire(40))
            pin.niveau = 1
            pin.front()  # Rebond du relachement pendant une pause.
            self.assertTrue(bouton.lire(700))
            self.assertFalse(bouton.lire(730))
            self.assertFalse(bouton.lire(800))


class SurveillanceTests(unittest.TestCase):
    class Wdt:
        repas = 0
        def feed(self):
            self.repas += 1

    def test_nourri_tant_que_la_tache_reseau_vit(self):
        wdt = self.Wdt()
        tache = type("Tache", (), {"fini": False, "done": lambda self: self.fini})()
        messages = []
        s = simulation.Surveillance(wdt, tache, messages.append)
        s.nourrir()
        s.nourrir()
        self.assertEqual(wdt.repas, 2)
        tache.fini = True
        s.nourrir()
        s.nourrir()
        self.assertEqual(wdt.repas, 2)
        self.assertEqual(len(messages), 1)

    def test_mode_simule_sans_tache_reseau(self):
        wdt = self.Wdt()
        simulation.Surveillance(wdt).nourrir()
        self.assertEqual(wdt.repas, 1)


class VoyantTests(unittest.TestCase):
    def test_respiration_bleue_dix_secondes_et_verte_quatre_secondes_sans_extinction(self):
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        voyant = simulation.VoyantRGB((), respiration=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            for t, niveau in ((0, 64), (2500, 38), (5000, 12), (7500, 38), (10_000, 64)):
                voyant.afficher_etat(b, t)
                self.assertEqual(voyant.derniere_couleur, (0, 0, niveau))
            b.etat = simulation.CONFIRMEE
            for t, niveau in ((10_000, 96), (11_000, 58), (12_000, 19), (13_000, 58), (14_000, 96)):
                voyant.afficher_etat(b, t)
                self.assertEqual(voyant.derniere_couleur, (0, niveau, 0))

    def test_respiration_ne_masque_pas_les_priorites_et_gele_pendant_lecture(self):
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        voyant = simulation.VoyantRGB((), respiration=True)
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            voyant.afficher_etat(b, 0)
            voyant.afficher_etat(b, 2500)
            avant = voyant.derniere_couleur
            b.reseau.lecture_de_fond = True
            voyant.afficher_etat(b, 7000)
            self.assertEqual(voyant.derniere_couleur, avant)
            b.reseau.lecture_de_fond = False
            voyant.afficher_etat(b, 7000)
            self.assertEqual(voyant.derniere_couleur, avant)
            b.reseau.wifi = False
            voyant.afficher_etat(b, 7200)
            self.assertEqual(voyant.derniere_couleur, simulation.VIOLET)
            b.reseau.wifi = True
            b.reseau.en_cours = {"nature": "AIDE"}
            voyant.afficher_etat(b, 7300)
            self.assertEqual(voyant.derniere_couleur, simulation.CYAN)
            b.maintien_depuis = 7300
            voyant.afficher_etat(b, 7400)
            self.assertEqual(voyant.derniere_couleur, simulation.ORANGE)

    def test_respiration_ne_modifie_pas_orange_rouge_ni_duree_confirmation(self):
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        voyant = simulation.VoyantRGB((), respiration=True)
        for etat, couleur in ((simulation.ATTENTE, simulation.ORANGE), (simulation.SANS_CONFIRMATION, (255, 0, 0))):
            b.etat, b.envois = etat, 1
            voyant.afficher_etat(b, 0)
            self.assertEqual(voyant.derniere_couleur, couleur)
        b.etat = simulation.CONFIRMEE
        b.confirmee_depuis = 0
        with patch.object(simulation, "ecart_ms", lambda a, b: a - b):
            b.actualiser(simulation.RETOUR_REPOS_MS, False, False)
            voyant.afficher_etat(b, simulation.RETOUR_REPOS_MS)
            self.assertEqual(b.etat, simulation.REPOS)
            self.assertEqual(voyant.derniere_couleur, (0, 0, 64))

    def test_respiration_faible_intensite_reste_visible_et_extinction_explicite_possible(self):
        from unittest.mock import MagicMock
        pixel = MagicMock()
        voyant = simulation.VoyantRGB((), pixel, luminosite_carte=1, respiration=True, intensite_bleu=1)
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        voyant.afficher_etat(b, 0)
        pixel.__setitem__.assert_called_with(0, (0, 0, 1))
        voyant.eteindre()
        pixel.__setitem__.assert_called_with(0, (0, 0, 0))
        for parametre, valeur in (("periode_bleu_ms", 0), ("periode_vert_ms", 999), ("intensite_bleu", 0), ("intensite_vert", 256)):
            with self.assertRaises(ValueError):
                simulation.VoyantRGB((), **{parametre: valeur})

    def test_pixel_et_pwm_suivent_le_meme_cycle_et_s_eteignent_ensemble(self):
        class Sortie:
            def __init__(self):
                self.valeur = None
                self.fermee = False
            def duty_u16(self, valeur):
                self.valeur = valeur
            def deinit(self):
                self.fermee = True

        class Pixel:
            def __init__(self):
                self.couleur = None
                self.ecritures = []
            def __setitem__(self, indice, couleur):
                self.couleur = couleur
            def write(self):
                self.ecritures.append(self.couleur)

        sorties = [Sortie(), Sortie(), Sortie()]
        pixel = Pixel()
        voyant = simulation.VoyantRGB(sorties, pixel, luminosite_carte=32)
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        for etat, date, attendue in (
            (simulation.REPOS, 0, (0, 0, 32)),
            (simulation.ATTENTE, 0, (32, 10, 0)),
            (simulation.ATTENTE, 500, (0, 0, 0)),
            (simulation.SANS_CONFIRMATION, 0, (32, 0, 0)),
            (simulation.CONFIRMEE, 0, (0, 32, 0)),
        ):
            b.etat = etat
            b.envois = 1
            voyant.afficher_etat(b, date)
            self.assertEqual(pixel.ecritures[-1], attendue)
            self.assertEqual([s.valeur for s in sorties], [v * 257 for v in b.couleur(date)])
        voyant.eteindre()
        self.assertEqual(pixel.ecritures[-1], (0, 0, 0))
        self.assertTrue(all(s.fermee for s in sorties))

    def test_pixel_seul_et_couleur_inchangee_sans_recriture(self):
        class Pixel:
            def __setitem__(self, indice, couleur):
                self.couleur = couleur
            def write(self):
                self.ecritures = getattr(self, "ecritures", 0) + 1

        pixel = Pixel()
        voyant = simulation.VoyantRGB((), pixel)
        for _ in range(100):
            voyant.afficher((0, 0, 255))
        self.assertEqual(pixel.couleur, (0, 0, 32))
        self.assertEqual(pixel.ecritures, 1)
        voyant.eteindre()
        self.assertEqual(pixel.couleur, (0, 0, 0))

    def test_luminosite_pixel_zero_ou_max_sans_modifier_couleur_etat(self):
        class Pixel:
            def __setitem__(self, indice, couleur):
                self.couleur = couleur
            def write(self):
                pass

        for luminosite, attendue in ((0, (0, 0, 0)), (255, simulation.ORANGE)):
            pixel = Pixel()
            voyant = simulation.VoyantRGB((), pixel, luminosite)
            voyant.afficher(simulation.ORANGE)
            self.assertEqual(pixel.couleur, attendue)
            self.assertEqual(voyant.derniere_couleur, simulation.ORANGE)
        for invalide in (-1, 256, 1.5, "32"):
            with self.assertRaises(ValueError):
                simulation.VoyantRGB((), luminosite_carte=invalide)

    def test_profil_sans_voyant_externe_n_ouvre_aucune_sortie_pwm(self):
        from types import SimpleNamespace
        from unittest.mock import Mock

        pin, pwm = Mock(), Mock()
        voyant = simulation.creer_voyant(SimpleNamespace(VOYANT_BOUTON_ACTIF=False), pin, pwm)
        pin.assert_not_called()
        pwm.assert_not_called()
        self.assertEqual(voyant.sorties, ())

    def test_lecture_de_fond_fige_la_couleur_d_etat_sans_cyan(self):
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        b.actualiser(0, True, False)
        b.actualiser(40, False, False)
        self.assertEqual(b.couleur(500), (0, 0, 0))  # Phase eteinte du clignotement.
        b.reseau.lecture_de_fond = True
        self.assertEqual(b.couleur(500), simulation.ORANGE)
        b.etat = simulation.SANS_CONFIRMATION
        self.assertEqual(b.couleur(150), (255, 0, 0))
        b.reseau.wifi = False
        self.assertEqual(b.couleur(300), simulation.VIOLET)
    def test_orange_du_geste_prime_sur_cyan(self):
        b = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        b.actualiser(0, True, False)
        b.actualiser(40, False, False)
        b.actualiser(100, True, False)
        b.reseau.en_cours = {"nature": "LECTURE"}
        self.assertEqual(b.couleur(400), simulation.ORANGE)
        b.maintien_depuis = None  # Geste relache : le cyan reprend.
        self.assertEqual(b.couleur(400), simulation.CYAN)

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
