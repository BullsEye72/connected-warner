import unittest
from types import SimpleNamespace

from audio import (DetectionSonore, SequenceBips, AudioBoitier, creer_audio,
                   BIP_LOCAL, BIPS_CONFIRMATION)
from main import Boitier, REPOS, ATTENTE, CONFIRMEE, SANS_CONFIRMATION


def ecart(a, b):
    return a - b


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.d = DetectionSonore(seuil_haut=100, seuil_bas=50, ecart=ecart)

    def bas(self, t):
        self.assertFalse(self.d.actualiser(t, 0))
        self.assertFalse(self.d.actualiser(t + 80, 0))

    def cri(self, t):
        self.assertFalse(self.d.actualiser(t, 150))
        return self.d.actualiser(t + 60, 150)

    def test_trois_cris_courts_declenchent_une_fois(self):
        for t in (0, 400, 800):
            self.bas(t)
            self.assertEqual(self.cri(t + 100), t == 800)
        for t in range(1000, 3000, 100):
            self.assertFalse(self.d.actualiser(t, 150))

    def test_bruit_continu_compte_une_seule_fois(self):
        self.bas(0)
        for t in range(100, 16000, 20):
            self.assertFalse(self.d.actualiser(t, 150))
        self.assertLessEqual(len(self.d.evenements), 1)

    def test_claquement_trop_bref_ne_compte_pas(self):
        for t in range(0, 3000, 300):
            self.bas(t)
            self.d.actualiser(t + 100, 150)
            self.d.actualiser(t + 120, 0)
        self.assertEqual(self.d.evenements, [])

    def test_retour_dans_hysteresis_ne_rearme_pas(self):
        self.bas(0)
        self.cri(100)
        for t in range(200, 1000, 100):
            self.assertFalse(self.d.actualiser(t, 75 if t % 200 else 150))
        self.assertEqual(len(self.d.evenements), 1)

    def test_retour_bas_trop_bref_ne_rearme_pas(self):
        self.bas(0)
        self.cri(100)
        self.d.actualiser(200, 0)
        self.d.actualiser(220, 150)
        self.d.actualiser(300, 150)
        self.assertEqual(len(self.d.evenements), 1)

    def test_evenements_hors_fenetre_expirent(self):
        self.bas(0)
        self.cri(100)
        self.bas(16000)
        self.cri(16100)
        self.bas(16400)
        self.assertFalse(self.cri(16500))
        self.assertEqual(len(self.d.evenements), 2)

    def test_pause_de_boucle_ne_transforme_pas_un_pic_en_cri(self):
        self.bas(0)
        self.d.actualiser(100, 150)
        self.assertFalse(self.d.actualiser(8000, 150))
        self.assertFalse(self.d.actualiser(8100, 150))
        self.assertEqual(self.d.evenements, [])

    def test_mesure_absente_ou_invalide_interrompt_la_candidature(self):
        for valeur in (None, -1, 65536, float('nan'), float('inf'), True, '150'):
            self.d.reinitialiser()
            self.bas(0)
            self.d.actualiser(100, 150)
            self.assertFalse(self.d.actualiser(120, valeur))
            self.assertFalse(self.d.actualiser(200, 150))
            self.assertEqual(self.d.evenements, [])

    def test_suspendre_efface_compteur_et_exige_un_nouveau_retour_bas(self):
        self.bas(0)
        self.cri(100)
        self.d.actualiser(200, 0, autorise=False)
        self.assertEqual(self.d.evenements, [])
        for t in (300, 400, 500):
            self.assertFalse(self.d.actualiser(t, 150))

    def test_temps_micro_python_avec_retour_compteur(self):
        modulo = 65536
        diff = lambda a, b: ((a - b + modulo // 2) % modulo) - modulo // 2
        self.d = DetectionSonore(seuil_haut=100, seuil_bas=50, nombre=2, ecart=diff)
        for t, v in ((65300, 0), (65380, 0), (65400, 150), (65460, 150),
                     (65500, 0), (44, 0), (64, 150)):
            self.assertFalse(self.d.actualiser(t, v))
        self.assertTrue(self.d.actualiser(124, 150))

    def test_parametres_incoherents_refuses(self):
        for args in ({'seuil_bas': 12000}, {'nombre': 0}, {'fenetre_ms': -1},
                     {'duree_min_ms': 0}, {'nombre': True}):
            with self.assertRaises(ValueError):
                DetectionSonore(**args)


class BipsTests(unittest.TestCase):
    def setUp(self):
        self.sorties = []
        self.bips = SequenceBips(self.sorties.append, ecart=ecart)

    def test_motif_frequences_pauses_et_silence_apres_arret(self):
        self.bips.jouer(BIPS_CONFIRMATION, 0)
        for t in (50, 119, 120, 200, 220, 419, 420):
            self.assertTrue(self.bips.micro_ignore(t))
            self.bips.actualiser(t)
        self.assertEqual(self.sorties, [1800, 0, 2400, 0])
        self.assertTrue(self.bips.micro_ignore(719))
        self.assertFalse(self.bips.micro_ignore(720))

    def test_retard_saute_notes_et_garde_delai_depuis_extinction_reelle(self):
        self.bips.jouer(BIPS_CONFIRMATION, 0)
        self.bips.actualiser(8000)
        self.assertEqual(self.sorties, [1800, 0])
        self.assertTrue(self.bips.micro_ignore(8299))
        self.assertFalse(self.bips.micro_ignore(8300))

    def test_confirmation_remplace_bip_local_sans_file(self):
        self.bips.jouer(BIP_LOCAL, 0)
        self.bips.jouer(BIPS_CONFIRMATION, 20)
        self.bips.actualiser(140)
        self.bips.actualiser(240)
        self.bips.actualiser(440)
        self.assertEqual(self.sorties, [2000, 1800, 0, 2400, 0])

    def test_arret_force_ne_repousse_pas_indefiniment_le_silence(self):
        self.bips.jouer(BIP_LOCAL, 0)
        self.bips.arreter(10)
        self.bips.arreter(200)
        self.assertFalse(self.bips.micro_ignore(310))
        self.assertEqual(self.sorties, [2000, 0])

    def test_frequences_pour_une_future_melodie(self):
        self.bips.jouer(((262, 100), (330, 100), (392, 100)), 0)
        for t in (100, 200, 300):
            self.bips.actualiser(t)
        self.assertEqual(self.sorties, [262, 330, 392, 0])

    def test_motif_invalide_ne_remplace_pas_la_sequence_en_cours(self):
        self.bips.jouer(BIP_LOCAL, 0)
        for motif in ((), ((-1, 10),), ((2000, 0),)):
            with self.assertRaises(ValueError):
                self.bips.jouer(motif, 20)
        self.assertEqual(self.bips.motif, BIP_LOCAL)


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.sorties = []
        self.audio = AudioBoitier(
            DetectionSonore(seuil_haut=100, seuil_bas=50, ecart=ecart),
            SequenceBips(self.sorties.append, ecart=ecart))
        self.b = Boitier(journal=lambda msg: None, ecart=ecart, audio=self.audio)

    def mesure(self, t, v):
        self.b.actualiser(t, False, False, niveau_sonore=v)

    def cris(self, debut=0):
        for t in (debut, debut + 400, debut + 800):
            self.mesure(t, 0)
            self.mesure(t + 80, 0)
            self.mesure(t + 100, 150)
            self.mesure(t + 160, 150)

    def test_cris_declenchent_cycle_existant_avec_bip_local(self):
        self.cris()
        self.assertEqual((self.b.etat, self.b.demande, self.b.envois), (ATTENTE, 1, 1))
        self.assertEqual(self.sorties, [2000])
        self.assertTrue(self.b.annulation_armee)
        self.cris(1200)
        self.assertEqual(self.b.demande, 1)

    def test_demande_sonore_peut_etre_annulee_par_le_premier_maintien(self):
        self.cris()
        self.b.actualiser(1100, True, False)
        self.b.actualiser(11100, True, False)
        self.assertEqual(self.b.etat, REPOS)
        self.assertEqual(self.b.dernier_resultat, (1, 'ANNULEE'))
        self.assertEqual(self.b.demande, 1)

    def test_bip_local_immediat_meme_sans_reseau_et_confirmation_distincte(self):
        self.b.actualiser(0, True, False, wifi_disponible=False)
        self.assertEqual(self.b.envois, 0)
        self.assertEqual(self.sorties, [2000])
        self.b.actualiser(40, False, False, wifi_disponible=True)
        self.assertEqual(self.b.envois, 1)
        self.assertNotIn(1800, self.sorties)
        self.b.actualiser(500, False, True)
        self.assertEqual(self.b.etat, CONFIRMEE)
        self.assertEqual(self.sorties[-1], 1800)
        self.b.actualiser(600, False, False)
        self.b.reseau.confirmations.append(1)
        self.b.actualiser(700, False, False)
        self.assertEqual(self.sorties.count(1800), 1)

    def test_sons_apres_plafond_ou_confirmation_ne_recreent_pas_cycle(self):
        for etat in (SANS_CONFIRMATION, CONFIRMEE):
            self.b.etat = etat
            self.b.confirmee_depuis = 0
            self.cris()
            self.assertEqual(self.b.demande, 0)

    def test_bips_ne_peuvent_pas_alimenter_le_compteur(self):
        self.audio.bips.jouer(BIPS_CONFIRMATION, 0)
        for t in range(0, 800, 20):
            self.mesure(t, 150 if (t // 100) % 2 else 0)
        self.assertEqual(self.b.demande, 0)
        self.assertEqual(self.audio.detection.evenements, [])
        self.cris(1000)
        self.assertEqual(self.b.demande, 1)

    def test_appui_simultane_aux_cris_ne_double_pas_demande(self):
        cris_partiels = ((0, 0), (80, 0), (100, 150), (160, 150),
                        (400, 0), (480, 0), (500, 150), (560, 150),
                        (800, 0), (880, 0), (900, 150))
        for t, v in cris_partiels:
            self.mesure(t, v)
        self.b.actualiser(960, True, False, niveau_sonore=150)
        self.assertEqual(self.b.demande, 1)
        self.assertEqual(self.sorties, [2000])

    def test_pas_de_lecture_micro_pendant_silence_ni_demandes(self):
        lectures = []
        self.audio.lire_niveau = lambda: lectures.append(True) or 0
        self.audio.bips.jouer(BIP_LOCAL, 0)
        self.mesure(0, None)
        self.mesure(120, None)
        self.mesure(419, None)
        self.assertEqual(lectures, [])
        self.mesure(420, None)
        self.assertEqual(len(lectures), 1)
        self.b.actualiser(500, True, False)
        self.mesure(1000, None)
        self.assertEqual(len(lectures), 1)

    def test_inactif_par_defaut_et_adaptateurs_obligatoires_si_actif(self):
        self.assertIsNone(creer_audio(None))
        self.assertIsNone(creer_audio(SimpleNamespace()))
        for profil in (SimpleNamespace(BIPS_ACTIFS=True),
                       SimpleNamespace(DETECTION_SONORE_ACTIVE=True)):
            with self.assertRaises(ValueError):
                creer_audio(profil)
        audio = creer_audio(SimpleNamespace(DETECTION_SONORE_ACTIVE=True, BIPS_ACTIFS=True),
                            lire_niveau=lambda: 0, sortie_son=self.sorties.append, ecart=ecart)
        self.assertIsInstance(audio, AudioBoitier)
        audio.signaler('locale', 0)
        audio.arreter(10)
        self.assertEqual(self.sorties, [2000, 0])


if __name__ == '__main__':
    unittest.main()
