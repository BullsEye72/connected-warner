"""Logique sonore sans acquisition ADC ni acces aux GPIO.

Un niveau est une amplitude deja calculee (0..65535), pas une lecture ADC
instantanee ni une mesure en dB. Les adaptateurs materiels viendront apres
validation du montage ; les rappels injectes permettent les essais sur PC.
"""
import time


def ecart_ms(fin, debut):
    return time.ticks_diff(fin, debut)


def entier(nom, valeur, minimum, maximum):
    if type(valeur) is not int or not minimum <= valeur <= maximum:
        raise ValueError("%s doit etre entre %d et %d." % (nom, minimum, maximum))
    return valeur


class DetectionSonore:
    def __init__(self, seuil_haut=12000, seuil_bas=6000, nombre=3,
                 fenetre_ms=15000, duree_min_ms=60, retour_bas_ms=80,
                 ecart_max_ms=250, ecart=ecart_ms):
        self.seuil_haut = entier("seuil_haut", seuil_haut, 1, 65535)
        self.seuil_bas = entier("seuil_bas", seuil_bas, 0, seuil_haut - 1)
        self.nombre = entier("nombre", nombre, 1, 20)
        self.fenetre_ms = entier("fenetre_ms", fenetre_ms, 1, 60000)
        self.duree_min_ms = entier("duree_min_ms", duree_min_ms, 1, fenetre_ms)
        self.retour_bas_ms = entier("retour_bas_ms", retour_bas_ms, 1, fenetre_ms)
        self.ecart_max_ms = entier("ecart_max_ms", ecart_max_ms, 1, 60000)
        self.ecart = ecart
        self.reinitialiser()

    def reinitialiser(self):
        self.evenements = []
        self.derniere_mesure = None
        self.debut_haut = None
        self.debut_bas = None
        # Une periode basse observee est requise au demarrage et apres silence.
        self.arme = False

    def actualiser(self, maintenant, niveau, autorise=True):
        if not autorise:
            self.reinitialiser()
            return False
        self.evenements = [t for t in self.evenements
                           if 0 <= self.ecart(maintenant, t) <= self.fenetre_ms]
        valide = (type(niveau) in (int, float) and 0 <= niveau <= 65535)
        interruption = (self.derniere_mesure is not None and
                        not 0 <= self.ecart(maintenant, self.derniere_mesure) <= self.ecart_max_ms)
        if not valide or interruption:
            self.debut_haut = self.debut_bas = None
            self.arme = False
        self.derniere_mesure = maintenant if valide else None
        if not valide:
            return False

        if niveau <= self.seuil_bas:
            self.debut_haut = None
            if self.debut_bas is None:
                self.debut_bas = maintenant
            if self.ecart(maintenant, self.debut_bas) >= self.retour_bas_ms:
                self.arme = True
            return False
        self.debut_bas = None
        if not self.arme or niveau < self.seuil_haut:
            self.debut_haut = None
            return False
        if self.debut_haut is None:
            self.debut_haut = maintenant
        if self.ecart(maintenant, self.debut_haut) < self.duree_min_ms:
            return False
        self.arme = False
        self.debut_haut = None
        self.evenements.append(maintenant)
        if len(self.evenements) >= self.nombre:
            self.evenements = []
            return True
        return False


# (frequence Hz, duree ms) ; 0 = pause. Motifs provisoires a essayer sur carte.
BIP_LOCAL = ((2000, 120),)
BIPS_CONFIRMATION = ((1800, 120), (0, 100), (2400, 200))


