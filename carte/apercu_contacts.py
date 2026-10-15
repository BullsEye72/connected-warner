"""Apercu local du portail avec donnees fictives, sans carte ni Pushbullet."""
import asyncio
import tempfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "wokwi-test"))
import config_wifi


class StationFictive:
    def disconnect(self):
        pass
    def config(self, **options):
        pass
    def connect(self, ssid, mot_de_passe):
        pass
    def isconnected(self):
        return False


async def lancer():
    with tempfile.TemporaryDirectory(prefix="ps2-apercu-") as dossier:
        chemin = str(Path(dossier) / "wifi.json")
        config_wifi.ecrire_atomiquement(chemin, config_wifi.valider_identifiants("Maison de demonstration", "abcdefgh"))
        contacts = [{"nom": "Alice", "email": "alice@example.com", "actif": True},
                    {"nom": "Bob", "email": "bob@example.com", "actif": False}]
        portail = config_wifi.Portail(StationFictive(), token="apercu", chemin=chemin, contacts=contacts)
        connexion = portail.connecter
        async def connecter(donnees):
            await connexion(donnees, delai_ms=0)
        portail.connecter = connecter
        config_wifi.time.ticks_ms = lambda: int(asyncio.get_running_loop().time() * 1000)
        config_wifi.time.ticks_diff = lambda a, b: a - b
        async def traiter(reader, writer):
            methode, cible, entetes, corps = await config_wifi.lire_requete(reader)
            entetes["host"] = "192.168.4.1"
            requete = (methode + " " + cible + " HTTP/1.1\r\n" + "".join(
                cle + ": " + valeur + "\r\n" for cle, valeur in entetes.items()) + "\r\n").encode() + corps
            entree = asyncio.StreamReader()
            entree.feed_data(requete)
            entree.feed_eof()
            await portail.traiter(entree, writer)
        serveur = await asyncio.start_server(traiter, "127.0.0.1", 19082)
        print("Apercu fictif : http://127.0.0.1:19082/", flush=True)
        async with serveur:
            await serveur.serve_forever()


if __name__ == "__main__":
    asyncio.run(lancer())
