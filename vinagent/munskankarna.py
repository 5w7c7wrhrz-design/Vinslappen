"""Läser Munskänkarnas provningar av Systembolagets släpp (vindatabasen Vinlocus).

Munskänkarna provar tillfälligt sortiment per släpp ("tillfalligt-sortiment-27-november-2026")
och gör hitlistor. (Deras "webbviner" är importörernas egna webbutiker utan artikelnummer
hos Systembolaget, så de tas inte med.) Varje vin har betyg
av 20, prisvärdhet, en skriven bedömning och Systembolagets artikelnummer, så det
går att koppla till rätt vin.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from .browser import pause

log = logging.getLogger(__name__)

BAS = "https://www.munskankarna.se"
SITEMAP = f"{BAS}/sv/vinlocus/sitemap-vinlocus-activity"
MANADER = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti",
           "september", "oktober", "november", "december"]
PROVNING_RE = re.compile(
    r"/sv/vinlocus/(?P<typ>tillfalligt-sortiment|hitlista)-"
    r"(?:(?P<dag>\d{1,2})-)?(?P<manad>[a-zåäö]+)-(?P<ar>\d{4})/?$")
PRISVARDE = ["Ej prisvärt", "Prisvärt", "Mer än prisvärt", "Fynd i sin prisklass"]


def tolka_provning(url: str) -> dict | None:
    """'…/tillfalligt-sortiment-27-november-2026' -> typ, datum eller månad."""
    m = PROVNING_RE.search(url)
    if not m or m.group("manad") not in MANADER:
        return None
    ar, manad = int(m.group("ar")), MANADER.index(m.group("manad")) + 1
    dag = int(m.group("dag")) if m.group("dag") else None
    try:
        start = date(ar, manad, dag or 1)
    except ValueError:
        return None
    slut = start if dag else (date(ar + (manad == 12), manad % 12 + 1, 1))
    return {"url": url, "typ": m.group("typ"), "start": start, "slut": slut, "hel_manad": dag is None}


def tal(text: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)?", text or "")
    return float(m.group(0).replace(",", ".")) if m else None


def tolka_lista(html: str, provning_url: str = "") -> dict[str, dict]:
    """Alla vinkort på en provningssida, nycklade på Systembolagets artikelnummer."""
    soup = BeautifulSoup(html, "html.parser")
    ut: dict[str, dict] = {}
    for kort in soup.select("li.groupedlist"):
        text = re.sub(r"\s+", " ", kort.get_text(" ")).strip()
        nr = re.search(r"Systembolaget:\s*(\d{5,8})", text)
        poang = kort.select_one(".wine-points")
        if not nr or not poang:
            continue
        betyg = tal(poang.get_text())
        if betyg is None or not 0 < betyg <= 20:
            continue
        pv_el = kort.select_one(".c-wine-info__stat span")
        pv = pv_el.get_text(strip=True) if pv_el else None
        if pv and pv.startswith("Ett fynd"):
            pv = "Fynd i sin prisklass"
        bedomning = text.split(nr.group(0), 1)[1].split("Druvor:", 1)[0].strip()
        lank = kort.select_one("h3 a[href]") or kort.select_one("a[href*='/sv/vinlocus/']")
        href = lank["href"] if lank else provning_url
        ut[nr.group(1)] = {
            "betyg": betyg,
            "prisvarde": pv if pv in PRISVARDE else None,
            "typisk": kort.select_one(".c-wine-info__typical") is not None,
            "text": bedomning,
            "namn": lank.get_text(strip=True) if lank else "",
            "url": href if href.startswith("http") else BAS + href,
            "provning": provning_url,
        }
    return ut


def hamta(ctx, fran: date, till: date) -> dict[str, dict]:
    """Munskänkarnas betyg för viner i provningar som rör släpp mellan fran och till."""
    page = ctx.new_page()
    try:
        return _hamta(page, fran, till)
    finally:
        page.close()


def _text(page, url: str) -> str | None:
    try:
        svar = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    except Exception as e:  # noqa: BLE001 - t.ex. en provning som inte är publicerad än
        log.warning("Munskänkarna: kunde inte läsa %s (%s)", url, str(e).splitlines()[0])
        return None
    if not svar or not svar.ok:
        log.warning("Munskänkarna: %s svarade %s", url, svar.status if svar else "inget")
        return None
    return svar.text()


def _hamta(page, fran: date, till: date) -> dict[str, dict]:
    sitemap = _text(page, SITEMAP)
    if sitemap is None:
        raise RuntimeError("kunde inte läsa Munskänkarnas sitemap")
    urls = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap)
    provningar = [p for p in (tolka_provning(u) for u in urls) if p]
    # släppdagar kan skilja ett par dagar mellan Munskänkarna och Systembolaget
    aktuella = [p for p in provningar if p["slut"] >= fran.replace(day=1) and p["start"] <= till]
    # specifika provningar först, hitlistor sist (de upprepar samma bedömningar)
    aktuella.sort(key=lambda p: (p["typ"] == "hitlista", p["start"]))
    log.info("Munskänkarna: %s provningar i perioden", len(aktuella))
    ut: dict[str, dict] = {}
    for p in aktuella:
        pause()
        html = _text(page, p["url"])
        if html is None:
            continue
        for nr, data in tolka_lista(html, p["url"]).items():
            ut.setdefault(nr, data)
    return ut
