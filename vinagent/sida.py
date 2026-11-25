"""Bygger webbsidan (en enda HTML-fil) från de betygsatta vinerna."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from urllib.parse import quote_plus

from jinja2 import Environment, PackageLoader, select_autoescape

MANADER = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti",
           "september", "oktober", "november", "december"]
DAGAR = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]

env = Environment(loader=PackageLoader("vinagent", "mallar"),
                  autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)


def svenskt_datum(d: date) -> str:
    return f"{DAGAR[d.weekday()]} {d.day} {MANADER[d.month - 1]}"


def kr(v) -> str:
    if v is None:
        return "–"
    v = float(v)
    s = f"{v:,.0f}" if v.is_integer() else f"{v:,.2f}"
    return s.replace(",", " ").replace(".", ",") + " kr"


def poang(v) -> str:
    return f"{v:.1f}".replace(".0", "").replace(".", ",")


def typklass(vin: dict) -> str:
    t = (vin.get("typ") or "").lower()
    for nyckel, klass in [("rött", "rott"), ("vitt", "vitt"), ("rosé", "rose"),
                          ("mousserande", "bubbel"), ("sött", "sott"), ("starkvin", "sott")]:
        if nyckel in t:
            return klass
    return "ovrigt"


env.filters.update(kr=kr, poang=poang, quote=quote_plus)
env.globals.update(typklass=typklass)


def bygg_sida(viner: list[dict], idag: date, nu: datetime, pref: dict, fragment: bool = False) -> str:
    per_datum: dict[str, list[dict]] = defaultdict(list)
    for v in viner:
        per_datum[v["lansering"]].append(v)
    slapp = []
    for d in sorted(per_datum):
        lista = sorted(per_datum[d], key=lambda v: -v["rank"])
        dd = date.fromisoformat(d)
        typer = sorted({v["sortiment"] for v in lista if v["sortiment"]})
        slapp.append({
            "datum": d, "rubrik": svenskt_datum(dd), "viner": lista, "typer": typer,
            "passerat": dd < idag, "dagar_kvar": (dd - idag).days,
            "provade": sum(v["betyg_kalla"] == "finewines" for v in lista),
            "kop": sum(v["kopforslag"] for v in lista),
            "mk": sum(1 for v in lista if v.get("munskankarna")),
        })
    kop = sorted([v for v in viner if v["kopforslag"] and v["lansering"] >= idag.isoformat()],
                 key=lambda v: (v["lansering"], -v["rank"]))
    kommande = next((s for s in slapp if not s["passerat"]), None)
    typer = sorted({typklass(v) for v in viner})
    druvraknare: dict[str, int] = defaultdict(int)
    visning: dict[str, str] = {}
    for d in pref.get("favoritdruvor") or []:
        druvraknare[d.lower()] += 1000  # dina favoriter först
        visning.setdefault(d.lower(), d)
    for v in viner:
        for d in v.get("druvor") or []:
            druvraknare[d.lower()] += 1
            visning.setdefault(d.lower(), d)
    vanliga_druvor = [visning[k] for k in sorted(druvraknare, key=lambda k: -druvraknare[k])[:24]]
    return env.get_template("sida.html").render(
        slapp=slapp, kop=kop, kommande=kommande, antal=len(viner), pref=pref, typer=typer,
        provade=sum(v["betyg_kalla"] == "finewines" for v in viner),
        mk_antal=sum(1 for v in viner if v.get("munskankarna")),
        vanliga_druvor=vanliga_druvor, idag=idag.isoformat(),
        uppdaterad=f"{nu.day} {MANADER[nu.month - 1]} {nu:%H:%M}", fragment=fragment,
        svenskt_datum=lambda s: svenskt_datum(date.fromisoformat(s)),
    )
