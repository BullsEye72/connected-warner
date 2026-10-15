import time
import journal as diagnostic

# Mode simule par defaut ; configuration.py permet les essais Pushbullet reels.
GPIO_ROUGE = 3
GPIO_VERT = 8
GPIO_BLEU = 18
GPIO_AIDE = 12
GPIO_VALIDATION = 40
GPIO_WIFI_TEST = 13
GPIO_PUSHBULLET_TEST = 14
ANTI_REBOND_MS = 30
PAUSE_BOUCLE_MS = 50  # Ecart entre lectures au-dela duquel un appui bref a pu echapper.
ANNULATION_MS = 10_000
INTERVALLE_RELANCE_MS = 5_000  # Essais rapides ; cible : 120_000.
MAX_ENVOIS = 5  # Premier envoi compris.
RETOUR_REPOS_MS = 600_000  # Dix minutes apres confirmation.
ORANGE = (255, 80, 0)  # Intensites 0..255 ; ajustables selon la LED.
VIOLET = (180, 0, 255)
CYAN = (0, 255, 255)  # Fixe pendant les communications ; reprend l'etat ensuite.
LATENCE_RESEAU_MS = 750  # Une requete simulee ne bloque pas les boutons.
INTERVALLE_REESSAI_MS = 2_000  # Apres echec, distinct des relances acceptees.
# Redemarrage si la boucle des boutons ne tourne plus. Large : DNS et TLS
# peuvent bloquer plusieurs secondes, et un redemarrage perd la demande en
# RAM tant qu'il n'y a pas de persistance. 0 desactive (developpement).
WATCHDOG_MS = 60_000

REPOS = "REPOS"
ATTENTE = "ATTENTE"
SANS_CONFIRMATION = "SANS_CONFIRMATION"
CONFIRMEE = "CONFIRMEE"
ANNULEE = "ANNULEE"


def ecart_ms(fin, debut):
    return time.ticks_diff(fin, debut)


class SurveillanceWiFi:
    """Etat Wi-Fi local et signal ; aucune requete Internet depuis les boutons."""

    def __init__(self, station, configure=True, seuil_dbm=-75, journal=print, ecart=ecart_ms):
        if not isinstance(seuil_dbm, int) or not -120 <= seuil_dbm <= -30:
            raise ValueError("SEUIL_WIFI_FAIBLE_DBM doit etre entre -120 et -30.")
        self.station = station
        self.configure = configure
        self.seuil_dbm = seuil_dbm
        self.journal = journal
        self.ecart = ecart
        self.connecte = False
        self.faible = False
        self.rssi = None
        self.derniere_lecture = None
        self.dernier_etat = None
        self.mesures_faibles = 0
        self.mesures_bonnes = 0

    def etat(self):
        if not self.configure:
            return "non configure"
        if not self.connecte:
            return "connexion absente ou en cours"
        return "signal faible" if self.faible else "connecte"

    def actualiser(self, maintenant):
        if self.derniere_lecture is not None and self.ecart(maintenant, self.derniere_lecture) < 1000:
            return
        self.derniere_lecture = maintenant
        try:
            self.connecte = bool(self.configure and self.station.isconnected())
        except OSError:
            self.connecte = False
        self.rssi = None
        if not self.connecte:
            self.faible = False
            self.mesures_faibles = self.mesures_bonnes = 0
        else:
            try:
                valeur = self.station.status("rssi")
                if isinstance(valeur, int) and -127 <= valeur < 0:
                    self.rssi = valeur
            except (OSError, ValueError):
                pass
            if self.rssi is None:
                # Une mesure absente ne vaut ni amelioration ni degradation.
                self.mesures_faibles = self.mesures_bonnes = 0
            elif not self.faible:
                self.mesures_faibles = self.mesures_faibles + 1 if self.rssi < self.seuil_dbm else 0
                if self.mesures_faibles >= 2:
                    self.faible = True
                    self.mesures_faibles = 0
            else:
                self.mesures_bonnes = self.mesures_bonnes + 1 if self.rssi >= self.seuil_dbm + 5 else 0
                if self.mesures_bonnes >= 2:
                    self.faible = False
                    self.mesures_bonnes = 0
        etat = self.etat()
        if etat != self.dernier_etat:
            self.dernier_etat = etat
            diagnostic.contexte(wifi=etat)
            diagnostic.evenement("wifi")
            print_rssi = " ; RSSI=%d dBm" % self.rssi if self.rssi is not None else ""
            self.journal("[WIFI] %s%s" % (etat, print_rssi))

    def couleur_repos(self, maintenant):
        phase = maintenant % 4000
        if self.faible and (phase < 120 or 240 <= phase < 360):
            return VIOLET
        return (0, 0, 255)


