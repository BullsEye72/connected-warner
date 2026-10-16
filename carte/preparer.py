"""Prepare les seuls fichiers embarques pour MicroPico, sans ouvrir le port USB."""
from pathlib import Path
import shutil


def preparer():
    racine = Path(__file__).resolve().parent.parent
    destination = racine / ".deploy"
    destination.mkdir(exist_ok=True)
    for nom in ("main.py", "audio.py", "journal.py", "dashboard.py", "pushbullet_reel.py", "certificats.py", "ca.pem", "config_wifi.py", "contacts.py"):
        shutil.copyfile(racine / "wokwi-test" / nom, destination / nom)
    profil = racine / "carte" / "configuration_privee.py"
    if not profil.exists():
        profil = racine / "carte" / "configuration_exemple.py"
    shutil.copyfile(profil, destination / "configuration.py")
    print("Fichiers pour la carte :", destination)
    print("Profil utilise :", profil.name)


if __name__ == "__main__":
    preparer()
