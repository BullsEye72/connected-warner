"""Configuration locale du Wi-Fi, disponible uniquement au demarrage sur carte."""
import json
import os
import time
import binascii
import struct
import journal as diagnostic
from contacts import valider_contacts, contacts_configuration, MAX_CONTACTS
try:
    import asyncio
except ImportError:
    import uasyncio as asyncio

FICHIER_WIFI = "wifi.json"
FICHIER_INSTALLATION = "wifi_installation.json"
BLANC = (255, 255, 255)
ADRESSE_PORTAIL = "192.168.4.1"
URL_PORTAIL = "http://192.168.4.1/"
MAX_CORPS = 12_288


def reponse_dns(paquet):
    """DNS du reseau d'installation : A vers le portail, autres types sans reponse."""
    if len(paquet) < 12:
        return None
    identifiant, flags, questions, _, _, _ = struct.unpack("!6H", paquet[:12])
    if flags & 0xF800 or questions != 1:
        return None
    offset = 12
    while True:
        if offset >= len(paquet) or offset - 12 > 254:
            return None
        longueur = paquet[offset]
        offset += 1
        if longueur == 0:
            break
        if longueur > 63 or offset + longueur >= len(paquet):
            return None
        offset += longueur
    if offset + 4 > len(paquet):
        return None
    type_question, classe = struct.unpack("!HH", paquet[offset:offset + 4])
    fin = offset + 4
    nombre = 1 if type_question == 1 and classe == 1 else 0
    entete = struct.pack("!6H", identifiant, 0x8400 | (flags & 0x0100), 1, nombre, 0, 0)
    reponse = entete + paquet[12:fin]
    if nombre:
        reponse += struct.pack("!HHHIH", 0xC00C, 1, 1, 0, 4) + bytes((192, 168, 4, 1))
    return reponse


class DNSCaptif:
    def __init__(self, adresse=ADRESSE_PORTAIL, port=53):
        import socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.requetes = 0
        try:
            self.sock.setblocking(False)
            self.sock.bind((adresse, port))
        except Exception:
            self.sock.close()
            raise

    async def boucle(self):
        try:
            while True:
                try:
                    paquet, source = self.sock.recvfrom(512)
                    reponse = reponse_dns(paquet)
                    if reponse is not None:
                        self.sock.sendto(reponse, source)
                        self.requetes += 1
                except OSError as erreur:
                    if not erreur.args or erreur.args[0] not in (11, 35, 10035):
                        raise
                    await asyncio.sleep(0.02)
                else:
                    # Eviter qu'un flux DNS continu monopolise la boucle.
                    await asyncio.sleep(0)
        finally:
            self.sock.close()


def valider_identifiants(ssid, mot_de_passe, ouvert=False):
    if not isinstance(ssid, str) or not 1 <= len(ssid.encode()) <= 32 or "\x00" in ssid:
        raise ValueError("Le nom du reseau doit contenir de 1 a 32 octets.")
    if not isinstance(mot_de_passe, str) or "\x00" in mot_de_passe:
        raise ValueError("Mot de passe invalide.")
    if ouvert:
        if mot_de_passe:
            raise ValueError("Un reseau ouvert ne doit pas avoir de mot de passe.")
    elif not 8 <= len(mot_de_passe.encode()) <= 63:
        raise ValueError("Le mot de passe doit contenir de 8 a 63 octets.")
    return {"version": 1, "ssid": ssid, "mot_de_passe": mot_de_passe}


def valider_nom_boitier(nom):
    if not isinstance(nom, str):
        raise ValueError("Nom du boitier invalide.")
    nom = nom.strip()
    if not 1 <= len(nom) <= 40 or any(ord(c) < 32 or ord(c) == 127 for c in nom):
        raise ValueError("Le nom du boitier doit contenir de 1 a 40 caracteres, sans controle.")
    return nom