class ReseauSimule:
    """Faux transport : aucune connexion, aucun secret, aucune API reelle."""

    def __init__(self, journal=print, ecart=ecart_ms, latence_ms=0):
        self.journal = journal
        self.ecart = ecart
        self.latence_ms = latence_ms
        self.wifi = True
        self.pushbullet = True
        self.en_cours = None
        self.messages = []
        self.confirmations = []

    @property
    def communication_en_cours(self):
        return self.en_cours is not None

    def disponible(self):
        return self.wifi and self.pushbullet

    def obstacle(self):
        return "Wi-Fi coupe" if not self.wifi else "Pushbullet indisponible"

    def configurer(self, wifi=None, pushbullet=None):
        if wifi is not None and wifi != self.wifi:
            self.wifi = wifi
            self.journal("[FAUX RESEAU] Wi-Fi : " + ("OK" if wifi else "COUPE"))
        if pushbullet is not None and pushbullet != self.pushbullet:
            self.pushbullet = pushbullet
            self.journal("[FAUX RESEAU] Pushbullet : " + ("OK" if pushbullet else "INDISPONIBLE"))
        if not self.disponible() and self.en_cours is not None:
            # Une coupure pendant la requete reste un echec, meme si la
            # connexion revient avant le prochain passage de la boucle.
            self.en_cours["erreur"] = self.obstacle()

    def commencer(self, nature, demande, maintenant):
        if not self.disponible() or self.en_cours is not None:
            return False
        self.en_cours = {"nature": nature, "demande": demande,
                         "debut": maintenant, "erreur": None}
        self.journal("[FAUX RESEAU] Envoi %s pour la demande %d..." % (nature, demande))
        return True

    def resultat(self, maintenant):
        if self.en_cours is None:
            return None
        requete = self.en_cours
        if not requete["erreur"] and self.ecart(maintenant, requete["debut"]) < self.latence_ms:
            return None
        self.en_cours = None
        requete["accepte"] = requete["erreur"] is None
        if requete["accepte"]:
            self.messages.append((requete["nature"], requete["demande"]))
        return requete

    def interrompre_aide(self):
        if self.en_cours is not None and self.en_cours["nature"] == "AIDE":
            self.journal("[FAUX RESEAU] Requete AIDE interrompue avant acceptation simulee.")
            self.en_cours = None

    def noter_interaction(self):
        pass  # Aucune lecture de fond a differer dans le faux reseau.

    def simuler_ok(self, demande):
        if not self.pushbullet:
            self.journal("[FAUX RESEAU] OK non depose : Pushbullet indisponible.")
        elif ("AIDE", demande) not in self.messages:
            self.journal("[FAUX RESEAU] OK ignore : aucune alerte acceptee pour cette demande.")
        else:
            self.confirmations.append(demande)
            self.journal("[FAUX RESEAU] Proche : OK pour la demande %d, en attente de lecture." % demande)

    def lire_ok(self):
        if self.disponible() and self.confirmations:
            return self.confirmations.pop(0)
        return None


