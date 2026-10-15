# A executer sur la carte, avec main.py et configuration.py deja transferes.
import time
from machine import Pin, PWM
import configuration
from main import creer_voyant

voyant = creer_voyant(configuration, Pin, PWM)
try:
    for nom, couleur in (
        ("ROUGE", (255, 0, 0)),
        ("VERT", (0, 255, 0)),
        ("BLEU", (0, 0, 255)),
    ):
        print(nom)
        voyant.afficher(couleur)
        time.sleep_ms(3000)
finally:
    voyant.afficher((0, 0, 255))
    print("Fin du test : bleu au repos.")
