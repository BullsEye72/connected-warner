"""Lire un diagnostic de repos autonome sur COM4, depuis le PC."""
import time
import serial
import re

port = serial.Serial(port=None, baudrate=115200, timeout=0.2)
port.dtr = False
port.rts = False
port.port = "COM4"
port.open()
limite = time.monotonic() + 35
ligne = bytearray()
try:
    while time.monotonic() < limite:
        for octet in port.read(port.in_waiting or 1):
            ligne.append(octet)
            if octet == 10:
                texte = ligne.decode("utf-8", "replace").strip()
                ligne.clear()
                if texte:
                    print(texte, flush=True)
                if "[DIAGNOSTIC] boucle active" in texte:
                    bleu = re.search(r"RGB=\(0, 0, ([0-9]+)\)", texte)
                    assert "etat=REPOS" in texte and bleu and int(bleu.group(1)) > 0
                    print("Demarrage normal apres fenetre de configuration : OK", flush=True)
                    raise SystemExit(0)
    raise SystemExit("Diagnostic de boucle non recu")
finally:
    port.close()
