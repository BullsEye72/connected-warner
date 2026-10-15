"""Essai volontaire du watchdog sur carte, via mpremote run --no-follow.

Le programme ne nourrit plus le minuteur et bloque pendant son delai : la carte
doit redemarrer seule, puis lancer main.py normalement. Aucun appel Pushbullet.
Ce fichier de diagnostic ne fait pas partie des fichiers deployes.
"""
import machine
import configuration
import journal
from main import Surveillance

delai = configuration.WATCHDOG_MS
if delai != 60_000:
    raise ValueError("Le diagnostic attend WATCHDOG_MS = 60000.")

journal.demarrer(machine, delai, essai=True)
journal.contexte(phase="blocage volontaire watchdog", etat="ESSAI", essai=True)
journal.evenement("essai_watchdog")

surveillance = Surveillance(machine.WDT(timeout=delai))
surveillance.nourrir()
print("[VERIFICATION] Watchdog 60000 ms arme ; blocage volontaire sans alimentation du minuteur.")
while True:
    pass
