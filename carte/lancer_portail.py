"""Ouvrir le portail pour le diagnostic USB, sans refaire le geste BOOT."""
import asyncio
from machine import Pin, PWM
import configuration
from main import creer_voyant
from config_wifi import ouvrir_portail

asyncio.new_event_loop()  # Ecarter les anciennes taches apres un Ctrl-C en REPL.
asyncio.run(ouvrir_portail(configuration, creer_voyant(configuration, Pin, PWM)))
