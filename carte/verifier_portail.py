"""Diagnostic sur carte : portail, protection des POST et stockage temporaire."""
import asyncio
import os
import network
import socket
import struct
from machine import Pin, PWM
import configuration
from main import creer_voyant
import config_wifi


async def requete(texte):
    reader, writer = await asyncio.open_connection("192.168.4.1", 80)
    try:
        writer.write(texte.encode())
        await writer.drain()
        return await asyncio.wait_for(reader.read(), 5)
    finally:
        writer.close()
        await writer.wait_closed()


async def verifier():
    voyant = creer_voyant(configuration, Pin, PWM)
    tache = asyncio.create_task(config_wifi.ouvrir_portail(configuration, voyant))
    try:
        reponse = None
        for _ in range(100):
            await asyncio.sleep(0.1)
            if tache.done():
                await tache
                raise RuntimeError("Portail arrete avant le test")
            try:
                reponse = await requete("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\n\r\n")
                break
            except OSError:
                pass
        assert reponse and reponse.startswith(b"HTTP/1.1 200")
        assert b'name="ssid"' in reponse and b'name="mot_de_passe"' in reponse
        ap = network.WLAN(network.AP_IF)
        assert ap.config("security") == network.AUTH_WPA2_PSK
        print("[VERIFICATION] AP WPA2 et page HTTP 200 OK")
        question = struct.pack("!6H", 1234, 0x0100, 1, 0, 0, 0) + b"\x07captive\x05apple\x03com\x00\x00\x01\x00\x01"
        client_dns = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client_dns.setblocking(False)
        try:
            client_dns.sendto(question, ("192.168.4.1", 53))
            reponse_dns = None
            for _ in range(100):
                try:
                    reponse_dns, _ = client_dns.recvfrom(512)
                    break
                except OSError:
                    await asyncio.sleep(0.02)
            assert reponse_dns and reponse_dns[-4:] == b"\xc0\xa8\x04\x01"
            print("[VERIFICATION] DNS UDP 53 dirige vers 192.168.4.1")
        finally:
            client_dns.close()
        reponse = await requete("GET /hotspot-detect.html HTTP/1.1\r\nHost: captive.apple.com\r\n\r\n")
        assert reponse.startswith(b"HTTP/1.1 302") and b"Location: http://192.168.4.1/" in reponse
        print("[VERIFICATION] Sonde captive redirigee HTTP 302 vers la page locale")
        reponse = await requete("GET / HTTP/1.1\r\nHost: 192.168.4.1\r\nUser-Agent: Mozilla/5.0 (Linux; Android) Chrome/145.0 Mobile Safari/537.36\r\nAccept: text/html,application/xhtml+xml,*/*\r\nAccept-Language: fr-FR,fr;q=0.9\r\nCookie: exemple=" + "a" * 1500 + "\r\n\r\n")
        assert reponse.startswith(b"HTTP/1.1 200")
        print("[VERIFICATION] Requete de navigateur avec entetes longs HTTP 200 OK")
        corps = "token=invalide&ssid=Verification&mot_de_passe=abcdefgh"
        reponse = await requete("POST /wifi HTTP/1.1\r\nHost: 192.168.4.1\r\nContent-Type: application/x-www-form-urlencoded\r\nContent-Length: %d\r\n\r\n%s" % (len(corps), corps))
        assert reponse.startswith(b"HTTP/1.1 403")
        print("[VERIFICATION] POST sans autorisation refuse ; aucune connexion tentee")
    finally:
        tache.cancel()
        try:
            await tache
        except asyncio.CancelledError:
            pass
        voyant.afficher((0, 0, 255))
    assert not network.WLAN(network.AP_IF).active()
    chemin = "wifi_verification.json"
    try:
        for nom in ("Verification-1", "Verification-2"):
            config_wifi.ecrire_atomiquement(chemin, config_wifi.valider_identifiants(nom, "abcdefgh"))
            assert config_wifi.charger(configuration, chemin)
            assert configuration.SSID == nom
        print("[VERIFICATION] Remplacement atomique et relecture du fichier OK")
    finally:
        os.remove(chemin)
    print("[VERIFICATION] Diagnostic termine ; AP arrete, fichier de test supprime")


asyncio.new_event_loop()
asyncio.run(verifier())
