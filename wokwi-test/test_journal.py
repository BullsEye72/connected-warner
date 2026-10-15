import json
import os
from pathlib import Path
import tempfile
import unittest
import importlib.util
from types import SimpleNamespace
from unittest.mock import patch

import journal
from pushbullet_reel import ReseauReel

spec = importlib.util.spec_from_file_location("lire_journal", Path(__file__).resolve().parent.parent / "carte/lire_journal.py")
lecture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lecture)


class RTC:
    def __init__(self, brut=b""):
        self.brut = brut
    def memory(self, donnees=None):
        if donnees is not None:
            self.brut = donnees
        return self.brut


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.chemin = str(Path(self.temp.name) / "diagnostic.jsonl")
        self.horloge = [0]
        self.patch = patch.object(journal, "ticks_ms", side_effect=lambda: self.horloge[0])
        self.patch.start()
        self.rtc = RTC()
        self.j = journal.Journal(self.rtc, self.chemin)
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.patch.stop)
        self.addCleanup(setattr, journal, "_actif", None)

    def entrees(self, chemin=None):
        return [json.loads(ligne) for ligne in Path(chemin or self.chemin).read_text().splitlines() if ligne.strip()]

    def test_rtc_garde_derniere_phase_sans_ecrire_en_flash(self):
        self.horloge[0] = 45_000
        self.j.contexte_maj(etat="ATTENTE", phase="resolution DNS")
        self.assertFalse(Path(self.chemin).exists())
        nouveau = journal.Journal(self.rtc, self.chemin)
        self.assertEqual(nouveau.precedent["phase"], "resolution DNS")
        self.assertEqual(nouveau.precedent["secondes"], 45)
        self.assertNotEqual(nouveau.session, self.j.session)

    def test_boot_wdt_conserve_contexte_precedent_et_essai(self):
        self.j.contexte_maj(phase="blocage volontaire", essai=True)
        machine = SimpleNamespace(RTC=lambda: self.rtc, reset_cause=lambda: 3, WDT_RESET=3)
        nouveau = journal.demarrer(machine, 60_000, self.chemin)
        entree = self.entrees()[0]
        self.assertEqual(entree["cause"], "WDT_RESET")
        self.assertTrue(entree["precedent"]["essai"])
        self.assertEqual(entree["precedent"]["phase"], "blocage volontaire")
        self.assertEqual(entree["watchdog_ms"], 60_000)
        self.assertEqual(entree["session"], nouveau.session)

    def test_erreurs_repetitives_bornees_mais_nouveau_statut_immediat(self):
        for ms in (0, 1_000, 59_000):
            self.horloge[0] = ms
            self.j.ecrire("http_erreur", classe="HTTP", statut=503)
        self.assertEqual(len(self.entrees()), 1)
        self.j.ecrire("http_erreur", classe="HTTP", statut=401)
        self.assertEqual(len(self.entrees()), 2)
        self.horloge[0] = 119_000
        self.j.ecrire("http_erreur", classe="HTTP", statut=401)
        self.assertEqual(len(self.entrees()), 3)

    def test_points_activite_espaces_et_utc_apres_synchronisation_seulement(self):
        for ms in range(0, journal.POINT_MS, 30_000):
            self.horloge[0] = ms
            self.j.point(etat="REPOS")
        self.assertFalse(Path(self.chemin).exists())
        self.horloge[0] = journal.POINT_MS
        self.j.point(etat="REPOS")
        self.assertIsNone(self.entrees()[0]["utc"])
        self.j.horloge_prete = True
        self.j.ecrire("horloge_reglee")
        self.assertTrue(self.entrees()[-1]["utc"].endswith("Z"))

    def test_rotation_deux_fichiers_bornes_y_compris_utf8(self):
        self.j.maximum = 1024
        for _ in range(40):
            self.j.contexte_maj(phase="é" * 64)
            self.j.ecrire("etat")
        for chemin in (self.chemin, self.chemin + ".1"):
            self.assertLessEqual(os.stat(chemin).st_size, 1024)
            self.assertTrue(self.entrees(chemin))
        self.assertEqual(len(list(Path(self.temp.name).iterdir())), 2)

    def test_ligne_tronquee_ne_fusionne_pas_avec_evenement_suivant(self):
        Path(self.chemin).write_bytes(b'{"evenement": "incomplet')
        self.j.ecrire("etat")
        lignes = Path(self.chemin).read_text().splitlines()
        self.assertEqual(json.loads(lignes[-1])["evenement"], "etat")

    def test_stockage_plein_ne_casse_pas_le_programme_ni_la_trace_rtc(self):
        with patch("builtins.open", side_effect=OSError(28, "plein")), patch("builtins.print") as afficher:
            self.j.ecrire("etat")
            self.j.ecrire("etat")
            self.assertEqual(afficher.call_count, 1)
        self.j.contexte_maj(phase="suite")
        self.assertIn(b"suite", self.rtc.brut)

    def test_donnees_privees_ignorees_et_requete_sans_parametres(self):
        journal._actif = self.j
        self.j.contexte_maj(token="SECRET", ssid="MAISON", phase="test")
        self.j.ecrire("exception", classe="ValueError", message="PRIVE", email="ALICE")
        r = object.__new__(ReseauReel)
        r.c = SimpleNamespace(TRACE_HTTPS=False)
        r.tracer_https("GET", "pushes?cursor=JETON", "lecture du statut HTTP")
        self.j.ecrire("etat")
        contenu = Path(self.chemin).read_text() + self.rtc.brut.decode()
        for secret in ("SECRET", "MAISON", "PRIVE", "ALICE", "JETON"):
            self.assertNotIn(secret, contenu)
        self.assertEqual(self.j.contexte["ressource"], "pushes")

    def test_ticks_qui_bouclent_et_donnees_rtc_invalides(self):
        self.j.dernier_tick = 9000
        self.horloge[0] = 1000
        with patch.object(journal, "ecart_ms", side_effect=lambda a, b: (a - b + 5000) % 10000 - 5000):
            self.assertEqual(self.j.temps(), 2)
        for brut in (b"autre programme", journal.PREFIXE_RTC + b"{", journal.PREFIXE_RTC + b"[]"):
            self.assertIsNone(journal.Journal(RTC(brut), self.chemin).precedent)

    def test_export_ignore_ligne_tronquee_et_distingue_essais_du_debug(self):
        entrees = [
            {"evenement": "demarrage", "cause": "WDT_RESET", "precedent": {"essai": True}},
            {"evenement": "demarrage", "cause": "WDT_RESET", "precedent": {"phase": "arret_manuel"}},
            {"evenement": "demarrage", "cause": "WDT_RESET", "precedent": {"phase": "resolution DNS"}},
            {"evenement": "demarrage", "cause": "PWRON_RESET"},
        ]
        Path(self.chemin).write_text("\n".join(json.dumps(e) for e in entrees) + '\n{"tronque')
        donnees, invalides = lecture.lire_entrees(self.temp.name)
        self.assertEqual(invalides, 1)
        resume = lecture.bilan(donnees)
        self.assertEqual((resume["demarrages"], resume["watchdogs"], resume["essais"], resume["debug"]), (4, 1, 1, 1))
        self.assertEqual(resume["dernier_incident"]["precedent"]["phase"], "resolution DNS")

    def test_export_tente_reset_meme_si_lecture_en_echec(self):
        def resultat(port, *args):
            return SimpleNamespace(returncode=0 if args[0] == "reset" else 1, stdout="", stderr="erreur")
        with patch.object(lecture, "commande", side_effect=resultat) as commande:
            with self.assertRaises(RuntimeError):
                lecture.recuperer("COM4", Path(self.temp.name))
        self.assertEqual(commande.call_args.args, ("COM4", "reset"))

    def test_absence_premiere_generation_normale_et_reset_apres_copie(self):
        reponses = [SimpleNamespace(returncode=1, stdout="", stderr="mpremote: cp: diagnostic.jsonl.1: No such file or directory."),
                    SimpleNamespace(returncode=0, stdout="", stderr=""),
                    SimpleNamespace(returncode=0, stdout="", stderr="")]
        with patch.object(lecture, "commande", side_effect=reponses) as commande:
            lecture.recuperer("COM4", Path(self.temp.name))
        self.assertEqual(commande.call_count, 3)
        self.assertEqual(commande.call_args.args, ("COM4", "reset"))


if __name__ == "__main__":
    unittest.main()
