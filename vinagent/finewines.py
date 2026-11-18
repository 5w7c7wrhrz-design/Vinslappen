"""Läser provningsanteckningar från forumet "Lanseringar från Systembolaget" på finewines.se.

Varje släpp har en tråd, t.ex. "Tillfälligt sortiment 20261204". Inläggen
börjar ofta med Systembolagets femsiffriga artikelnummer följt av namn, pris och
en poäng i stil med "88-90p". Det gör att anteckningarna går att koppla till rätt vin.
"""
from __future__ import annotations

import logging
import re
from datetime import date

from bs4 import BeautifulSoup

from .browser import pause

log = logging.getLogger(__name__)

BAS = "https://www.finewines.se"
FORUM = f"{BAS}/forums/lanseringar-fran-systembolaget.51/"
FORUMSIDOR = 3
MAX_TRADSIDOR = 10

TRAD_RE = re.compile(r"(Tillf[äa]lligt sortiment|Webblansering\w*)\D*(\d{8})", re.I)
NR_RAD_RE = re.compile(r"^\W*(\d{5})\b\s*(.*)$")
NR_RE = re.compile(r"(?<![\d,.])(\d{5})(?![\d,.])")
POANG_INTERVALL_RE = re.compile(r"\b(\d{2})\s*[-–]\s*(\d{2})\s*(?:p\b|poäng|/100)", re.I)
POANG_RE = re.compile(r"\b(\d{2})\s*(?:p\b|poäng|/100)", re.I)
PRIS_RE = re.compile(r"(?<![\d])(\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)\s*kr\b", re.I)
FLASKOR_RE = re.compile(r"(?<![\d])(\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)\s*flaskor", re.I)
VOLYM_RE = re.compile(r"(\d{3,4})\s*ml", re.I)
ARGANG_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")


# ---------- tolkning (rena funktioner, testas utan nätverk) ----------

def tolka_tradtitel(titel: str) -> tuple[str, date] | None:
    m = TRAD_RE.search(titel)
    if not m:
        return None
    typ = "Webblansering" if m.group(1).lower().startswith("webb") else "Tillfälligt sortiment"
    d = m.group(2)
    try:
        return typ, date(int(d[:4]), int(d[4:6]), int(d[6:]))
    except ValueError:
        return None


def tolka_poang(text: str) -> float | None:
    """'88-90p' -> 89.0, '91p' -> 91.0. Bara rimliga vinpoäng (70-100)."""
    m = POANG_INTERVALL_RE.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if 70 <= a <= b <= 100:
            return (a + b) / 2
    for m in POANG_RE.finditer(text):
        v = int(m.group(1))
        if 70 <= v <= 100:
            return float(v)
    return None


def tolka_rubrik(rad: str) -> dict:
    """'Savennières Roche aux Moines Domaine aux Moines 2023 539 kr 600 flaskor'."""
    ut: dict = {}
    pris = PRIS_RE.search(rad)
    namn = rad[:pris.start()] if pris else rad
    ut["namn"] = re.sub(r"\s+", " ", namn).strip(" -–,:")
    if pris:
        ut["pris"] = int(re.sub(r"\D", "", pris.group(1)))
    fl = FLASKOR_RE.search(rad)
    if fl:
        ut["flaskor"] = int(re.sub(r"\D", "", fl.group(1)))
    vol = VOLYM_RE.search(rad[pris.end():] if pris else "")
    if vol:
        ut["volym_ml"] = int(vol.group(1))
    ar = ARGANG_RE.findall(ut["namn"])
    if ar:
        ut["argang"] = ar[-1]
    return ut


def tolka_inlagg(text: str) -> tuple[dict[str, dict], set[str]]:
    """Delar ett inlägg i block per artikelnummer.

    Returnerar ({nr: {rubrik, text, poang}}, {nummer som bara nämns i löptext}).
    """
    block: dict[str, dict] = {}
    aktuellt: str | None = None
    for rad in text.splitlines():
        rad = rad.strip()
        if not rad:
            continue
        m = NR_RAD_RE.match(rad)
        if m:
            aktuellt = m.group(1)
            block[aktuellt] = {"rubrik": tolka_rubrik(m.group(2)), "rader": []}
            continue
        if aktuellt:
            block[aktuellt]["rader"].append(rad)
    for b in block.values():
        b["text"] = "\n".join(b.pop("rader"))
        b["poang"] = tolka_poang(b["text"])
    if not block:  # svarsinlägg: "Köpte 90180, riktigt bra!"
        return {}, set(NR_RE.findall(text))
    return block, set()


