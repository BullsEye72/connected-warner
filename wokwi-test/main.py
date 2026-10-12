import time

# Mode simule par defaut ; configuration.py permet les essais Pushbullet reels.
GPIO_ROUGE = 3
GPIO_VERT = 8
GPIO_BLEU = 18
GPIO_AIDE = 12
GPIO_VALIDATION = 40
GPIO_WIFI_TEST = 13
GPIO_PUSHBULLET_TEST = 14
ANTI_REBOND_MS = 30
ANNULATION_MS = 10_000
INTERVALLE_RELANCE_MS = 5_000  # Essais rapides ; cible : 120_000.
MAX_ENVOIS = 5  # Premier envoi compris.
RETOUR_REPOS_MS = 600_000  # Dix minutes apres confirmation.
ORANGE = (255, 80, 0)  # Intensites 0..255 ; ajustables selon la LED.
VIOLET = (180, 0, 255)
CYAN = (0, 255, 255)  # Fixe pendant les communications ; reprend l'etat ensuite.
LATENCE_RESEAU_MS = 750  # Une requete simulee ne bloque pas les boutons.
INTERVALLE_REESSAI_MS = 2_000  # Apres echec, distinct des relances acceptees.

REPOS = "REPOS"
ATTENTE = "ATTENTE"
SANS_CONFIRMATION = "SANS_CONFIRMATION"
CONFIRMEE = "CONFIRMEE"
ANNULEE = "ANNULEE"