def ecrire_atomiquement(chemin, donnees):
    temporaire = chemin + ".tmp"
    try:
        with open(temporaire, "w") as fichier:
            json.dump(donnees, fichier)
            fichier.flush()
        if hasattr(os, "sync"):
            os.sync()
        if hasattr(os, "replace"):
            os.replace(temporaire, chemin)
        else:
            os.rename(temporaire, chemin)
        if hasattr(os, "sync"):
            os.sync()
    finally:
        try:
            os.remove(temporaire)
        except OSError:
            pass


def charger(configuration, chemin=FICHIER_WIFI):
    try:
        with open(chemin) as fichier:
            donnees = json.load(fichier)
        if donnees.get("version") != 1:
            raise ValueError("Version inconnue")
        nom = valider_nom_boitier(donnees["nom_boitier"]) if "nom_boitier" in donnees else None
        contacts = valider_contacts(donnees["contacts"]) if "contacts" in donnees else None
        donnees = valider_identifiants(donnees["ssid"], donnees["mot_de_passe"],
                                      donnees["mot_de_passe"] == "")
    except OSError as erreur:
        if erreur.args and erreur.args[0] == 2:
            return False
        raise
    except (ValueError, KeyError, TypeError, AttributeError):
        print("[WIFI] Fichier de reglages invalide ; configuration locale conservee.")
        return False
    configuration.SSID = donnees["ssid"]
    configuration.MOT_DE_PASSE_WIFI = donnees["mot_de_passe"]
    if nom is not None:
        configuration.PIECE = nom
    if contacts is not None:
        configuration.DESTINATAIRES = contacts
    return True


def identite_installation(mac, chemin=FICHIER_INSTALLATION):
    try:
        with open(chemin) as fichier:
            donnees = json.load(fichier)
        cle = donnees["cle"]
        if not isinstance(cle, str) or len(cle) != 16 or any(c not in "0123456789abcdef" for c in cle):
            raise ValueError("Cle invalide")
    except (OSError, ValueError, KeyError, TypeError):
        cle = binascii.hexlify(os.urandom(8)).decode()
        ecrire_atomiquement(chemin, {"cle": cle})
    nom = "Aide-" + binascii.hexlify(mac[-3:]).decode().upper()
    return nom, cle


def decoder_url(valeur):
    sortie = bytearray()
    i = 0
    while i < len(valeur):
        octet = valeur[i]
        if octet == 37:
            if i + 2 >= len(valeur):
                raise ValueError("Encodage incomplet")
            paire = valeur[i + 1:i + 3]
            if any(c not in b"0123456789abcdefABCDEF" for c in paire):
                raise ValueError("Encodage invalide")
            sortie.append(int(paire, 16))
            i += 3
        else:
            sortie.append(32 if octet == 43 else octet)
            i += 1
    return sortie.decode("utf-8")


def decoder_formulaire(corps):
    resultat = {}
    for champ in corps.split(b"&"):
        morceaux = champ.split(b"=", 1)
        if len(morceaux) != 2:
            raise ValueError("Champ invalide")
        cle, valeur = (decoder_url(x) for x in morceaux)
        if cle in resultat:
            raise ValueError("Champ repete")
        resultat[cle] = valeur
    return resultat


