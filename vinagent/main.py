"""Kör hela flödet: hämta släpp, hämta anteckningar, betygsätt och bygg webbsidan."""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import betyg, finewines, munskankarna, systembolaget
from .browser import browser
from .sida import bygg_sida

log = logging.getLogger("vinagent")
ROT = Path(__file__).resolve().parent
TZ = ZoneInfo("Europe/Stockholm")


def las_preferenser(sokvag: Path) -> dict:
    try:
        return json.loads(sokvag.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def sok_url_sb(nr: str) -> str:
    return f"https://www.systembolaget.se/sok/?textQuery={nr}"


def koppla_munskankarna(viner: list[dict], mk: dict[str, dict]) -> None:
    """Munskänkarnas betyg via Systembolagets artikelnummer (sju siffror, eller de fem
    första för viner som bara finns i forumet än)."""
    kort = {}
    for nr, data in mk.items():
        kort.setdefault(nr[:5], data)
    for v in viner:
        v["munskankarna"] = mk.get(v.get("artikelnr") or "") or (None if v.get("artikelnr") else kort.get(v["nr"]))


def slå_ihop(sb_viner: list[dict], anteckningar: dict[str, dict], fran: date, till: date) -> list[dict]:
    viner = []
    sedda = set()
    for v in sb_viner:
        a = anteckningar.get(v["nr"])
        v["recensioner"] = a["recensioner"] if a else []
        v["omnamnanden"] = a["omnamnanden"] if a else 0
        v["trad"] = a["trad"] if a else None
        if a and a["rubrik"].get("flaskor"):
            v["flaskor"] = a["rubrik"]["flaskor"]
        viner.append(v)
        sedda.add(v["nr"])
    # Viner som forumet redan provat men som Systembolaget inte visar ännu
    for nr, a in anteckningar.items():
        if nr in sedda or not a["recensioner"]:
            continue
        d = date.fromisoformat(a["trad"]["datum"])
        if not (fran <= d <= till):
            continue
        r = a["rubrik"]
        viner.append({
            "nr": nr, "artikelnr": "", "namn": r.get("namn") or f"Artikel {nr}", "producent": "",
            "lansering": a["trad"]["datum"], "sortiment": a["trad"]["typ"],
            "webblansering": a["trad"]["typ"] == "Webblansering", "pris": r.get("pris"),
            "volym_ml": r.get("volym_ml", 750), "alkohol": None, "land": "",
            "region": "", "typ": "", "stil": "", "druvor": [], "argang": r.get("argang", ""),
            "smak": "", "doft": "", "passar_till": [], "eko": False, "bild": None,
            "url": sok_url_sb(nr), "kalla": "finewines", "flaskor": r.get("flaskor"),
            "recensioner": a["recensioner"], "omnamnanden": a["omnamnanden"], "trad": a["trad"],
        })
    return viner


def kor(dagar_fram: int, dagar_bak: int, ut: Path, pref_fil: Path) -> list[dict]:
    idag = datetime.now(TZ).date()
    fran, till = idag - timedelta(days=dagar_bak), idag + timedelta(days=dagar_fram)
    pref = las_preferenser(pref_fil)
    with browser() as ctx:
        sb = systembolaget.hamta_slapp(ctx, fran, till)
        log.info("Systembolaget: %s viner %s–%s", len(sb), fran, till)
        try:
            anteckningar = finewines.hamta_anteckningar(ctx, fran - timedelta(days=14))
        except Exception:  # forumet nere ska inte stoppa listan
            log.exception("Kunde inte läsa finewines.se, fortsätter utan anteckningar")
            anteckningar = {}
        log.info("Finewines: anteckningar om %s artikelnummer", len(anteckningar))
        try:
            mk = munskankarna.hamta(ctx, fran, till)
        except Exception:  # Munskänkarna nere ska inte stoppa listan
            log.exception("Kunde inte läsa Munskänkarna, fortsätter utan deras betyg")
            mk = {}
        log.info("Munskänkarna: betyg på %s viner", len(mk))
    alla = slå_ihop(sb, anteckningar, fran, till)
    koppla_munskankarna(alla, mk)
    viner = [betyg.bedom(v, pref, idag) for v in alla]
    betyg.begransa_kopforslag(viner, pref.get("max_kopforslag_per_slapp", 6))
    ut.mkdir(parents=True, exist_ok=True)
    (ut / "viner.json").write_text(json.dumps(viner, ensure_ascii=False, indent=1), encoding="utf-8")
    (ut / "index.html").write_text(bygg_sida(viner, idag, datetime.now(TZ), pref), encoding="utf-8")
    log.info("Klart: %s viner, %s köpförslag -> %s", len(viner),
             sum(v["kopforslag"] for v in viner), ut / "index.html")
    return viner


def main(argv=None):
    ap = argparse.ArgumentParser(description="Vinagent för Systembolagets släpp")
    ap.add_argument("--dagar", type=int, default=60, help="hur många dagar framåt (60)")
    ap.add_argument("--bakat", type=int, default=7, help="ta med släpp så här många dagar bakåt (7)")
    ap.add_argument("--ut", type=Path, default=Path("site"), help="mapp för webbsidan (site)")
    ap.add_argument("--preferenser", type=Path, default=ROT / "preferenser.json")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    kor(a.dagar, a.bakat, a.ut, a.preferenser)
