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

MK_FYND = ("Fynd i sin prisklass", "Mer än prisvärt")
MK_MIN = 16.5  # Munskänkarnas betyg (av 20) som räcker för köpförslag

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


def mk_som_100(mk_betyg: float) -> float:
    """Ungefärlig motsvarighet på 100-skalan, bara för sortering och för att se när
    forumet och Munskänkarna tycker olika. Visas aldrig som betyg."""
    return 85 + (mk_betyg - 14) * 2.5


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
    mk = vin.get("munskankarna") or None
    mk_fynd = bool(mk and mk.get("prisvarde") in MK_FYND)
    if provat and vin["betyg"] >= 92:
        etiketter.append("Toppvin")
    if (provat and vin["prisvarde"] >= 3) or mk_fynd:
        etiketter.append("Fynd")
    if vin.get("flaskor") and vin["flaskor"] <= 600:
        etiketter.append("Liten upplaga")
    if vin["preferenstraffar"]:
        etiketter.append("Din stil")
    vin["etiketter"] = etiketter

    maxpris = pref.get("maxpris")
    for_dyr = bool(maxpris and vin.get("pris") and vin["pris"] > maxpris)
    min_betyg = pref.get("minbetyg_kopforslag", 89)
    kop_forum = provat and (
        vin["betyg"] >= min_betyg
        or (vin["betyg"] >= min_betyg - 1 and vin["prisvarde"] >= 3)
        or (vin["betyg"] >= min_betyg - 1 and vin["preferenstraffar"])
    )
    kop_mk = bool(mk and mk["betyg"] >= pref.get("munskankarna_min", MK_MIN))
    vin["kopforslag"] = bool((kop_forum or kop_mk) and not for_dyr)
    # Sorteringsvärde: betyg, lite extra för prisvärdhet och din stil, avdrag för gissningar.
    # Viner som bara Munskänkarna provat sorteras efter deras betyg i stället för gissningen.
    grund = vin["betyg"] + 0.3 * vin["prisvarde"] if provat else (
        mk_som_100(mk["betyg"]) if mk else vin["betyg"] + 0.3 * vin["prisvarde"] - 3)
    vin["rank"] = round(grund + (1 if vin["preferenstraffar"] else 0) + (0.5 if mk_fynd else 0), 2)
    # Tycker forumet och Munskänkarna tydligt olika?
    vin["oense"] = bool(provat and mk and (
        (vin["prisvarde"] >= 3 and mk.get("prisvarde") == "Ej prisvärt")
        or (vin["prisvarde"] <= -2 and mk_fynd)
        or abs(vin["betyg"] - mk_som_100(mk["betyg"])) >= 4))
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
