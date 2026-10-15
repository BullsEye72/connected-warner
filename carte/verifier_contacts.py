"""Verification MicroPython avec contacts fictifs ; aucun appel Pushbullet reel."""
import asyncio
import json
import os
import pushbullet_reel as pb
import config_wifi as wifi
from contacts import valider_contacts
from main import Boitier, CONFIRMEE


CONTACTS = valider_contacts([{"nom": "Alice", "email": "alice@example.com", "actif": True},
                             {"nom": "Bob", "email": "bob@example.com", "actif": True}])


class Profil:
    INTERVALLE_RELANCE_MS = 10_000


class ReseauEssai(pb.ReseauReel):
    def __init__(self):
        self.c = Profil()
        self.journal = lambda message: None
        self.suivi = pb.SuiviGroupe(CONTACTS, "Lit", "ESSAI")
        self.suivi.identifier({"iden": "boitier", "email": "boitier@example.com"})
        self.resultats, self.confirmations, self.appels = [], [], []
        self.annonces = []
        self.en_cours = self.tache_envoi = None
        self.echec_bob = False

    def disponible(self):
        return True

    async def api(self, methode, chemin, charge, fond=False):
        self.appels.append(charge["email"])
        if charge["email"] == "bob@example.com" and not self.echec_bob:
            self.echec_bob = True
            raise pb.ApiErreur("Echec fictif", True)
        return {"iden": "push" + str(len(self.appels)), "created": 100,
                "receiver_iden": "id-" + charge["email"]}


class StationFictive:
    def disconnect(self):
        pass
    def config(self, **options):
        pass
    def connect(self, ssid, mot_de_passe):
        pass
    def isconnected(self):
        return False


async def verifier():
    chemin = "wifi_verification_contacts.json"
    try:
        os.stat(chemin)
    except OSError:
        pass
    else:
        raise RuntimeError("Fichier de test deja present ; verification non lancee")
    donnees = wifi.valider_identifiants("Verification", "abcdefgh")
    donnees.update(nom_boitier="Lit", contacts=CONTACTS)
    portail = wifi.Portail(StationFictive(), chemin=chemin, contacts=CONTACTS)
    try:
        await portail.connecter(donnees, delai_ms=0)
        assert portail.etat == "non_verifie"
        assert portail.enregistrer(donnees, False)
        profil = Profil()
        assert wifi.charger(profil, chemin) and len(profil.DESTINATAIRES) == 2
        assert 'id="contacts-seuls"' in wifi.page("test", [], "Lit", CONTACTS).decode()
        print("[VERIFICATION] Portail : contacts et preconfiguration relus depuis un fichier de test")
    finally:
        try:
            os.remove(chemin)
        except OSError:
            pass
    horloge, initial = [0], pb.maintenant_ms
    pb.maintenant_ms = lambda: horloge[0]
    try:
        reseau = ReseauEssai()
        boitier = Boitier(lambda message: None, lambda a, b: a - b, reseau)
        boitier.actualiser(0, True, False)
        await reseau.tache_envoi
        boitier.actualiser(40, False, False)
        assert reseau.appels == ["alice@example.com", "bob@example.com"]
        horloge[0] = 2000
        boitier.actualiser(2000, False, False)
        await reseau.tache_envoi
        boitier.actualiser(2040, False, False)
        assert reseau.appels == ["alice@example.com", "bob@example.com", "bob@example.com"]
        assert boitier.envois == 1
        reponse = {"iden": "ok", "active": True, "type": "note", "created": 101,
                   "receiver_iden": "boitier", "sender_iden": "id-bob@example.com",
                   "sender_email": "bob@example.com", "direction": "incoming", "body": "OK"}
        reseau.confirmations.append(reseau.suivi.examiner(reponse))
        boitier.actualiser(2100, False, False)
        assert boitier.etat == CONFIRMEE and reseau.suivi.terminee(1)
        print("[VERIFICATION] Diffusion, echec partiel, reessai cible et premier OK : OK")
        reseau.annonces.extend(reseau.suivi.messages_confirmation(1))
        assert len(reseau.annonces) == 1
        assert "Bob a répondu OK" in reseau.annonces[0]["body"]
        await reseau.annoncer_confirmation()
        await reseau.annoncer_confirmation()
        assert reseau.appels[-1] == "alice@example.com" and len(reseau.appels) == 4
        assert boitier.envois == 1 and boitier.etat == CONFIRMEE
        print("[VERIFICATION] Annonce aux autres contacts, une fois, sans modifier le vert : OK")
    finally:
        pb.maintenant_ms = initial
    print("[VERIFICATION] Aucun message reel ; reglages Wi-Fi et contacts reels inchanges")


asyncio.new_event_loop()
asyncio.run(verifier())