class Boitier:
    def __init__(self, journal=print, ecart=ecart_ms, reseau=None, audio=None):
        self.journal = journal
        self.ecart = ecart
        self.audio = audio
        self.qualite_wifi = None
        # Latence nulle par defaut pour les tests de logique existants.
        # executer() choisit une latence visible de 750 ms dans Wokwi.
        self.reseau = reseau if reseau is not None else ReseauSimule(journal, ecart)
        if getattr(self.reseau, "reel", False):
            self.journal = lambda message: journal(message.replace(
                "[SIMULATION]", "[TEST REEL]").replace("[FAUX RESEAU]", "[RESEAU REEL]"))
        self.reseau_avant = self.reseau.disponible()
        self.annulations_a_transmettre = []
        self.dernier_essai = None
        self.tentatives = 0
        self.etat = REPOS
        self.demande = 0
        self.envois = 0
        self.dernier_envoi = None
        self.aide_avant = False
        self.validation_avant = False
        self.annulation_armee = False
        self.maintien_depuis = None
        self.relance_au_relachement = False
        self.confirmee_depuis = None
        self.dernier_resultat = None
        self.journal("[SIMULATION] REPOS : bleu. AIDE pour commencer.")

    def changer_etat(self, etat):
        self.etat = etat
        diagnostic.contexte(etat=etat)
        diagnostic.evenement("etat")
        self.journal("Etat : " + etat)

    def envoyer(self, maintenant):
        if self.annulations_a_transmettre:
            return
        if self.reseau.commencer("AIDE", self.demande, maintenant):
            self.tentatives += 1
            self.dernier_essai = maintenant
            self.traiter_envoi(maintenant)

    def traiter_envoi(self, maintenant):
        resultat = self.reseau.resultat(maintenant)
        if resultat is None:
            return
        if not resultat["accepte"]:
            self.journal("[FAUX RESEAU] Echec %s : %s. Aucun envoi ajoute au compteur." % (
                resultat["nature"], resultat["erreur"]))
            self.verifier_plafond()
            return
        if resultat["nature"] == "ANNULATION":
            self.annulations_a_transmettre.remove(resultat["demande"])
            self.journal("[FAUX RESEAU] Annulation demande %d terminee%s." % (
                resultat["demande"], " avec contact(s) refuse(s), voir diagnostic" if resultat.get("partiel") else ""))
            self.dernier_essai = None
            return
        if resultat["demande"] != self.demande or self.etat not in (ATTENTE, CONFIRMEE):
            return
        self.envois = resultat.get("envois", self.envois + 1)
        self.dernier_envoi = maintenant
        self.journal(("[SIMULATION] Demande %d : maximum %d/%d par contact" if "contacts" in resultat else
                      "[SIMULATION] Demande %d : notification %d/%d") % (self.demande, self.envois, MAX_ENVOIS))
        self.verifier_plafond()

    def verifier_plafond(self):
        verifier = getattr(self.reseau, "plafond_atteint", None)
        plafond = verifier(self.demande) if verifier is not None else self.envois >= MAX_ENVOIS
        if plafond and self.etat == ATTENTE:
            self.changer_etat(SANS_CONFIRMATION)
            self.journal("Plafond atteint. Toujours sans confirmation.")

    def nouvelle_demande(self, maintenant):
        if self.etat in (CONFIRMEE, SANS_CONFIRMATION):
            self.journal("[SIMULATION] Nouveau cycle d'aide apres la demande %d." % self.demande)
        self.demande += 1
        self.envois = 0
        self.tentatives = 0
        self.dernier_envoi = None
        self.dernier_essai = None
        self.annulation_armee = False
        self.maintien_depuis = None
        self.relance_au_relachement = False
        self.confirmee_depuis = None
        self.changer_etat(ATTENTE)
        if self.audio is not None:
            self.audio.signaler("locale", maintenant)
        self.envoyer(maintenant)

    def retour_repos(self):
        self.maintien_depuis = None
        self.relance_au_relachement = False
        self.annulation_armee = False
        self.confirmee_depuis = None
        self.changer_etat(REPOS)

    def annuler(self):
        self.reseau.interrompre_aide()
        if self.tentatives:
            self.annulations_a_transmettre.append(self.demande)
            self.dernier_essai = None
            self.journal("[FAUX RESEAU] Annulation a transmettre pour la demande %d." % self.demande)
        self.changer_etat(ANNULEE)
        self.dernier_resultat = (self.demande, ANNULEE)
        self.journal("[SIMULATION] Demande %d : Tout compte fait, tout va bien." % self.demande)
        self.retour_repos()

    def actualiser(self, maintenant, aide, validation, wifi_disponible=None, pushbullet_disponible=None,
                   niveau_sonore=None):
        if self.audio is not None:
            self.audio.actualiser(maintenant)
        appui_aide = aide and not self.aide_avant
        relache_aide = not aide and self.aide_avant
        appui_validation = validation and not self.validation_avant
        self.aide_avant = aide
        self.validation_avant = validation
        # Les interrupteurs imposent un etat, au lieu de basculer a l'appui.
        # None laisse le faux reseau inchange pour les tests sans entree physique.
        self.reseau.configurer(wifi=wifi_disponible, pushbullet=pushbullet_disponible)
        if aide:
            # Le transport reel differe ses lectures de fond pendant un geste.
            self.reseau.noter_interaction()

        disponible = self.reseau.disponible()
        if disponible != self.reseau_avant:
            self.reseau_avant = disponible
            if disponible:
                self.dernier_essai = None
                self.journal("[FAUX RESEAU] Retabli : reprise des transmissions en attente.")
            else:
                self.journal("[FAUX RESEAU] Transmission suspendue : " + self.reseau.obstacle())

        if appui_aide:
            if self.etat in (REPOS, ANNULEE):
                self.nouvelle_demande(maintenant)
            elif self.annulation_armee:
                self.maintien_depuis = maintenant
                # Fixer l'intention a l'appui : un OK recu pendant un geste
                # commence en ATTENTE ne doit pas provoquer une relance.
                self.relance_au_relachement = self.etat in (CONFIRMEE, SANS_CONFIRMATION)
                if self.relance_au_relachement:
                    self.journal("Relacher avant 10 secondes : nouveau cycle ; maintenir : annulation.")
                else:
                    self.journal("Maintien : annulation apres 10 secondes.")

        if self.maintien_depuis is not None:
            if self.ecart(maintenant, self.maintien_depuis) >= ANNULATION_MS:
                self.annuler()
                return  # Prioritaire, meme si le seuil est constate au relachement.

        if relache_aide:
            if self.relance_au_relachement:
                self.nouvelle_demande(maintenant)
                # Ce nouvel envoi a lieu au relachement : le prochain appui
                # peut deja etre un geste d'annulation.
                self.annulation_armee = True
                return  # Un OK simultane ne confirme pas le nouveau cycle.
            if (self.maintien_depuis is not None and self.etat == ATTENTE and self.envois and
                    self.ecart(maintenant, self.dernier_envoi) >= INTERVALLE_RELANCE_MS):
                # Relance suspendue par le geste : reprendre apres un intervalle
                # complet, sans rattrapage. Un appui bref qui n'a rien suspendu
                # ne decale pas le calendrier : des appuis repetes ne doivent
                # jamais empecher les relances.
                self.dernier_envoi = maintenant
            self.maintien_depuis = None
            self.relance_au_relachement = False
            if self.etat in (ATTENTE, SANS_CONFIRMATION, CONFIRMEE):
                self.annulation_armee = True

        if appui_validation:
            if self.etat in (ATTENTE, SANS_CONFIRMATION):
                self.reseau.simuler_ok(self.demande)
            elif self.etat in (CONFIRMEE, ANNULEE):
                self.retour_repos()
                self.journal("[SIMULATION] Retour au repos pour un nouvel essai.")
            else:
                self.journal("Validation ignoree : aucune demande en attente.")

        if self.audio is not None and self.audio.detecter(
                maintenant, niveau_sonore,
                autorise=self.etat == REPOS and not aide and not self.annulations_a_transmettre):
            self.journal("[SON] Sons forts repetes : demande d'aide locale.")
            self.nouvelle_demande(maintenant)
            # Pas d'appui initial a relacher : le prochain maintien peut annuler.
            self.annulation_armee = True

        self.traiter_envoi(maintenant)
        while True:
            demande_ok = self.reseau.lire_ok()
            if demande_ok is None:
                break
            if demande_ok == self.demande and self.etat in (ATTENTE, SANS_CONFIRMATION):
                self.changer_etat(CONFIRMEE)
                self.confirmee_depuis = maintenant
                self.dernier_resultat = (self.demande, CONFIRMEE)
                if self.audio is not None:
                    self.audio.signaler("confirmation", maintenant)
                self.journal("[SIMULATION] OK recu : prise en charge confirmee.")
            else:
                self.journal("[FAUX RESEAU] OK ancien ou deja traite ignore : demande %d." % demande_ok)

        if self.etat == CONFIRMEE and not aide:
            if self.ecart(maintenant, self.confirmee_depuis) >= RETOUR_REPOS_MS:
                self.retour_repos()
                self.journal("[SIMULATION] Confirmation depuis 10 minutes : retour au bleu.")

        reessai_permis = self.dernier_essai is None or self.ecart(maintenant, self.dernier_essai) >= INTERVALLE_REESSAI_MS
        if disponible and self.reseau.en_cours is None and reessai_permis:
            if self.annulations_a_transmettre:
                if self.reseau.commencer("ANNULATION", self.annulations_a_transmettre[0], maintenant):
                    self.dernier_essai = maintenant
                    self.traiter_envoi(maintenant)
            elif self.etat == ATTENTE and self.maintien_depuis is None:
                verifier = getattr(self.reseau, "doit_envoyer_aide", None)
                du = verifier(self.demande, maintenant) if verifier is not None else (
                    self.envois == 0 or self.ecart(maintenant, self.dernier_envoi) >= INTERVALLE_RELANCE_MS)
                if du:
                    self.envoyer(maintenant)

    def couleur(self, maintenant):
        if self.maintien_depuis is not None:
            # Orange fixe pendant le geste d'annulation, meme si une requete
            # demarre : le retour du geste en cours prime sur le cyan.
            return ORANGE
        if self.qualite_wifi is not None and not self.qualite_wifi.connecte:
            fixe = getattr(self.reseau, "lecture_de_fond", False)
            return VIOLET if fixe or (maintenant // 300) % 2 == 0 else (0, 0, 0)
        if getattr(self.reseau, "communication_en_cours", False):
            return CYAN
        # Requete de fond : couleur de l'etat sans clignotement, pour qu'une
        # pause TLS ne fige jamais le voyant dans sa phase eteinte.
        fixe = getattr(self.reseau, "lecture_de_fond", False)

        def clignoter(couleur, periode):
            return couleur if fixe or (maintenant // periode) % 2 == 0 else (0, 0, 0)

        if not self.reseau.disponible() or self.annulations_a_transmettre:
            return clignoter(VIOLET, 300)
        if self.etat == ATTENTE and self.envois == 0:
            return clignoter(VIOLET, 300)
        if self.etat == REPOS:
            return self.qualite_wifi.couleur_repos(maintenant) if self.qualite_wifi is not None and not fixe else (0, 0, 255)
        if self.etat == CONFIRMEE:
            return (0, 255, 0)
        if self.etat == ATTENTE:
            return clignoter(ORANGE, 500)
        if self.etat == SANS_CONFIRMATION:
            return clignoter((255, 0, 0), 150)
        return (0, 0, 0)


class VoyantRGB:
    """Couleur commune au bouton PWM et, en option, a la NeoPixel de la carte."""

    def __init__(self, sorties, pixel=None, luminosite_carte=32, respiration=False,
                 periode_bleu_ms=10_000, periode_vert_ms=4_000,
                 intensite_bleu=64, intensite_vert=96):
        if not isinstance(luminosite_carte, int) or not 0 <= luminosite_carte <= 255:
            raise ValueError("LUMINOSITE_RGB_CARTE doit etre un entier entre 0 et 255.")
        self.sorties = sorties
        self.pixel = pixel
        self.luminosite_carte = luminosite_carte
        self.derniere_couleur = None
        for periode in (periode_bleu_ms, periode_vert_ms):
            if not isinstance(periode, int) or not 1000 <= periode <= 60_000:
                raise ValueError("Periode de respiration : 1000 a 60000 ms.")
        for intensite in (intensite_bleu, intensite_vert):
            if not isinstance(intensite, int) or not 1 <= intensite <= 255:
                raise ValueError("Intensite de respiration : 1 a 255.")
        self.respiration = respiration
        self.periodes = {REPOS: periode_bleu_ms, CONFIRMEE: periode_vert_ms}
        self.intensites = {REPOS: intensite_bleu, CONFIRMEE: intensite_vert}
        self.etat_animation = None
        self.dernier_animation = None
        self.phase_animation = 0
        self.niveau_animation = None

    def afficher(self, couleur):
        if couleur != self.derniere_couleur:
            for sortie, intensite in zip(self.sorties, couleur):
                sortie.duty_u16(intensite * 257)
            if self.pixel is not None:
                self.pixel[0] = tuple(max(1, (v * self.luminosite_carte + 127) // 255)
                                      if self.respiration and v and self.luminosite_carte else
                                      (v * self.luminosite_carte + 127) // 255 for v in couleur)
                self.pixel.write()
            self.derniere_couleur = couleur

    def afficher_etat(self, boitier, maintenant):
        couleur = boitier.couleur(maintenant)
        if self.respiration:
            if boitier.etat != self.etat_animation:
                self.etat_animation = boitier.etat
                self.dernier_animation = None
                self.phase_animation = 0
                self.niveau_animation = None
            attendue = {REPOS: (0, 0, 255), CONFIRMEE: (0, 255, 0)}.get(boitier.etat)
            if couleur == attendue:
                periode, maximum = self.periodes[boitier.etat], self.intensites[boitier.etat]
                if self.niveau_animation is None:
                    self.niveau_animation = maximum
                if not getattr(boitier.reseau, "lecture_de_fond", False):
                    if self.dernier_animation is not None:
                        self.phase_animation = (self.phase_animation + ecart_ms(
                            maintenant, self.dernier_animation)) % periode
                    fraction = self.phase_animation * 2 / periode
                    triangle = fraction if fraction <= 1 else 2 - fraction
                    # Courbe douce, minimum visible ; pas de temps d'extinction.
                    douceur = triangle * triangle * (3 - 2 * triangle)
                    minimum = max(1, maximum // 5)
                    self.niveau_animation = round(maximum - (maximum - minimum) * douceur)
                couleur = tuple(v * self.niveau_animation // 255 for v in couleur)
                self.dernier_animation = maintenant
            elif self.dernier_animation is not None:
                self.dernier_animation = maintenant
        self.afficher(couleur)

    def eteindre(self):
        try:
            self.afficher((0, 0, 0))
        finally:
            for sortie in self.sorties:
                sortie.deinit()


def creer_voyant(configuration, Pin, PWM):
    # Sans profil materiel, le montage Wokwi a trois sorties reste identique.
    sorties = ()
    luminosite = getattr(configuration, "LUMINOSITE_RGB_CARTE", 32)
    if not isinstance(luminosite, int) or not 0 <= luminosite <= 255:
        raise ValueError("LUMINOSITE_RGB_CARTE doit etre un entier entre 0 et 255.")
    if getattr(configuration, "VOYANT_BOUTON_ACTIF", True):
        sorties = tuple(PWM(Pin(gpio), freq=1000, duty_u16=0)
                        for gpio in (GPIO_ROUGE, GPIO_VERT, GPIO_BLEU))
    pixel = None
    gpio = getattr(configuration, "GPIO_RGB_CARTE", None)
    if gpio is not None:
        from neopixel import NeoPixel
        pixel = NeoPixel(Pin(gpio, Pin.OUT), 1)
    return VoyantRGB(sorties, pixel, luminosite,
                     respiration=getattr(configuration, "RESPIRATION_VOYANTS", False),
                     periode_bleu_ms=getattr(configuration, "PERIODE_RESPIRATION_BLEU_MS", 10_000),
                     periode_vert_ms=getattr(configuration, "PERIODE_RESPIRATION_VERT_MS", 4_000),
                     intensite_bleu=getattr(configuration, "INTENSITE_BLEU_REPOS", 64),
                     intensite_vert=getattr(configuration, "INTENSITE_VERT_CONFIRME", 96))


class Bouton:
    def __init__(self, pin, maintenant, memoriser=False, ignorer_appui_initial=False):
        self.pin = pin
        self.stable = pin.value() == 0
        self.lecture = self.stable
        self.changement = maintenant
        self.derniere_lecture = maintenant
        self.appui_memorise = False
        self.attendre_relachement = ignorer_appui_initial and self.stable
        if memoriser:
            # TLS peut figer la boucle plusieurs centaines de ms. Le front
            # descendant est memorise par interruption et traite au reveil ;
            # sinon un appui bref complet pendant la pause serait perdu.
            pin.irq(trigger=pin.IRQ_FALLING, handler=self.memoriser_appui)

    def memoriser_appui(self, pin):
        self.appui_memorise = True

    def lire(self, maintenant):
        lecture = self.pin.value() == 0
        memorise, self.appui_memorise = self.appui_memorise, False
        pause = ecart_ms(maintenant, self.derniere_lecture) >= PAUSE_BOUCLE_MS
        self.derniere_lecture = maintenant
        if self.attendre_relachement:
            # Le geste de configuration ne doit jamais devenir une demande.
            if lecture != self.lecture:
                self.lecture = lecture
                self.changement = maintenant
            if not lecture and ecart_ms(maintenant, self.changement) >= ANTI_REBOND_MS:
                self.stable = False
                self.attendre_relachement = False
            return False
        # Seulement apres une pause : en boucle normale, l'anti-rebond suffit et
        # filtre les parasites. Bouton deja appuye : fronts de rebond, ignores.
        if memorise and pause and not self.stable and not lecture:
            # Appui et relachement pendant la pause : un appui est rapporte,
            # puis le relachement apres l'anti-rebond habituel.
            self.stable = True
            self.lecture = lecture
            self.changement = maintenant
            return True
        if lecture != self.lecture:
            self.lecture = lecture
            self.changement = maintenant
        if ecart_ms(maintenant, self.changement) >= ANTI_REBOND_MS:
            self.stable = lecture
        return self.stable


class Surveillance:
    """Nourrit le watchdog depuis la boucle des boutons, seulement si elle
    tourne ET si la tache reseau vit : sans elle, aucune aide ne part."""

    def __init__(self, wdt, tache_reseau=None, journal=print):
        self.wdt = wdt
        self.tache_reseau = tache_reseau
        self.journal = journal
        self.arret_signale = False

    def nourrir(self):
        if self.tache_reseau is not None and self.tache_reseau.done():
            if not self.arret_signale:
                self.arret_signale = True
                self.journal("[DIAGNOSTIC] Tache reseau arretee : redemarrage par watchdog.")
                diagnostic.evenement("tache_reseau_arretee")
            return
        self.wdt.feed()


async def boucle_principale():
    import machine
    from machine import Pin, PWM
    try:
        import asyncio
    except ImportError:
        import uasyncio as asyncio

    try:
        import configuration
    except ImportError:
        configuration = None
    journal_local = diagnostic.demarrer(machine, getattr(configuration, "WATCHDOG_MS", WATCHDOG_MS))
    from audio import creer_audio
    audio = creer_audio(configuration)
    voyant = creer_voyant(configuration, Pin, PWM)
    tache_wifi = None
    surveiller_wifi = getattr(configuration, "SURVEILLANCE_WIFI_REELLE",
                              getattr(configuration, "PORTAIL_WIFI_ACTIF", False))
    if surveiller_wifi or getattr(configuration, "PORTAIL_WIFI_ACTIF", False):
        from config_wifi import charger, demander_portail, connexion_simulee
        charger(configuration)
        if getattr(configuration, "PORTAIL_WIFI_ACTIF", False):
            await demander_portail(configuration, voyant, GPIO_AIDE)
        if configuration.MODE_RESEAU != "reel" and configuration.SSID:
            tache_wifi = asyncio.create_task(connexion_simulee(configuration))
    entrees_test = getattr(configuration, "ENTREES_TEST_ACTIVES", True)
    dernier_diagnostic = time.ticks_ms()
    maintenant = time.ticks_ms()
    aide = Bouton(Pin(GPIO_AIDE, Pin.IN, Pin.PULL_UP), maintenant, memoriser=True,
                  ignorer_appui_initial=getattr(configuration, "PORTAIL_WIFI_ACTIF", False))
    validation = Bouton(Pin(GPIO_VALIDATION, Pin.IN, Pin.PULL_UP), maintenant) if entrees_test else None
    wifi_test = Bouton(Pin(GPIO_WIFI_TEST, Pin.IN, Pin.PULL_UP), maintenant) if entrees_test else None
    pushbullet_test = Bouton(Pin(GPIO_PUSHBULLET_TEST, Pin.IN, Pin.PULL_UP), maintenant) if entrees_test else None
    reseau = ReseauSimule(latence_ms=LATENCE_RESEAU_MS)
    tache_reseau = None
    if configuration is not None and configuration.MODE_RESEAU == "reel":
        from pushbullet_reel import ReseauReel, valider_configuration
        valider_configuration(configuration)
        global INTERVALLE_RELANCE_MS
        INTERVALLE_RELANCE_MS = configuration.INTERVALLE_RELANCE_MS
        reseau = ReseauReel(configuration)
        tache_reseau = asyncio.create_task(reseau.boucle())
        print("[TEST REEL] Envois Pushbullet actifs. Repondre OK depuis Pushbullet ; V ne confirme pas.")
    else:
        print("[SIMULATION] Aucun envoi reel.")
    boitier = Boitier(reseau=reseau, audio=audio)
    diagnostic.contexte(etat=REPOS, phase="boucle_bouton")
    qualite_wifi = None
    if surveiller_wifi:
        import network
        qualite_wifi = SurveillanceWiFi(network.WLAN(network.STA_IF), bool(configuration.SSID),
                                       getattr(configuration, "SEUIL_WIFI_FAIBLE_DBM", -75))
        boitier.qualite_wifi = qualite_wifi
    print("AIDE : GPIO%d ; VALIDATION : GPIO%d. Autres contacts vers GND." % (
        GPIO_AIDE, GPIO_VALIDATION))
    print("Relances de test : %d ms, %d envois maximum par contact." % (
        INTERVALLE_RELANCE_MS, MAX_ENVOIS))
    print("Premier appui : aide immediate. Relacher avant un maintien d'annulation.")
    print("Apres confirmation ou plafond : appui bref AIDE = nouveau cycle au relachement.")
    if entrees_test:
        print("Interrupteurs GPIO13 (Wi-Fi) et GPIO14 (Pushbullet) : gauche OFF, droite ON.")
        print("V : OK fictif en simulation seulement.")
    else:
        print("Entrees de simulation V/Wi-Fi/Pushbullet desactivees sur carte.")
    print("Violet : transmission en attente ou reseau indisponible.")
    if qualite_wifi is not None:
        print("Wi-Fi absent/en connexion : violet clignotant. Signal faible au repos : double flash violet sur bleu.")
    if voyant.pixel is not None:
        print("LED RGB carte : GPIO%d ; luminosite %d/255 ; meme etat que le bouton." % (
            configuration.GPIO_RGB_CARTE, voyant.luminosite_carte))
    print("Cyan fixe : envoi AIDE/ANNULATION ; lecture de fond : couleur de l'etat sans clignoter.")
    if machine.reset_cause() == machine.WDT_RESET:
        print("[DIAGNOSTIC] Redemarrage par watchdog : une demande en RAM a pu etre perdue.")
    surveillance = None
    watchdog_ms = getattr(configuration, "WATCHDOG_MS", WATCHDOG_MS)
    if watchdog_ms:
        # Irreversible sur ESP32 : apres arret du programme (Ctrl-C), la carte
        # redemarre au bout de WATCHDOG_MS. Mettre 0 pour deboguer.
        surveillance = Surveillance(machine.WDT(timeout=watchdog_ms), tache_reseau)
        print("Watchdog : redemarrage si la boucle est bloquee %d s." % (watchdog_ms // 1000))

    try:
        while True:
            if surveillance is not None:
                surveillance.nourrir()
            maintenant = time.ticks_ms()
            if qualite_wifi is not None:
                qualite_wifi.actualiser(maintenant)
            wifi_disponible = wifi_test.lire(maintenant) if wifi_test is not None else None
            if qualite_wifi is not None and not getattr(reseau, "reel", False):
                # Sur carte, les envois fictifs attendent aussi le vrai Wi-Fi.
                wifi_disponible = qualite_wifi.connecte and wifi_disponible is not False
            boitier.actualiser(maintenant, aide.lire(maintenant),
                               validation.lire(maintenant) if validation is not None else False,
                               wifi_disponible,
                               pushbullet_test.lire(maintenant) if pushbullet_test is not None else None)
            voyant.afficher_etat(boitier, maintenant)
            if ecart_ms(maintenant, dernier_diagnostic) >= 30_000:
                dernier_diagnostic = maintenant
                journal_local.point(etat=boitier.etat)
                print("[DIAGNOSTIC] boucle active ; etat=%s ; RGB=%s ; temps=%d ms" % (
                    boitier.etat, str(voyant.derniere_couleur), maintenant))
                if qualite_wifi is not None:
                    print("[WIFI DIAGNOSTIC] etat=%s ; RSSI=%s" % (qualite_wifi.etat(), qualite_wifi.rssi))
            await asyncio.sleep(0.005)
    finally:
        if audio is not None:
            audio.arreter(time.ticks_ms())
        if tache_wifi is not None:
            tache_wifi.cancel()
        if tache_reseau is not None:
            tache_reseau.cancel()
        voyant.eteindre()
        diagnostic.evenement("arret_programme")
        print("[DIAGNOSTIC] Programme arrete : voyant eteint.")


def executer():
    try:
        import asyncio
    except ImportError:
        import uasyncio as asyncio
    try:
        asyncio.run(boucle_principale())
    except KeyboardInterrupt:
        diagnostic.contexte(phase="arret_manuel")
        diagnostic.evenement("arret_manuel")
        raise
    except Exception as erreur:
        diagnostic.evenement("exception", classe=type(erreur).__name__)
        raise


if __name__ == "__main__":
    executer()