def echapper(texte):
    return texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def page(token, reseaux, nom_boitier="Lit", contacts=None):
    options = "".join('<option value="%s"></option>' % echapper(nom) for nom in reseaux)
    return ('''<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Wi-Fi du boîtier</title>
<style>body{margin:0;background:#eef3f8;color:#172536;font:17px system-ui,sans-serif}main{max-width:440px;margin:32px auto;padding:26px;background:white;border-radius:18px;box-shadow:0 8px 32px #162b4212}h1{font-size:26px;margin:0 0 12px}p{line-height:1.5;color:#46586b}label{display:block;margin-top:20px;font-weight:600}input:not([type=checkbox]),button{box-sizing:border-box;width:100%;padding:13px;border-radius:9px;font:inherit}input{border:1px solid #9aabba;margin-top:7px}button{margin-top:24px;background:#165bc0;color:white;border:0;font-weight:600}button:disabled{opacity:.6}.option{font-size:15px;font-weight:400}#etat{min-height:24px;font-weight:600}@media(max-width:500px){main{margin:16px;padding:22px}}</style>
<main><h1>Connecter le boîtier</h1><p>Choisissez votre réseau Wi-Fi <strong>2,4 GHz</strong>. Vous pouvez aussi saisir son nom. Restez connecté au réseau du boîtier pendant la configuration.</p>
<form id="form" action="/wifi" method="post"><input type="hidden" name="token" value="TOKEN">
<label for="ssid">Réseau Wi-Fi</label><input id="ssid" name="ssid" list="reseaux" required maxlength="32" autocomplete="off"><datalist id="reseaux">OPTIONS</datalist>
<label for="mdp">Mot de passe Wi-Fi</label><input id="mdp" name="mot_de_passe" type="password" required minlength="8" maxlength="63" autocomplete="new-password">
<label class="option"><input id="afficher" type="checkbox"> Afficher le mot de passe</label>
<label class="option"><input id="ouvert" name="ouvert" value="1" type="checkbox"> Réseau sans mot de passe</label>
<fieldset><legend>Contacts Pushbullet</legend><p>Chaque contact actif recevra la demande. Le premier qui répond OK confirme pour tous. Jusqu’à huit contacts.</p><div id="contacts"></div><button id="ajouter" type="button">Ajouter un contact</button></fieldset>
<button id="bouton">Vérifier le Wi-Fi et tout enregistrer</button><button id="contacts-seuls" type="button">Enregistrer le nom et les contacts</button><p>Le second bouton conserve le Wi-Fi déjà enregistré.</p></form><p id="etat" role="status" aria-live="polite"></p>
<section id="suite" hidden><p id="avertissement"></p><button id="continuer" type="button">Continuer quand même</button><p>Ces réglages remplaceront les précédents. Le boîtier essaiera ce réseau au prochain démarrage ; il restera indisponible tant que la connexion manque.</p></section>
<p>Après un échec, les réglages précédents sont conservés tant que vous ne choisissez pas de continuer. Pour quitter, redémarrez le boîtier.</p></main>
<script type="application/json" id="contacts-init">CONTACTS_JSON</script>
<script>const f=document.getElementById('form'),m=document.getElementById('mdp'),b=document.getElementById('bouton'),s=document.getElementById('etat'),suite=document.getElementById('suite'),continuer=document.getElementById('continuer'),liste=document.getElementById('contacts'),contactsSeuls=document.getElementById('contacts-seuls');let suivi=false,confirmation=null;
function invalider(){confirmation=null;suite.hidden=true}
function ajouter(c={nom:'',email:'',actif:true}){if(liste.children.length>=8)return;const ligne=document.createElement('fieldset');for(const [cle,texte,type] of [['nom','Nom du contact','text'],['email','E-mail du compte Pushbullet','email'],['actif','Contact actif','checkbox']]){const label=document.createElement('label'),input=document.createElement('input');label.append(document.createTextNode(texte));input.dataset.champ=cle;input.type=type;if(type==='checkbox'){input.checked=c.actif!==false}else{input.value=c[cle]||'';input.maxLength=cle==='nom'?40:254;input.required=cle==='email';input.autocomplete=cle==='email'?'email':'off'}label.append(input);ligne.append(label)}const supprimer=document.createElement('button');supprimer.type='button';supprimer.textContent='Supprimer ce contact';supprimer.onclick=()=>{ligne.remove();invalider();document.getElementById('ajouter').disabled=false};ligne.append(supprimer);liste.append(ligne);document.getElementById('ajouter').disabled=liste.children.length>=8;invalider()}
function lireContacts(){const resultat=[],adresses=new Set();for(const ligne of liste.children){const nom=ligne.querySelector('[data-champ="nom"]'),email=ligne.querySelector('[data-champ="email"]'),actif=ligne.querySelector('[data-champ="actif"]');email.setCustomValidity('');if(!email.reportValidity())return null;const adresse=email.value.trim().toLowerCase();if(adresses.has(adresse)){email.setCustomValidity('Ce contact est déjà dans la liste.');email.reportValidity();return null}adresses.add(adresse);resultat.push({nom:nom.value,email:adresse,actif:actif.checked})}if(!resultat.some(c=>c.actif)){s.textContent='Ajoutez au moins un contact actif.';return null}return resultat}
document.getElementById('ajouter').onclick=()=>ajouter();const init=JSON.parse(document.getElementById('contacts-init').textContent);for(const c of init)ajouter(c);if(!init.length)ajouter();
contactsSeuls.onclick=async()=>{if(!document.getElementById('nom').reportValidity())return;const contacts=lireContacts();if(!contacts)return;contactsSeuls.disabled=true;b.disabled=true;invalider();try{const r=await fetch('/contacts',{method:'POST',body:new URLSearchParams({token:f.elements.token.value,nom_boitier:document.getElementById('nom').value,contacts:JSON.stringify(contacts)})});const j=await r.json();afficher(j);if(!r.ok)b.disabled=false}catch(err){s.textContent='Reconnectez-vous au boîtier pour vérifier l’enregistrement.';suivi=true}finally{contactsSeuls.disabled=false}};
function afficher(j){s.textContent=j.message;if(j.etat==='non_verifie'){suivi=false;b.disabled=false;confirmation=j.confirmation;document.getElementById('avertissement').textContent='Enregistrer « '+j.nom_boitier+' » sur le réseau « '+j.ssid+' » sans connexion vérifiée ?';suite.hidden=false}if(j.etat==='erreur'){suivi=false;b.disabled=false}if(j.etat==='ok'){suivi=false;b.disabled=true;suite.hidden=true}}
f.addEventListener('input',invalider);
document.getElementById('afficher').onchange=e=>m.type=e.target.checked?'text':'password';
document.getElementById('ouvert').onchange=e=>{m.required=!e.target.checked;m.disabled=e.target.checked;if(e.target.checked)m.value=''};
f.onsubmit=async e=>{e.preventDefault();const contacts=lireContacts();if(!contacts)return;const donnees=new URLSearchParams(new FormData(f));donnees.set('contacts',JSON.stringify(contacts));b.disabled=true;suite.hidden=true;confirmation=null;s.textContent='Connexion au Wi-Fi en cours…';try{const r=await fetch('/wifi',{method:'POST',body:donnees});const j=await r.json();s.textContent=j.message;if(!r.ok){b.disabled=false;return}suivi=true}catch(err){s.textContent='Connexion au boîtier interrompue. Reconnectez-vous à son Wi-Fi puis réessayez.';b.disabled=false}};
continuer.onclick=async()=>{continuer.disabled=true;try{const r=await fetch('/enregistrer',{method:'POST',body:new URLSearchParams({token:f.elements.token.value,confirmation:confirmation||''})});const j=await r.json();afficher(j);if(!r.ok){confirmation=null;suite.hidden=true;b.disabled=false}}catch(err){s.textContent='Réponse inconnue. Reconnectez-vous au Wi-Fi du boîtier pour vérifier l’enregistrement.';suivi=true}finally{continuer.disabled=false}};
setInterval(async()=>{if(!suivi)return;try{const r=await fetch('/etat',{cache:'no-store'});afficher(await r.json())}catch(err){s.textContent='Reconnectez-vous au Wi-Fi du boîtier pour suivre la connexion.'}},1000);
</script></html>'''.replace('id="contacts-init">CONTACTS_JSON</script>', 'id="contacts-init">%s</script>' % json.dumps(contacts or []).replace('<', '\\u003c'), 1).replace('value="TOKEN"', 'value="%s"' % token, 1).replace(
    '<label for="ssid">', '<label for="nom">Nom du boîtier</label><input id="nom" name="nom_boitier" value="%s" required maxlength="40" autocomplete="off"><label for="ssid">' % echapper(nom_boitier), 1).replace(
    '<datalist id="reseaux">OPTIONS</datalist>', '<datalist id="reseaux">%s</datalist>' % options, 1)).encode()


