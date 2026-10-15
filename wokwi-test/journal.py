"""Diagnostic local borne : evenements en flash, derniere activite en RTC.

Ne recoit que des champs techniques, jamais les traces console ni les secrets.
Inactif tant que demarrer() n'est pas appele (tests PC et imports de modules).
"""
import json
import os
import time

PREFIXE_RTC = b"AIDE-J1:"
MAX_OCTETS = 32_768  # Deux generations, soit au plus 64 Kio.
POINT_MS = 1_800_000  # Un point d'activite en flash toutes les 30 minutes.
_actif = None


def ticks_ms():
    return time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.monotonic() * 1000)


def ecart_ms(a, b):
    return time.ticks_diff(a, b) if hasattr(time, "ticks_diff") else a - b


class Journal:
    def __init__(self, rtc=None, chemin="diagnostic.jsonl", maximum=MAX_OCTETS):
        self.rtc, self.chemin, self.maximum = rtc, chemin, maximum
        self.contexte = {}
        self.precedent = None
        self.debut = self.dernier_tick = ticks_ms()
        self.duree_ms = 0
        self.dernier_point = 0
        self.horloge_prete = False
        self.derniers = {}
        self.stockage_signale = False
        try:
            self.session = os.urandom(4).hex()
        except AttributeError:
            import binascii
            self.session = binascii.hexlify(os.urandom(4)).decode()
        if rtc is not None:
            try:
                brut = rtc.memory()
                if brut.startswith(PREFIXE_RTC):
                    ancien = json.loads(brut[len(PREFIXE_RTC):])
                    if isinstance(ancien, dict):
                        self.precedent = ancien
            except (OSError, ValueError, TypeError):
                pass

    def temps(self):
        maintenant = ticks_ms()
        self.duree_ms += max(0, ecart_ms(maintenant, self.dernier_tick))
        self.dernier_tick = maintenant
        return self.duree_ms // 1000

    def contexte_maj(self, **champs):
        # Liste fermee de champs : aucune adresse, exception libre ou charge HTTP.
        permis = ("etat", "wifi", "phase", "methode", "ressource", "essai")
        self.contexte.update({k: (v[:64] if isinstance(v, str) else v)
                             for k, v in champs.items() if k in permis})
        self.contexte.update(session=self.session, secondes=self.temps())
        if self.rtc is not None:
            try:
                self.rtc.memory(PREFIXE_RTC + json.dumps(self.contexte).encode())
            except (OSError, ValueError):
                pass

    def ecrire(self, evenement, **champs):
        secondes = self.temps()
        # Les erreurs repetees sont bornees a une par categorie et par minute.
        if evenement in ("http_erreur", "pause_boucle"):
            precedent = self.derniers.get(evenement)
            signature = (champs.get("classe"), champs.get("statut"))
            if precedent and precedent[1] == signature and secondes - precedent[0] < 60:
                return
            self.derniers[evenement] = (secondes, signature)
        permis = ("cause", "code_cause", "classe", "statut", "duree_ms", "watchdog_ms")
        donnees = {k: v for k, v in champs.items() if k in permis}
        donnees.update(evenement=evenement, session=self.session, secondes=secondes,
                       contexte=dict(self.contexte), utc=None)
        if self.horloge_prete:
            donnees["utc"] = "%04d-%02d-%02dT%02d:%02d:%02dZ" % time.gmtime()[:6]
        if evenement == "demarrage":
            donnees["precedent"] = self.precedent
        try:
            # Un saut initial isole aussi une derniere ligne tronquee par coupure.
            ligne = ("\n" + json.dumps(donnees) + "\n").encode()
            if len(ligne) > self.maximum:
                raise ValueError("Entree de diagnostic trop grande")
            try:
                taille = os.stat(self.chemin)[6]
            except OSError as erreur:
                if erreur.args[0] != 2:
                    raise
                taille = 0
            if taille + len(ligne) > self.maximum:
                try:
                    os.remove(self.chemin + ".1")
                except OSError as erreur:
                    if erreur.args[0] != 2:
                        raise
                os.rename(self.chemin, self.chemin + ".1")
            with open(self.chemin, "ab") as fichier:
                fichier.write(ligne)
                fichier.flush()
        except (OSError, ValueError):
            if not self.stockage_signale:
                print("[JOURNAL] Ecriture indisponible ; fonctionnement du bouton conserve.")
                self.stockage_signale = True

    def point(self, **champs):
        self.contexte_maj(**champs)
        if self.duree_ms - self.dernier_point >= POINT_MS:
            self.dernier_point = self.duree_ms
            self.ecrire("activite")


def demarrer(machine, watchdog_ms=0, chemin="diagnostic.jsonl", essai=False):
    global _actif
    _actif = Journal(machine.RTC(), chemin)
    cause = machine.reset_cause()
    nom = "autre"
    for constante in ("PWRON_RESET", "HARD_RESET", "WDT_RESET", "DEEPSLEEP_RESET", "SOFT_RESET"):
        if cause == getattr(machine, constante, None):
            nom = constante
            break
    _actif.contexte_maj(phase="demarrage", essai=essai)
    _actif.ecrire("demarrage", cause=nom, code_cause=cause, watchdog_ms=watchdog_ms)
    return _actif


def contexte(**champs):
    if _actif is not None:
        _actif.contexte_maj(**champs)


def evenement(nom, **champs):
    if _actif is not None:
        _actif.ecrire(nom, **champs)


def horloge_reglee():
    if _actif is not None:
        _actif.horloge_prete = True
        _actif.ecrire("horloge_reglee")
