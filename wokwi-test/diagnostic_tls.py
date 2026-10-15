"""Diagnostic Wokwi : trois GET sans jeton, aucun POST, aucun fichier de secrets lu.

Pour l'essai seulement, copier ce fichier dans main.py de Wokwi puis arreter
et relancer. Retablir ensuite le main.py des boutons depuis le workspace.
Conserver pushbullet_reel.py et certificats.py dans le projet.
"""
import time
import sys
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

from pushbullet_reel import (HOTE_API, charger_certificats, decrire_erreur_transport,
                            lire_reponse_http, maintenant_ms, ecart_ms, synchroniser_horloge)

REQUETE = ("GET /v2/users/me HTTP/1.1\r\nHost: %s\r\n"
           "Accept: application/json\r\nAccept-Encoding: identity\r\n"
           "Connection: close\r\n\r\n" % HOTE_API).encode()

HOTE_TEMOIN = "docs.micropython.org"


def contexte_tls():
    import ssl
    contexte = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    contexte.verify_mode = ssl.CERT_REQUIRED
    charger_certificats(contexte, "ca.pem")
    return contexte


async def sonde_async(contexte, adresse):
    print("[SONDE ASYNC] connexion TCP/TLS...")
    lecteur, ecrivain = await asyncio.open_connection(
        adresse, 443, ssl=contexte, server_hostname=HOTE_API)
    try:
        print("[SONDE ASYNC] ecriture / negociation TLS...")
        ecrivain.write(REQUETE)
        await ecrivain.drain()
        print("[SONDE ASYNC] lecture HTTP...")
        statut, _, _ = await lire_reponse_http(lecteur)
        print("[SONDE ASYNC] HTTP %d (401 attendu sans jeton)." % statut)
    finally:
        try:
            ecrivain.close()
            await asyncio.wait_for(ecrivain.wait_closed(), 1)
        except Exception:
            pass


def sonde_bloquante(contexte, adresse, hote=HOTE_API, chemin="/v2/users/me",
                    etiquette="BLOQUANTE"):
    import socket
    sock = socket.socket()
    flux = None
    try:
        sock.settimeout(30)
        print("[SONDE %s] connexion TCP vers %s..." % (etiquette, hote))
        sock.connect((adresse, 443))
        print("[SONDE %s] negociation TLS verifiee..." % etiquette)
        flux = contexte.wrap_socket(sock, server_hostname=hote,
                                   do_handshake_on_connect=True)
        print("[SONDE %s] ecriture puis lecture HTTP..." % etiquette)
        requete = ("GET %s HTTP/1.1\r\nHost: %s\r\n"
                   "Accept-Encoding: identity\r\nConnection: close\r\n\r\n"
                   % (chemin, hote)).encode()
        donnees = memoryview(requete)
        position = 0
        while position < len(donnees):
            nombre = flux.write(donnees[position:])
            if nombre is None or nombre <= 0:
                raise OSError("Ecriture incomplete")
            position += nombre
        ligne = flux.readline()
        morceaux = ligne.split()
        if len(morceaux) < 2 or not morceaux[0].startswith(b"HTTP/"):
            raise OSError("Statut HTTP invalide")
        print("[SONDE %s] HTTP %d ; TLS et lecture du statut reussis."
              % (etiquette, int(morceaux[1])))
    finally:
        if flux is not None:
            try:
                flux.close()
            except Exception:
                pass
        try:
            sock.close()
        except Exception:
            pass


async def executer():
    import network
    import socket
    print("[SONDE] Aucun jeton utilise ; aucune notification envoyee.")
    print("[SONDE] Version SONDE-TLS-2 ; temoin puis Pushbullet.")
    print("[SONDE] Firmware :", sys.version)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect("Wokwi-GUEST", "")
        debut = maintenant_ms()
        while not wlan.isconnected():
            if ecart_ms(maintenant_ms(), debut) >= 20_000:
                raise OSError("Connexion Wi-Fi indisponible")
            await asyncio.sleep(0.1)
    await synchroniser_horloge()
    print("[SONDE] UTC : %04d-%02d-%02d %02d:%02d:%02d" % time.gmtime()[:6])
    debut = maintenant_ms()
    try:
        adresse_temoin = socket.getaddrinfo(HOTE_TEMOIN, 443, 0, socket.SOCK_STREAM)[0][-1][0]
        sonde_bloquante(contexte_tls(), adresse_temoin, HOTE_TEMOIN, "/", "TEMOIN")
    except Exception as erreur:
        print("[SONDE TEMOIN] ECHEC : " + decrire_erreur_transport(erreur))
    print("[SONDE TEMOIN] duree observee : %d ms." % ecart_ms(maintenant_ms(), debut))
    await asyncio.sleep(0.5)
    # Meme adresse et meme contenu de certificats pour comparer les deux modes.
    adresse = socket.getaddrinfo(HOTE_API, 443, 0, socket.SOCK_STREAM)[0][-1][0]
    for nom in ("ASYNC", "BLOQUANTE"):
        contexte = contexte_tls()
        debut = maintenant_ms()
        try:
            if nom == "ASYNC":
                await asyncio.wait_for(sonde_async(contexte, adresse), 30)
            else:
                # Isole deliberement l'API TLS du scheduler asyncio.
                sonde_bloquante(contexte, adresse)
        except Exception as erreur:
            print("[SONDE %s] ECHEC : %s" % (nom, decrire_erreur_transport(erreur)))
        print("[SONDE %s] duree observee : %d ms." % (nom, ecart_ms(maintenant_ms(), debut)))
        await asyncio.sleep(0.5)
    print("[SONDE] Termine. Retablir ensuite le main.py des boutons.")


if __name__ == "__main__":
    try:
        asyncio.run(executer())
    except Exception as erreur:
        print("[SONDE] Preparation impossible : " + decrire_erreur_transport(erreur))