async def envoyer(writer, statut, corps, type_contenu="application/json; charset=utf-8", location=None):
    if isinstance(corps, dict):
        corps = json.dumps(corps).encode()
    redirection = "Location: %s\r\n" % location if location is not None else ""
    entetes = ("HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n%s"
               "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
               "Connection: close\r\n\r\n" % (statut, type_contenu, len(corps), redirection)).encode()
    writer.write(entetes + corps)
    await writer.drain()


async def lire_requete(reader):
    total = 0
    async def ligne_bornee():
        nonlocal total
        ligne = bytearray()
        while True:
            octet = await reader.read(1)
            total += len(octet)
            if total > 4096 or not octet:
                raise ValueError("Entetes invalides")
            ligne.extend(octet)
            if octet == b"\n":
                return bytes(ligne)
    ligne = await ligne_bornee()
    elements = ligne.decode("ascii").strip().split(" ")
    if len(elements) != 3 or elements[2] not in ("HTTP/1.0", "HTTP/1.1"):
        raise ValueError("Requete invalide")
    entetes = {}
    while True:
        ligne = await ligne_bornee()
        if ligne == b"\r\n":
            break
        cle, valeur = ligne.decode("ascii").split(":", 1)
        cle = cle.lower().strip()
        if cle in entetes:
            raise ValueError("Entete repete")
        entetes[cle] = valeur.strip()
    if "transfer-encoding" in entetes:
        raise ValueError("Format non pris en charge")
    longueur = int(entetes.get("content-length", "0"))
    if not 0 <= longueur <= MAX_CORPS:
        raise ValueError("Formulaire trop grand")
    corps = await reader.readexactly(longueur) if longueur else b""
    return elements[0], elements[1], entetes, corps


