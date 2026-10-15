"""Liste privee de contacts commune au portail et au transport MicroPython."""
MAX_CONTACTS = 8


def valider_contacts(contacts):
    if not isinstance(contacts, list) or not 1 <= len(contacts) <= MAX_CONTACTS:
        raise ValueError("Prevoir de 1 a 8 contacts, dont au moins un actif.")
    resultat, adresses = [], set()
    for contact in contacts:
        if not isinstance(contact, dict):
            raise ValueError("Contact invalide.")
        email, nom, actif = contact.get("email"), contact.get("nom", ""), contact.get("actif", True)
        if not isinstance(email, str) or not isinstance(nom, str) or not isinstance(actif, bool):
            raise ValueError("Contact invalide.")
        email, nom = email.strip().lower(), nom.strip()
        morceaux = email.split("@")
        if (not 3 <= len(email) <= 254 or len(morceaux) != 2 or not all(morceaux) or
                any(ord(c) < 33 or ord(c) > 126 or c in '<>,;"\\' for c in email)):
            raise ValueError("Adresse du compte Pushbullet invalide.")
        if len(nom) > 40 or any(ord(c) < 32 or ord(c) == 127 for c in nom):
            raise ValueError("Nom de contact invalide (40 caracteres maximum).")
        if email in adresses:
            raise ValueError("Un contact ne doit apparaitre qu'une fois.")
        adresses.add(email)
        resultat.append({"nom": nom or email.split("@", 1)[0], "email": email, "actif": actif})
    if not any(c["actif"] for c in resultat):
        raise ValueError("Activer au moins un contact.")
    return resultat


def contacts_configuration(configuration):
    liste = getattr(configuration, "DESTINATAIRES", None)
    if liste:
        return valider_contacts(liste)
    email = getattr(configuration, "DESTINATAIRE_EMAIL", "")
    if email:
        return valider_contacts([{"nom": "Contact", "email": email, "actif": True}])
    return []
