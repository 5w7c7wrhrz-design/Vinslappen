"""Hämtar kommande vinsläpp från systembolaget.se.

Sortimentssidan laddar produkterna själv när den visas i webbläsaren. Vi öppnar
samma sida som en besökare och läser produktlistan som sidan tar emot.
"""
from __future__ import annotations

import logging
from datetime import date
from urllib.parse import quote_plus

from .browser import felsok, pause

log = logging.getLogger(__name__)

SORTIMENT = ["Tillfälligt sortiment", "Webblanseringar"]
BAS = "https://www.systembolaget.se"
MAX_SIDOR = 40
VANTA_MS = 60_000
KATEGORIER = ["rott-vin", "vitt-vin", "mousserande-vin", "rosevin"]


def sok_url(fran: date, till: date, sida: int = 1, kategori: str = "") -> str:
    sortiment = quote_plus("_eller_".join(SORTIMENT))
    url = (f"{BAS}/sortiment/vin/{kategori + '/' if kategori else ''}?sortiment={sortiment}"
           f"&saljstart-fran={fran.isoformat()}&saljstart-till={till.isoformat()}")
    if sida > 1:
        url += f"&p={sida}"
    return url


def produkt_url(p: dict) -> str:
    return f"{BAS}/produkt/vin/{p['productNumber']}/"


def normalisera(p: dict) -> dict:
    """Plockar ut det vi behöver ur Systembolagets produktpost."""
    namn = " ".join(x for x in [p.get("productNameBold"), p.get("productNameThin")] if x)
    bild = None
    if p.get("images"):
        # Basadress; storlek och format läggs till i mallen, t.ex. "_100.webp"
        bild = p["images"][0].get("imageUrl") or None
    return {
        "nr": p.get("productNumberShort") or "",
        "artikelnr": p.get("productNumber") or "",
        "namn": namn,
        "producent": p.get("producerName") or "",
        "lansering": (p.get("productLaunchDate") or "")[:10],
        "sortiment": p.get("assortmentText") or "",
        "webblansering": bool(p.get("isWebLaunch")),
        "pris": p.get("price"),
        "volym_ml": p.get("volume"),
        "alkohol": p.get("alcoholPercentage"),
        "land": p.get("country") or "",
        "region": ", ".join(x for x in [p.get("originLevel1"), p.get("originLevel2")] if x),
        "typ": p.get("categoryLevel2") or "",
        "stil": p.get("categoryLevel3") or "",
        "druvor": p.get("grapes") or [],
        "argang": p.get("vintage") or "",
        "smak": (p.get("taste") or "").strip(),
        "doft": (p.get("aroma") or "").strip(),
        "passar_till": p.get("tasteSymbolsList") or [],
        "eko": bool(p.get("isOrganic")),
        "bild": bild,
        "url": produkt_url(p),
        "kalla": "systembolaget",
    }


class SystembolagetFel(RuntimeError):
    pass


class _Sokare:
    """Öppnar sortimentssidor och fångar produktlistan som sidan laddar."""

    def __init__(self, ctx):
        self.page = ctx.new_page()

    def _ladda(self, url: str) -> dict:
        """Öppnar sidan och väntar bara på produktlistan (inte på att all trafik tystnat)."""
        senaste_fel: Exception | None = None
        for forsok in (1, 2):
            try:
                with self.page.expect_response(
                    lambda r: "productsearch/search" in r.url and r.request.method == "GET",
                    timeout=VANTA_MS,
                ) as info:
                    self.page.goto(url, wait_until="domcontentloaded", timeout=VANTA_MS)
                svar = info.value
                if svar.status != 200:
                    raise SystembolagetFel(f"produktsökningen svarade {svar.status}")
                return svar.json()
            except Exception as e:  # noqa: BLE001
                senaste_fel = e
                log.warning("Systembolaget: försök %s misslyckades för %s: %s", forsok, url, e)
                pause()
        felsok(self.page, "systembolaget")
        raise SystembolagetFel(f"kunde inte läsa {url}: {senaste_fel}")

    def sok(self, fran: date, till: date, kategori: str = "") -> tuple[dict[str, dict], int]:
        """Alla sidor för en sökning. Returnerar (produkter, antal enligt Systembolaget)."""
        produkter: dict[str, dict] = {}
        totalt = 0
        for sida in range(1, MAX_SIDOR + 1):
            data = self._ladda(sok_url(fran, till, sida, kategori))
            pause()
            for p in data.get("products") or []:
                if p.get("categoryLevel1") == "Vin":
                    produkter[p["productNumber"]] = p
            meta = data.get("metadata") or {}
            totalt = meta.get("docCount") or 0
            if meta.get("nextPage", -1) in (-1, None):
                break
        return produkter, totalt

    def stang(self):
        self.page.close()


def hamta_slapp(ctx, fran: date, till: date) -> list[dict]:
    """Alla viner i tillfälligt sortiment och webblanseringar med säljstart i intervallet.

    Sökningen sorteras inte stabilt mellan sidor, så vi delar upp den per släppdatum
    och, när ett släpp är större än en sida, per vintyp.
    """
    s = _Sokare(ctx)
    try:
        alla, totalt = s.sok(fran, till)
        datum = sorted({p["productLaunchDate"][:10] for p in alla.values() if p.get("productLaunchDate")})
        log.info("Systembolaget: %s släppdatum, %s viner enligt sökningen", len(datum), totalt)
        for d in datum:
            dag = date.fromisoformat(d)
            try:
                hittade, antal = s.sok(dag, dag)
                alla.update(hittade)
                if len(hittade) < antal:
                    for kat in KATEGORIER:
                        alla.update(s.sok(dag, dag, kat)[0])
            except SystembolagetFel as e:
                log.warning("Systembolaget %s: hoppar över kompletteringen (%s)", d, e)
            log.info("Systembolaget %s: %s viner", d,
                     sum(1 for p in alla.values() if p.get("productLaunchDate", "")[:10] == d))
        if len(alla) < totalt:
            log.warning("Systembolaget: fick %s av %s viner", len(alla), totalt)
    finally:
        s.stang()
    return [normalisera(p) for p in alla.values()]
