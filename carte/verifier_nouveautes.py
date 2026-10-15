"""Essai sur carte : stockage de test et respiration, sans notification reelle."""
import asyncio
import json
import os
import time
from machine import Pin, PWM
import configuration
import config_wifi
from main import Boitier, CONFIRMEE, creer_voyant


class StationAbsente:
    def disconnect(self):
        pass

    def config(self, **options):
        pass

    def connect(self, ssid, mot_de_passe):
        pass

    def isconnected(self):
        return False


async def requete(methode, cible, corps=""):
    reader, writer = await asyncio.open_connection("127.0.0.1", 19081)
    try:
        writer.write(("%s %s HTTP/1.1\r\nHost: 192.168.4.1\r\n"
                      "Content-Type: application/x-www-form-urlencoded\r\n"
                      "Content-Length: %d\r\n\r\n%s" % (
                          methode, cible, len(corps.encode()), corps)).encode())
        await writer.drain()
        return await asyncio.wait_for(reader.read(), 5)
    finally:
        writer.close()
        await writer.wait_closed()


async def verifier():
    chemin = "wifi_verification_nouveautes.json"
    try:
        os.stat(chemin)
    except OSError:
        pass
    else:
        raise RuntimeError("Fichier de test deja present : verification non lancee")
    portail = config_wifi.Portail(StationAbsente(), chemin=chemin, nom_boitier="Lit")
    serveur = await asyncio.start_server(portail.traiter, "127.0.0.1", 19081)
    try:
        reponse = await requete("GET", "/")
        assert reponse.startswith(b"HTTP/1.1 200")
        assert b'name="nom_boitier"' in reponse and b'id="continuer"' in reponse
        donnees = config_wifi.valider_identifiants("Reseau de verification absent", "abcdefgh")
        donnees["nom_boitier"] = "Preconfiguration"
        await portail.connecter(donnees, delai_ms=0)
        assert portail.etat == "non_verifie"
        corps = "token=%s&confirmation=%s" % (portail.token, portail.confirmation)
        reponse = await requete("POST", "/enregistrer", corps)
        assert reponse.startswith(b"HTTP/1.1 200") and portail.etat == "ok"
        with open(chemin) as fichier:
            sauvegarde = json.load(fichier)
        assert sauvegarde["connexion_verifiee"] is False
        class Profil:
            PIECE = "Lit"
        profil = Profil()
        assert config_wifi.charger(profil, chemin) and profil.PIECE == "Preconfiguration"
        print("[VERIFICATION] HTTP 200 : nom, confirmation sans Wi-Fi et relecture OK (fichier de test)")
    finally:
        serveur.close()
        await serveur.wait_closed()
        try:
            os.remove(chemin)
        except OSError:
            pass
    voyant = creer_voyant(configuration, Pin, PWM)
    boitier = Boitier(journal=lambda message: None)
    for etat, duree, etiquette in ((boitier.etat, 20_000, "bleu : deux cycles de 10 secondes"),
                                  (CONFIRMEE, 8000, "vert : deux cycles de 4 secondes")):
        boitier.etat = etat
        print("[VERIFICATION] Rendu de test " + etiquette)
        debut = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), debut) < duree:
            voyant.afficher_etat(boitier, time.ticks_ms())
            await asyncio.sleep(0.02)
    print("[VERIFICATION] Termine : aucun envoi Pushbullet, aucun changement du Wi-Fi enregistre")


asyncio.new_event_loop()
asyncio.run(verifier())