def inlagg_fran_html(html: str) -> list[dict]:
    """Inläggen i en XenForo-trådsida: författare, länk och text utan citat."""
    soup = BeautifulSoup(html, "html.parser")
    ut = []
    for art in soup.select("article.message"):
        body = art.select_one(".bbWrapper")
        if not body:
            continue
        for q in body.select("blockquote, script, .bbCodeBlock--quote"):
            q.decompose()
        for br in body.find_all("br"):
            br.replace_with("\n")
        lank = art.select_one("a[href*='/post-']") or art.select_one(".message-attribution-main a")
        ut.append({
            "forfattare": art.get("data-author") or "",
            "id": art.get("data-content") or "",
            "url": BAS + lank["href"] if lank and lank.get("href", "").startswith("/") else None,
            "text": body.get_text("\n"),
        })
    return ut


def sista_sida(html: str) -> int:
    nr = [int(x) for x in re.findall(r"/page-(\d+)", html)]
    return min(max(nr, default=1), MAX_TRADSIDOR)


def trader_fran_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    ut = []
    for a in soup.select("a[data-tp-primary='on']"):
        titel = a.get_text(strip=True)
        tolkad = tolka_tradtitel(titel)
        if tolkad:
            ut.append({"titel": titel, "typ": tolkad[0], "datum": tolkad[1],
                       "url": BAS + a["href"]})
    return ut


def sammanstall(trad: dict, inlagg: list[dict]) -> dict[str, dict]:
    """Samlar recensioner och omnämnanden per artikelnummer för en tråd."""
    ut: dict[str, dict] = {}

    def post(nr):
        return ut.setdefault(nr, {"recensioner": [], "omnamnanden": 0, "rubrik": {},
                                  "trad": {k: trad[k] for k in ("titel", "typ", "url")}
                                  | {"datum": trad["datum"].isoformat()}})

    for i in inlagg:
        block, namnda = tolka_inlagg(i["text"])
        for nr, b in block.items():
            p = post(nr)
            if not p["rubrik"]:
                p["rubrik"] = b["rubrik"]
            p["recensioner"].append({"forfattare": i["forfattare"], "poang": b["poang"],
                                     "text": b["text"], "url": i["url"] or trad["url"]})
        for nr in namnda:
            post(nr)["omnamnanden"] += 1
    return ut


# ---------- hämtning ----------

def hamta_anteckningar(ctx, fran: date) -> dict[str, dict]:
    """Anteckningar för alla släpptrådar med datum från och med `fran`."""
    page = ctx.new_page()
    resultat: dict[str, dict] = {}
    try:
        trader: list[dict] = []
        for s in range(1, FORUMSIDOR + 1):
            url = FORUM if s == 1 else f"{FORUM}page-{s}"
            page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            trader += trader_fran_html(page.content())
            pause()
        trader = [t for t in trader if t["datum"] >= fran]
        log.info("Finewines: %s släpptrådar från %s", len(trader), fran)
        for t in trader:
            page.goto(t["url"], wait_until="domcontentloaded", timeout=60_000)
            html = page.content()
            inlagg = inlagg_fran_html(html)
            for s in range(2, sista_sida(html) + 1):
                pause()
                page.goto(f"{t['url']}page-{s}", wait_until="domcontentloaded", timeout=60_000)
                inlagg += inlagg_fran_html(page.content())
            pause()
            for nr, data in sammanstall(t, inlagg).items():
                if nr in resultat:  # samma vin i flera trådar: slå ihop
                    resultat[nr]["recensioner"] += data["recensioner"]
                    resultat[nr]["omnamnanden"] += data["omnamnanden"]
                else:
                    resultat[nr] = data
    finally:
        page.close()
    return resultat