def ecart_ms(fin, debut):
    return time.ticks_diff(fin, debut)


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
    def __init__(self, journal=print, ecart=ecart_ms, reseau=None):
        self.journal = journal
        self.ecart = ecart
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
            return
        if resultat["nature"] == "ANNULATION":
            self.annulations_a_transmettre.remove(resultat["demande"])
            self.journal("[FAUX RESEAU] Annulation demande %d acceptee par Pushbullet simule." % resultat["demande"])
            self.dernier_essai = None
            return
        if resultat["demande"] != self.demande or self.etat not in (ATTENTE, CONFIRMEE):
            return
        self.envois += 1
        self.dernier_envoi = maintenant
        self.journal("[SIMULATION] Demande %d : notification %d/%d" % (
            self.demande, self.envois, MAX_ENVOIS))
        if self.envois == MAX_ENVOIS and self.etat == ATTENTE:
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

    def actualiser(self, maintenant, aide, validation, wifi_disponible=None, pushbullet_disponible=None):
        appui_aide = aide and not self.aide_avant
        relache_aide = not aide and self.aide_avant
        appui_validation = validation and not self.validation_avant
        self.aide_avant = aide
        self.validation_avant = validation
        # Les interrupteurs imposent un etat, au lieu de basculer a l'appui.
        # None laisse le faux reseau inchange pour les tests sans entree physique.
        self.reseau.configurer(wifi=wifi_disponible, pushbullet=pushbullet_disponible)

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
            if self.maintien_depuis is not None and self.etat == ATTENTE:
                # Geste interrompu : reprendre apres un intervalle complet,
                # sans rattraper les notifications suspendues.
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

        self.traiter_envoi(maintenant)
        while True:
            demande_ok = self.reseau.lire_ok()
            if demande_ok is None:
                break
            if demande_ok == self.demande and self.etat in (ATTENTE, SANS_CONFIRMATION):
                self.changer_etat(CONFIRMEE)
                self.confirmee_depuis = maintenant
                self.dernier_resultat = (self.demande, CONFIRMEE)
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
                if self.envois == 0 or self.ecart(maintenant, self.dernier_envoi) >= INTERVALLE_RELANCE_MS:
                    self.envoyer(maintenant)

    def couleur(self, maintenant):
        if getattr(self.reseau, "communication_en_cours", False):
            return CYAN
        if self.maintien_depuis is not None:
            return ORANGE  # Orange fixe pendant le geste d'annulation.
        if not self.reseau.disponible() or self.annulations_a_transmettre:
            return VIOLET if (maintenant // 300) % 2 == 0 else (0, 0, 0)
        if self.etat == ATTENTE and self.envois == 0:
            return VIOLET if (maintenant // 300) % 2 == 0 else (0, 0, 0)
        if self.etat == REPOS:
            return (0, 0, 255)
        if self.etat == CONFIRMEE:
            return (0, 255, 0)
        if self.etat == ATTENTE:
            return ORANGE if (maintenant // 500) % 2 == 0 else (0, 0, 0)
        if self.etat == SANS_CONFIRMATION:
            return (255 if (maintenant // 150) % 2 == 0 else 0, 0, 0)
        return (0, 0, 0)


class VoyantRGB:
    """Un seul chemin de commande, sans reprogrammer un PWM inchange."""

    def __init__(self, sorties):
        self.sorties = sorties
        self.derniere_couleur = None

    def afficher(self, couleur):
        if couleur != self.derniere_couleur:
            for sortie, intensite in zip(self.sorties, couleur):
                sortie.duty_u16(intensite * 257)
            self.derniere_couleur = couleur

    def afficher_etat(self, boitier, maintenant):
        self.afficher(boitier.couleur(maintenant))

    def eteindre(self):
        self.afficher((0, 0, 0))
        for sortie in self.sorties:
            sortie.deinit()


class Bouton:
    def __init__(self, pin, maintenant):
        self.pin = pin
        self.stable = pin.value() == 0
        self.lecture = self.stable
        self.changement = maintenant

    def lire(self, maintenant):
        lecture = self.pin.value() == 0
        if lecture != self.lecture:
            self.lecture = lecture
            self.changement = maintenant
        if ecart_ms(maintenant, self.changement) >= ANTI_REBOND_MS:
            self.stable = lecture
        return self.stable


async def boucle_principale():
    from machine import Pin, PWM
    try:
        import asyncio
    except ImportError:
        import uasyncio as asyncio

    leds = (
        PWM(Pin(GPIO_ROUGE), freq=1000, duty_u16=0),
        PWM(Pin(GPIO_VERT), freq=1000, duty_u16=0),
        PWM(Pin(GPIO_BLEU), freq=1000, duty_u16=0),
    )
    voyant = VoyantRGB(leds)
    dernier_diagnostic = time.ticks_ms()
    maintenant = time.ticks_ms()
    aide = Bouton(Pin(GPIO_AIDE, Pin.IN, Pin.PULL_UP), maintenant)
    validation = Bouton(Pin(GPIO_VALIDATION, Pin.IN, Pin.PULL_UP), maintenant)
    wifi_test = Bouton(Pin(GPIO_WIFI_TEST, Pin.IN, Pin.PULL_UP), maintenant)
    pushbullet_test = Bouton(Pin(GPIO_PUSHBULLET_TEST, Pin.IN, Pin.PULL_UP), maintenant)
    reseau = ReseauSimule(latence_ms=LATENCE_RESEAU_MS)
    tache_reseau = None
    try:
        import configuration
    except ImportError:
        configuration = None
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
    boitier = Boitier(reseau=reseau)
    print("AIDE : GPIO%d ; VALIDATION : GPIO%d. Autres contacts vers GND." % (
        GPIO_AIDE, GPIO_VALIDATION))
    print("Relances de test : %d ms, %d envois maximum." % (
        INTERVALLE_RELANCE_MS, MAX_ENVOIS))
    print("Premier appui : aide immediate. Relacher avant un maintien d'annulation.")
    print("Apres confirmation ou plafond : appui bref AIDE = nouveau cycle au relachement.")
    print("Interrupteurs GPIO13 (Wi-Fi) et GPIO14 (Pushbullet) : gauche OFF, droite ON.")
    print("V : OK fictif en simulation seulement. Violet : transmission en attente ou reseau indisponible.")
    print("Cyan fixe : communication en cours ; reprise de la couleur de l'etat ensuite.")

    try:
        while True:
            maintenant = time.ticks_ms()
            boitier.actualiser(maintenant, aide.lire(maintenant), validation.lire(maintenant),
                               wifi_test.lire(maintenant), pushbullet_test.lire(maintenant))
            voyant.afficher_etat(boitier, maintenant)
            if ecart_ms(maintenant, dernier_diagnostic) >= 30_000:
                dernier_diagnostic = maintenant
                print("[DIAGNOSTIC] boucle active ; etat=%s ; RGB=%s ; temps=%d ms" % (
                    boitier.etat, str(voyant.derniere_couleur), maintenant))
            await asyncio.sleep(0.005)
    finally:
        if tache_reseau is not None:
            tache_reseau.cancel()
        voyant.eteindre()
        print("[DIAGNOSTIC] Programme arrete : voyant eteint.")


def executer():
    try:
        import asyncio
    except ImportError:
        import uasyncio as asyncio
    asyncio.run(boucle_principale())


if __name__ == "__main__":
    executer()
