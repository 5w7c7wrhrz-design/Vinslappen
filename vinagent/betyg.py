"""Betyg, prisvärdhet och köpförslag.

Betyget ges på 100-poängsskalan som vinskribenter använder:
- Har vinet provats på finewines.se används medelvärdet av forumets poäng.
- Annars görs en försiktig uppskattning utifrån pris, region, ålder och hur
  mycket vinet diskuteras. Uppskattningar markeras tydligt och blir aldrig köpförslag
  enbart på egen hand.
"""
from __future__ import annotations

import math
from datetime import date

PRESTIGE = [
    "bourgogne", "burgundy", "champagne", "bordeaux", "piemonte", "barolo", "barbaresco",
    "toscana", "brunello", "rhône", "rhone", "mosel", "rheingau", "nahe", "wachau",
    "rioja", "ribera del duero", "priorat", "napa", "douro", "jura", "loire", "etna",
]

BAS_POANG = 85.0
BAS_PRIS = 150.0  # kr för 75 cl


def forvantat_betyg(pris: float | None, volym_ml: float | None) -> float:
    """Vilket betyg man brukar få för pengarna (ca +2 poäng per prisfördubbling)."""
    if not pris:
        return BAS_POANG
    per_75 = pris * 750 / (volym_ml or 750)
    return BAS_POANG + 2 * math.log2(max(per_75, 60) / BAS_PRIS)


def uppskatta(vin: dict, idag: date) -> float:
    pris = vin.get("pris") or BAS_PRIS
    per_75 = pris * 750 / (vin.get("volym_ml") or 750)
    p = 84.0 + min(4.0, max(-2.0, 1.5 * math.log2(per_75 / BAS_PRIS)))
    plats = f"{vin.get('region', '')} {vin.get('land', '')}".lower()
    if any(x in plats for x in PRESTIGE):
        p += 1
    try:
        alder = idag.year - int(vin.get("argang") or 0)
        if 6 <= alder <= 40 and "rött" in (vin.get("typ") or "").lower():
            p += 0.5
    except ValueError:
        pass
    p += min(2.0, 0.5 * vin.get("omnamnanden", 0))
    return round(min(p, 90.0), 1)


def matchar_preferenser(vin: dict, pref: dict) -> list[str]:
    traffar = []
    druvor = {d.lower() for d in vin.get("druvor") or []}
    for d in pref.get("favoritdruvor") or []:
        if d.lower() in druvor or d.lower() in vin.get("namn", "").lower():
            traffar.append(d)
    plats = f"{vin.get('land', '')} {vin.get('region', '')}".lower()
    for x in (pref.get("favoritomraden") or []):
        if x.lower() in plats:
            traffar.append(x)
    for x in (pref.get("favoritproducenter") or []):
        if x.lower() in f"{vin.get('producent', '')} {vin.get('namn', '')}".lower():
            traffar.append(x)
    return traffar


def bedom(vin: dict, pref: dict, idag: date) -> dict:
    """Lägger till betyg, källa, prisvärdhet, etiketter och köpförslag på vinet."""
    poang = [r["poang"] for r in vin.get("recensioner", []) if r.get("poang")]
    if poang:
        vin["betyg"] = round(sum(poang) / len(poang), 1)
        vin["betyg_kalla"] = "finewines"
    else:
        vin["betyg"] = uppskatta(vin, idag)
        vin["betyg_kalla"] = "uppskattning"
    vin["prisvarde"] = round(vin["betyg"] - forvantat_betyg(vin.get("pris"), vin.get("volym_ml")), 1)
    vin["preferenstraffar"] = matchar_preferenser(vin, pref)

    etiketter = []
    provat = vin["betyg_kalla"] == "finewines"
    if provat and vin["betyg"] >= 92:
        etiketter.append("Toppvin")
    if provat and vin["prisvarde"] >= 3:
        etiketter.append("Fynd")
    if vin.get("flaskor") and vin["flaskor"] <= 600:
        etiketter.append("Liten upplaga")
    if vin["preferenstraffar"]:
        etiketter.append("Din stil")
    vin["etiketter"] = etiketter

    maxpris = pref.get("maxpris")
    for_dyr = bool(maxpris and vin.get("pris") and vin["pris"] > maxpris)
    min_betyg = pref.get("minbetyg_kopforslag", 89)
    kop = provat and not for_dyr and (
        vin["betyg"] >= min_betyg
        or (vin["betyg"] >= min_betyg - 1 and vin["prisvarde"] >= 3)
        or (vin["betyg"] >= min_betyg - 1 and vin["preferenstraffar"])
    )
    vin["kopforslag"] = bool(kop)
    # Sorteringsvärde: betyg, lite extra för prisvärdhet och din stil, avdrag för gissningar
    vin["rank"] = round(vin["betyg"] + 0.3 * vin["prisvarde"]
                        + (1 if vin["preferenstraffar"] else 0)
                        - (0 if provat else 3), 2)
    return vin


def begransa_kopforslag(viner: list[dict], max_per_slapp: int) -> None:
    """Behåll bara de bästa köpförslagen per släppdatum, så att listan går att använda."""
    per_datum: dict[str, list[dict]] = {}
    for v in viner:
        if v["kopforslag"]:
            per_datum.setdefault(v["lansering"], []).append(v)
    for lista in per_datum.values():
        lista.sort(key=lambda v: -v["rank"])
        for v in lista[max_per_slapp:]:
            v["kopforslag"] = False
