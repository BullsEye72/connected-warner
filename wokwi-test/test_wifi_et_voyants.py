import unittest

import main as simulation


class Station:
    def __init__(self, connecte=True, rssi=-55):
        self.connecte = connecte
        self.rssi = rssi
        self.lectures = 0
    def isconnected(self):
        self.lectures += 1
        if isinstance(self.connecte, Exception):
            raise self.connecte
        return self.connecte
    def status(self, parametre):
        if isinstance(self.rssi, Exception):
            raise self.rssi
        return self.rssi


class WiFiEtVoyantsTests(unittest.TestCase):
    def setUp(self):
        self.station = Station()
        self.qualite = simulation.SurveillanceWiFi(self.station, journal=lambda message: None,
                                                  ecart=lambda a, b: a - b)
        self.boitier = simulation.Boitier(lambda message: None, lambda a, b: a - b)
        self.boitier.qualite_wifi = self.qualite

    def test_wifi_non_configure_n_affiche_pas_le_repos_bleu(self):
        self.qualite.configure = False
        self.qualite.actualiser(0)
        self.assertFalse(self.qualite.connecte)
        self.assertEqual(self.qualite.etat(), "non configure")
        self.assertEqual(self.boitier.couleur(0), simulation.VIOLET)
        self.assertEqual(self.boitier.couleur(300), (0, 0, 0))
        self.assertEqual(self.station.lectures, 0)

    def test_connexion_et_signal_normal_donnent_le_bleu(self):
        self.qualite.actualiser(0)
        self.assertTrue(self.qualite.connecte)
        self.assertFalse(self.qualite.faible)
        self.assertEqual(self.qualite.rssi, -55)
        self.assertEqual(self.boitier.couleur(0), (0, 0, 255))

    def test_signal_faible_filtre_et_hysteresis(self):
        self.station.rssi = -80
        self.qualite.actualiser(0)
        self.assertFalse(self.qualite.faible)
        self.qualite.actualiser(1000)
        self.assertTrue(self.qualite.faible)
        for date in (0, 250, 4000):
            self.assertEqual(self.boitier.couleur(date), simulation.VIOLET)
        self.assertEqual(self.boitier.couleur(150), (0, 0, 255))
        self.assertEqual(self.boitier.couleur(500), (0, 0, 255))
        self.station.rssi = -74
        self.qualite.actualiser(2000)
        self.qualite.actualiser(3000)
        self.assertTrue(self.qualite.faible)
        self.station.rssi = -70
        self.qualite.actualiser(4000)
        self.assertTrue(self.qualite.faible)
        self.qualite.actualiser(5000)
        self.assertFalse(self.qualite.faible)

    def test_fluctuations_breves_ne_declenchent_pas_l_avertissement(self):
        for date, rssi in ((0, -80), (1000, -55), (2000, -80), (3000, -75)):
            self.station.rssi = rssi
            self.qualite.actualiser(date)
            self.assertFalse(self.qualite.faible)

    def test_lecture_wifi_limitee_a_une_par_seconde(self):
        for date in range(0, 1000, 5):
            self.qualite.actualiser(date)
        self.assertEqual(self.station.lectures, 1)
        self.qualite.actualiser(1000)
        self.assertEqual(self.station.lectures, 2)

    def test_perte_wifi_prime_sur_cyan_mais_pas_sur_annulation(self):
        self.qualite.actualiser(0)
        self.station.connecte = False
        self.qualite.actualiser(1000)
        self.boitier.reseau.en_cours = {"nature": "AIDE"}
        self.assertEqual(self.boitier.couleur(0), simulation.VIOLET)
        self.boitier.maintien_depuis = 500
        self.assertEqual(self.boitier.couleur(0), simulation.ORANGE)

    def test_signal_faible_ne_masque_pas_les_etats_d_aide(self):
        self.station.rssi = -90
        self.qualite.actualiser(0)
        self.qualite.actualiser(1000)
        self.boitier.envois = 1
        for etat, couleur in ((simulation.ATTENTE, simulation.ORANGE),
                              (simulation.CONFIRMEE, (0, 255, 0)),
                              (simulation.SANS_CONFIRMATION, (255, 0, 0))):
            self.boitier.etat = etat
            self.assertEqual(self.boitier.couleur(0), couleur)

    def test_lecture_de_fond_garde_le_bleu_fixe_meme_avec_signal_faible(self):
        self.station.rssi = -90
        self.qualite.actualiser(0)
        self.qualite.actualiser(1000)
        self.boitier.reseau.lecture_de_fond = True
        self.assertEqual(self.boitier.couleur(0), (0, 0, 255))

    def test_erreur_de_lecture_wifi_ne_vaut_pas_connexion(self):
        self.station.connecte = OSError("echec")
        self.qualite.actualiser(0)
        self.assertFalse(self.qualite.connecte)
        self.assertEqual(self.boitier.couleur(0), simulation.VIOLET)

    def test_rssi_absent_ne_vaut_pas_un_signal_faible(self):
        for date, valeur in ((0, OSError("echec")), (1000, 0), (2000, -200), (3000, None)):
            self.station.rssi = valeur
            self.qualite.actualiser(date)
            self.assertTrue(self.qualite.connecte)
            self.assertIsNone(self.qualite.rssi)
            self.assertFalse(self.qualite.faible)

    def test_demande_physique_hors_wifi_attend_reconnexion_simulee(self):
        self.station.connecte = False
        self.qualite.actualiser(0)
        self.boitier.actualiser(0, True, False, wifi_disponible=self.qualite.connecte)
        self.boitier.actualiser(40, False, False, wifi_disponible=self.qualite.connecte)
        self.assertEqual(self.boitier.etat, simulation.ATTENTE)
        self.assertEqual(self.boitier.envois, 0)
        self.assertEqual(self.boitier.reseau.messages, [])
        self.station.connecte = True
        self.qualite.actualiser(1000)
        self.boitier.actualiser(1000, False, False, wifi_disponible=self.qualite.connecte)
        self.assertEqual(self.boitier.envois, 1)
        self.assertEqual(self.boitier.reseau.messages, [("AIDE", 1)])


if __name__ == "__main__":
    unittest.main()