class SequenceBips:
    """Sortie injectee sortie(frequence) ; sortie(0) coupe le son.

    Aucun sleep, aucune file : une nouvelle sequence remplace l'ancienne.
    Une boucle retardee saute les notes expirees au lieu de les rejouer.
    """
    def __init__(self, sortie, pause_micro_ms=300, ecart=ecart_ms):
        self.sortie = sortie
        self.pause_micro_ms = entier("pause_micro_ms", pause_micro_ms, 0, 60000)
        self.ecart = ecart
        self.motif = ()
        self.debut = None
        self.dernier_arret = None
        self.frequence = None

    def emettre(self, frequence):
        if frequence != self.frequence:
            self.sortie(frequence)
            self.frequence = frequence

    def jouer(self, motif, maintenant):
        motif = tuple(motif)
        if not motif or len(motif) > 64:
            raise ValueError("Un motif doit contenir 1 a 64 notes/pauses.")
        for frequence, duree in motif:
            entier("frequence", frequence, 0, 20000)
            entier("duree", duree, 1, 60000)
        self.motif = motif
        self.debut = maintenant
        self.actualiser(maintenant)

    def actualiser(self, maintenant):
        if not self.motif:
            return
        ecoule = self.ecart(maintenant, self.debut)
        fin = 0
        for frequence, duree in self.motif:
            fin += duree
            if 0 <= ecoule < fin:
                self.emettre(frequence)
                return
        self.arreter(maintenant)

    def arreter(self, maintenant):
        # Le silence part de l'arret reel, y compris apres une pause TLS.
        if self.motif:
            self.dernier_arret = maintenant
        self.motif = ()
        self.emettre(0)

    def micro_ignore(self, maintenant):
        return bool(self.motif) or (self.dernier_arret is not None and
               self.ecart(maintenant, self.dernier_arret) < self.pause_micro_ms)


class AudioBoitier:
    def __init__(self, detection=None, bips=None, lire_niveau=None):
        self.detection = detection
        self.bips = bips
        self.lire_niveau = lire_niveau

    def actualiser(self, maintenant):
        if self.bips is not None:
            self.bips.actualiser(maintenant)

    def detecter(self, maintenant, niveau=None, autorise=True):
        if self.detection is None:
            return False
        autorise = autorise and not (self.bips is not None and self.bips.micro_ignore(maintenant))
        if autorise and niveau is None and self.lire_niveau is not None:
            niveau = self.lire_niveau()
        return self.detection.actualiser(maintenant, niveau, autorise)

    def signaler(self, evenement, maintenant):
        if evenement not in ("locale", "confirmation"):
            raise ValueError("Evenement sonore inconnu.")
        if self.detection is not None:
            self.detection.reinitialiser()
        if self.bips is not None:
            self.bips.jouer(BIP_LOCAL if evenement == "locale" else BIPS_CONFIRMATION, maintenant)

    def arreter(self, maintenant):
        if self.detection is not None:
            self.detection.reinitialiser()
        if self.bips is not None:
            self.bips.arreter(maintenant)


def creer_audio(configuration, lire_niveau=None, sortie_son=None, ecart=ecart_ms):
    """Desactive par defaut, sans meme ouvrir une broche.

    Les drapeaux actifs exigent explicitement un adaptateur injecte : on ne
    presente pas l'absence d'acquisition comme une detection fonctionnelle.
    """
    detection_active = getattr(configuration, "DETECTION_SONORE_ACTIVE", False)
    bips_actifs = getattr(configuration, "BIPS_ACTIFS", False)
    if not detection_active and not bips_actifs:
        return None
    if detection_active and lire_niveau is None:
        raise ValueError("DETECTION_SONORE_ACTIVE requiert un adaptateur de niveau sonore valide.")
    if bips_actifs and sortie_son is None:
        raise ValueError("BIPS_ACTIFS requiert un adaptateur de sortie sonore valide.")
    detection = None
    bips = None
    if detection_active:
        detection = DetectionSonore(
            seuil_haut=getattr(configuration, "SON_SEUIL_HAUT", 12000),
            seuil_bas=getattr(configuration, "SON_SEUIL_BAS", 6000),
            nombre=getattr(configuration, "SON_NOMBRE_EVENEMENTS", 3),
            fenetre_ms=getattr(configuration, "SON_FENETRE_MS", 15000),
            duree_min_ms=getattr(configuration, "SON_DUREE_MIN_MS", 60),
            retour_bas_ms=getattr(configuration, "SON_RETOUR_BAS_MS", 80), ecart=ecart)
    if bips_actifs:
        bips = SequenceBips(sortie_son, getattr(configuration, "SON_PAUSE_MICRO_MS", 300), ecart)
    return AudioBoitier(detection, bips, lire_niveau)
