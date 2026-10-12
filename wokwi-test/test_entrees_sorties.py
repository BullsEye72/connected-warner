from machine import Pin
import time

# Premier test, valide dans Wokwi le 12 octobre 2026.
rouge = Pin(3, Pin.OUT, value=0)
vert = Pin(8, Pin.OUT, value=0)
bleu = Pin(18, Pin.OUT, value=0)
bouton = Pin(39, Pin.IN, Pin.PULL_UP)


def couleur(r, v, b):
    rouge.value(r)
    vert.value(v)
    bleu.value(b)


try:
    for nom, valeurs in (
        ("Rouge", (1, 0, 0)),
        ("Vert", (0, 1, 0)),
        ("Bleu", (0, 0, 1)),
    ):
        print(nom)
        couleur(*valeurs)
        time.sleep_ms(500)

    etat = bouton.value()
    derniere_lecture = etat
    changement_ms = time.ticks_ms()
    couleur(1 - etat, 0, 0)
    print("Pret : appui = rouge, relachement = eteint.")

    while True:
        lecture = bouton.value()
        maintenant = time.ticks_ms()
        if lecture != derniere_lecture:
            derniere_lecture = lecture
            changement_ms = maintenant
        if lecture != etat and time.ticks_diff(maintenant, changement_ms) >= 30:
            etat = lecture
            couleur(1 - etat, 0, 0)
            print("Bouton appuye" if etat == 0 else "Bouton relache")
        time.sleep_ms(5)
finally:
    couleur(0, 0, 0)