class Portail:
    def __init__(self, station, token=None, chemin=FICHIER_WIFI, nom_boitier="Lit", contacts=None, configuration=None):
        self.station = station
        self.token = token or binascii.hexlify(os.urandom(16)).decode()
        self.chemin = chemin
        self.etat = "repos"
        self.message = "Prêt à configurer le Wi-Fi."
        self.tache = None
        self.succes_depuis = None
        self.clients = 0
        self.connexions = 0
        self.requetes = 0
        self.erreurs = 0
        self.nom_boitier = valider_nom_boitier(nom_boitier)
        self.contacts = valider_contacts(contacts) if contacts else []
        self.configuration = configuration
        self.en_attente = None
        self.confirmation = None
        self.html = page(self.token, [], self.nom_boitier, self.contacts)

    def conserver_wifi(self):
        try:
            with open(self.chemin) as fichier:
                anciennes = json.load(fichier)
            if anciennes.get("version") != 1:
                raise ValueError("Version inconnue")
        except OSError as erreur:
            if not erreur.args or erreur.args[0] != 2:
                raise
            anciennes = {"ssid": getattr(self.configuration, "SSID", ""),
                         "mot_de_passe": getattr(self.configuration, "MOT_DE_PASSE_WIFI", "")}
        donnees = valider_identifiants(anciennes["ssid"], anciennes["mot_de_passe"], anciennes["mot_de_passe"] == "")
        donnees["connexion_verifiee"] = anciennes.get("connexion_verifiee", False)
        return donnees

    def statut(self):
        resultat = {"etat": self.etat, "message": self.message}
        if self.etat == "non_verifie" and self.en_attente is not None:
            resultat.update({"confirmation": self.confirmation,
                             "ssid": self.en_attente["ssid"],
                             "nom_boitier": self.en_attente.get("nom_boitier", self.nom_boitier)})
        return resultat

    def enregistrer(self, donnees, verifie):
        try:
            sauvegarde = dict(donnees)
            sauvegarde["connexion_verifiee"] = verifie
            ecrire_atomiquement(self.chemin, sauvegarde)
        except Exception:
            self.etat, self.message = "erreur", "Enregistrement impossible. Les réglages précédents sont conservés. Réessayez."
            self.confirmation = None
            return False
        self.etat = "ok"
        self.message = ("Réglages enregistrés, connexion vérifiée. Redémarrage du boîtier…" if verifie else
                        "Réglages enregistrés sans connexion vérifiée. Redémarrage du boîtier…")
        self.succes_depuis = time.ticks_ms()
        self.en_attente = self.confirmation = None
        return True

    async def connecter(self, donnees, delai_ms=20_000):
        self.en_attente = donnees
        self.confirmation = None
        try:
            self.station.disconnect()
            self.station.config(reconnects=0)
            self.station.connect(donnees["ssid"], donnees["mot_de_passe"])
            debut = time.ticks_ms()
            while not self.station.isconnected():
                if time.ticks_diff(time.ticks_ms(), debut) >= delai_ms:
                    raise OSError("Delai de connexion depasse")
                await asyncio.sleep(0.1)
        except Exception:
            try:
                self.station.disconnect()
            except OSError:
                pass
            self.confirmation = binascii.hexlify(os.urandom(12)).decode()
            self.etat, self.message = "non_verifie", "Connexion impossible. Vérifiez les champs ou continuez quand même pour préparer un réseau absent."
        else:
            self.enregistrer(donnees, True)

    async def traiter(self, reader, writer):
        self.clients += 1
        self.connexions += 1
        try:
            # Un navigateur peut reserver plusieurs sockets avant d'envoyer GET.
            if self.clients > 8:
                await envoyer(writer, "503 Service Unavailable", {"message": "Réessayez dans quelques secondes."})
                return
            methode, cible, entetes, corps = await asyncio.wait_for(lire_requete(reader), 5)
            self.requetes += 1
            if entetes.get("host") not in ("192.168.4.1", "192.168.4.1:80"):
                if methode == "GET":
                    # Detection Android/iOS/Windows : redirection vers l'origine locale.
                    await envoyer(writer, "302 Found", b"", location=URL_PORTAIL)
                else:
                    await envoyer(writer, "403 Forbidden", {"message": "Ouvrez http://192.168.4.1."})
            elif methode == "GET" and cible == "/":
                await envoyer(writer, "200 OK", self.html, "text/html; charset=utf-8")
            elif methode == "GET" and cible == "/etat":
                await envoyer(writer, "200 OK", self.statut())
            elif methode == "GET" and cible != "/favicon.ico":
                await envoyer(writer, "302 Found", b"", location=URL_PORTAIL)
            elif methode == "POST" and cible in ("/wifi", "/enregistrer", "/contacts"):
                if entetes.get("content-type", "").split(";")[0].strip() != "application/x-www-form-urlencoded":
                    raise ValueError("Format de formulaire invalide")
                champs = decoder_formulaire(corps)
                if champs.get("token") != self.token:
                    await envoyer(writer, "403 Forbidden", {"message": "Rechargez la page avant de réessayer."})
                    return
                if cible == "/enregistrer":
                    if (self.etat != "non_verifie" or self.en_attente is None or
                            not self.confirmation or champs.get("confirmation") != self.confirmation):
                        await envoyer(writer, "409 Conflict", {"message": "Refaites le test avant de confirmer ces réglages."})
                        return
                    succes = self.enregistrer(self.en_attente, False)
                    await envoyer(writer, "200 OK" if succes else "500 Internal Server Error", self.statut())
                    return
                if self.etat in ("connexion", "ok"):
                    await envoyer(writer, "409 Conflict", {"message": "Une connexion est déjà en cours."})
                    return
                if cible == "/contacts":
                    contacts = valider_contacts(json.loads(champs.get("contacts", "null")))
                    nom = valider_nom_boitier(champs.get("nom_boitier", self.nom_boitier))
                    try:
                        donnees = self.conserver_wifi()
                    except (OSError, ValueError, KeyError, TypeError):
                        await envoyer(writer, "400 Bad Request", {"message": "Enregistrez d’abord un réseau Wi-Fi, puis les contacts."})
                        return
                    donnees.update({"contacts": contacts, "nom_boitier": nom})
                    succes = self.enregistrer(donnees, donnees["connexion_verifiee"])
                    if succes:
                        self.message = "Nom et contacts enregistrés. Wi-Fi conservé. Redémarrage du boîtier…"
                    await envoyer(writer, "200 OK" if succes else "500 Internal Server Error", self.statut())
                    return
                donnees = valider_identifiants(champs.get("ssid"), champs.get("mot_de_passe", ""), champs.get("ouvert") == "1")
                donnees["nom_boitier"] = valider_nom_boitier(champs.get("nom_boitier", self.nom_boitier))
                if "contacts" in champs:
                    donnees["contacts"] = valider_contacts(json.loads(champs["contacts"]))
                elif self.contacts:
                    donnees["contacts"] = self.contacts
                # Envoyer l'accuse avant toute tentative qui peut changer le canal AP.
                self.etat, self.message = "connexion", "Vérification de la connexion en cours…"
                self.en_attente = self.confirmation = None
                try:
                    await envoyer(writer, "202 Accepted", {"message": self.message})
                except Exception:
                    self.etat, self.message = "erreur", "Reconnectez-vous au boîtier puis réessayez."
                    raise
                self.tache = asyncio.create_task(self.connecter(donnees))
            else:
                await envoyer(writer, "404 Not Found", {"message": "Page introuvable."})
        except (ValueError, UnicodeError):
            self.erreurs += 1
            print("[WIFI HTTP] Requete invalide ; aucun contenu journalise.")
            await envoyer(writer, "400 Bad Request", {"message": "Formulaire invalide. Vérifiez les champs et réessayez."})
        except Exception as erreur:
            self.erreurs += 1
            print("[WIFI HTTP] Echec de lecture/ecriture : %s ; aucun contenu journalise." % type(erreur).__name__)
        finally:
            self.clients -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass


async def demander_portail(configuration, voyant, gpio_bouton=12):
    from machine import Pin
    bouton = Pin(gpio_bouton, Pin.IN, Pin.PULL_UP)
    debut, maintien = time.ticks_ms(), None
    voyant.afficher(BLANC)
    print("[WIFI] Fenetre bouton principal : 4 secondes ; maintenir 3 secondes pour configurer.")
    while time.ticks_diff(time.ticks_ms(), debut) < 4000 or maintien is not None:
        maintenant = time.ticks_ms()
        if bouton.value() == 0:
            if maintien is None:
                maintien = maintenant
            elif time.ticks_diff(maintenant, maintien) >= 3000:
                print("[WIFI] Configuration demandee ; relacher le bouton principal.")
                await ouvrir_portail(configuration, voyant)
                return
        else:
            maintien = None
        await asyncio.sleep(0.01)


async def ouvrir_portail(configuration, voyant):
    import network
    import machine
    diagnostic.contexte(phase="portail_wifi")
    diagnostic.evenement("portail_ouverture")
    station = network.WLAN(network.STA_IF)
    ap = network.WLAN(network.AP_IF)
    station.active(True)
    station.disconnect()
    nom, cle = identite_installation(station.config("mac"))
    try:
        contacts = contacts_configuration(configuration)
    except ValueError:
        contacts = []  # Le portail permet de corriger une liste locale invalide.
    portail = Portail(station, nom_boitier=getattr(configuration, "PIECE", "Lit"),
                      contacts=contacts, configuration=configuration)
    try:
        noms = []
        for resultat in station.scan():
            try:
                nom_reseau = resultat[0].decode("utf-8")
                if nom_reseau and nom_reseau not in noms:
                    noms.append(nom_reseau)
            except UnicodeError:
                pass
        portail.html = page(portail.token, noms, portail.nom_boitier, portail.contacts)
    except OSError:
        pass  # Le nom d'un reseau peut toujours etre saisi a la main.
    serveur = None
    dns, tache_dns = None, None
    try:
        ap.active(True)
        ap.config(ssid=nom, key=cle, security=network.AUTH_WPA2_PSK, max_clients=2)
        ap.ifconfig(("192.168.4.1", "255.255.255.0", "192.168.4.1", "192.168.4.1"))
        try:
            dns = DNSCaptif()
            tache_dns = asyncio.create_task(dns.boucle())
        except OSError:
            print("[WIFI] DNS indisponible ; utiliser l'adresse manuelle.")
        serveur = await asyncio.start_server(portail.traiter, "192.168.4.1", 80)
        print("[WIFI] Configuration : reseau %s ; cle %s ; http://192.168.4.1" % (nom, cle))
        print("[WIFI] Mode installation : demandes d'aide indisponibles ; sortie apres 5 minutes.")
        if dns is not None:
            print("[WIFI] Portail captif : DNS et redirections HTTP actifs ; ouverture selon le telephone.")
        debut = time.ticks_ms()
        diagnostic = debut
        while time.ticks_diff(time.ticks_ms(), debut) < 300_000:
            maintenant = time.ticks_ms()
            if tache_dns is not None and tache_dns.done():
                try:
                    await tache_dns
                except Exception:
                    print("[WIFI] DNS arrete ; adresse manuelle toujours disponible.")
                tache_dns = None
            voyant.afficher(BLANC if (maintenant // 500) % 2 == 0 else (0, 0, 0))
            if time.ticks_diff(maintenant, diagnostic) >= 15_000:
                diagnostic = maintenant
                try:
                    stations = len(ap.status("stations"))
                except (OSError, ValueError):
                    stations = -1
                print("[WIFI DIAGNOSTIC] IP=%s ; telephones=%d ; DNS=%d ; TCP=%d ; HTTP=%d ; erreurs=%d" % (
                    ap.ifconfig()[0], stations, dns.requetes if dns is not None else 0,
                    portail.connexions, portail.requetes, portail.erreurs))
            if portail.succes_depuis is not None and time.ticks_diff(maintenant, portail.succes_depuis) >= 5000:
                machine.reset()
            await asyncio.sleep(0.05)
        print("[WIFI] Fin du mode installation ; reprise du programme.")
    finally:
        if tache_dns is not None:
            tache_dns.cancel()
            try:
                await tache_dns
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
        if dns is not None:
            dns.sock.close()
        if serveur is not None:
            serveur.close()
            await serveur.wait_closed()
        if portail.tache is not None and not portail.tache.done():
            portail.tache.cancel()
            try:
                await portail.tache
            except asyncio.CancelledError:
                pass
        ap.active(False)
        station.disconnect()
        diagnostic.evenement("portail_fermeture")


async def connexion_simulee(configuration):
    # Test de reconnexion Wi-Fi sans activer Pushbullet ni ralentir les boutons.
    import network
    station = network.WLAN(network.STA_IF)
    try:
        station.active(True)
        station.config(reconnects=-1)
        station.connect(configuration.SSID, configuration.MOT_DE_PASSE_WIFI)
        debut = time.ticks_ms()
        while not station.isconnected() and time.ticks_diff(time.ticks_ms(), debut) < 20_000:
            await asyncio.sleep(0.1)
        print("[WIFI] Reglages enregistres : %s ; alertes toujours simulees." % (
            "connexion et adresse IP OK" if station.isconnected() else "connexion encore en attente"))
    except OSError:
        print("[WIFI] Connexion impossible ; alertes toujours simulees.")
