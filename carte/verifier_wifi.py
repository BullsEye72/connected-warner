"""Essai sur carte : Wi-Fi reel coupe/restaure, puis rendu d'un signal faible simule."""
import asyncio
import time
import network
from machine import Pin, PWM
import configuration
from config_wifi import charger
from main import Boitier, SurveillanceWiFi, creer_voyant, VIOLET


async def verifier():
    assert charger(configuration), "Configurer le Wi-Fi avant cet essai"
    station = network.WLAN(network.STA_IF)
    voyant = creer_voyant(configuration, Pin, PWM)
    boitier = Boitier()
    qualite = SurveillanceWiFi(station)
    boitier.qualite_wifi = qualite
    try:
        station.active(False)
        qualite.actualiser(time.ticks_ms())
        assert not qualite.connecte
        assert boitier.couleur(0) == VIOLET
        print("[VERIFICATION] Wi-Fi reel coupe : violet clignotant pendant 5 secondes")
        fin = time.ticks_add(time.ticks_ms(), 5000)
        while time.ticks_diff(fin, time.ticks_ms()) > 0:
            voyant.afficher_etat(boitier, time.ticks_ms())
            await asyncio.sleep(0.02)
        station.active(True)
        station.config(reconnects=-1)
        station.connect(configuration.SSID, configuration.MOT_DE_PASSE_WIFI)
        fin = time.ticks_add(time.ticks_ms(), 25_000)
        while time.ticks_diff(fin, time.ticks_ms()) > 0:
            qualite.actualiser(time.ticks_ms())
            voyant.afficher_etat(boitier, time.ticks_ms())
            if qualite.connecte:
                break
            await asyncio.sleep(0.05)
        assert qualite.connecte, "Reconnexion Wi-Fi non confirmee"
        print("[VERIFICATION] Wi-Fi reconnecte, RSSI reel=%s dBm" % qualite.rssi)
        qualite.faible = True  # Verifier le rendu sans pretendre affaiblir la radio.
        print("[VERIFICATION] Rendu signal faible simule : double flash violet sur bleu pendant 8 secondes")
        fin = time.ticks_add(time.ticks_ms(), 8000)
        while time.ticks_diff(fin, time.ticks_ms()) > 0:
            voyant.afficher_etat(boitier, time.ticks_ms())
            await asyncio.sleep(0.02)
        qualite.faible = False
        voyant.afficher_etat(boitier, time.ticks_ms())
        print("[VERIFICATION] Retour au bleu ; identifiants conserves ; aucune notification reelle")
    finally:
        if not station.active():
            station.active(True)
            station.config(reconnects=-1)
            station.connect(configuration.SSID, configuration.MOT_DE_PASSE_WIFI)


asyncio.new_event_loop()
asyncio.run(verifier())
