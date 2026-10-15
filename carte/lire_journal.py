"""Recuperer les seuls diagnostics via mpremote, puis redemarrer la carte.

MicroPico doit etre deconnecte. La lecture interrompt le programme et efface
sa demande en RAM au redemarrage ; elle ne supprime pas les journaux embarques.
Utiliser --hors-ligne DOSSIER pour relire un export sans toucher a la carte.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

FICHIERS = ("diagnostic.jsonl.1", "diagnostic.jsonl")


def lire_entrees(repertoire):
    entrees, invalides = [], 0
    for nom in FICHIERS:
        chemin = Path(repertoire) / nom
        if not chemin.exists():
            continue
        for ligne in chemin.read_text(encoding="utf-8", errors="replace").splitlines():
            if not ligne.strip():
                continue
            try:
                entree = json.loads(ligne)
                if not isinstance(entree, dict):
                    raise ValueError()
                entrees.append(entree)
            except ValueError:
                invalides += 1
    return entrees, invalides


def bilan(entrees):
    demarrages = [e for e in entrees if e.get("evenement") == "demarrage"]
    wdt = [e for e in demarrages if e.get("cause") == "WDT_RESET"]
    essais = [e for e in wdt if (e.get("precedent") or {}).get("essai")]
    debug = [e for e in wdt if e not in essais and (e.get("precedent") or {}).get("phase") == "arret_manuel"]
    incidents = [e for e in wdt if e not in essais and e not in debug]
    dates = [e["utc"] for e in entrees if isinstance(e.get("utc"), str)]
    return {"demarrages": len(demarrages), "watchdogs": len(incidents), "essais": len(essais), "debug": len(debug),
            "du": min(dates) if dates else None, "au": max(dates) if dates else None,
            "dernier_incident": incidents[-1] if incidents else None}


def commande(port, *args):
    return subprocess.run([sys.executable, "-m", "mpremote", "connect", port,
                           "resume", *args], capture_output=True, text=True, timeout=25)


def recuperer(port, destination):
    try:
        for nom in FICHIERS:
            for tentative in range(2):
                resultat = commande(port, "fs", "cp", ":" + nom, str(destination / nom))
                if resultat.returncode == 0:
                    break
                erreurs = resultat.stdout + resultat.stderr
                if ("ENOENT" in erreurs or "[Errno 2]" in erreurs or
                        (nom in erreurs and "No such file or directory" in erreurs)):
                    break  # Premiere generation absente au debut : normal.
                if tentative:
                    raise RuntimeError("Lecture impossible sur %s ; deconnecter MicroPico puis reessayer." % port)
    finally:
        # Ne pas laisser la carte au REPL apres lecture. Le watchdog reste arme.
        try:
            retour = commande(port, "reset")
            if retour.returncode:
                print("Redemarrage non confirme : appuyer sur RESET, boutons relaches.")
        except (OSError, subprocess.TimeoutExpired):
            print("Redemarrage non confirme : appuyer sur RESET, boutons relaches.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--hors-ligne", type=Path)
    args = parser.parse_args()
    if args.hors_ligne:
        destination = args.hors_ligne
    else:
        destination = Path(__file__).resolve().parent.parent / "logs" / (
            "diagnostic-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ"))
        destination.mkdir(parents=True)
        recuperer(args.port, destination)
    entrees, invalides = lire_entrees(destination)
    if not entrees:
        raise SystemExit("Aucun evenement lisible dans %s" % destination)
    resume = bilan(entrees)
    print("Export :", destination)
    print("Historique conserve : %d demarrages ; %d resets watchdog hors essais/arrets manuels ; %d essais ; %d arrets manuels." % (
        resume["demarrages"], resume["watchdogs"], resume["essais"], resume["debug"]))
    if resume["du"]:
        print("Evenements dates UTC : %s a %s" % (resume["du"], resume["au"]))
    if resume["dernier_incident"]:
        precedent = resume["dernier_incident"].get("precedent") or {}
        print("Dernier watchdog : derniere activite a %s s ; etat=%s ; phase=%s" % (
            precedent.get("secondes", "?"), precedent.get("etat", "?"), precedent.get("phase", "?")))
    if invalides:
        print("Lignes incompletes ou invalides ignorees :", invalides)


if __name__ == "__main__":
    main()
