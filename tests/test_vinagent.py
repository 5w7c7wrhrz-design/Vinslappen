from datetime import date

from vinagent import betyg, finewines
from vinagent.main import slå_ihop
from vinagent.sida import bygg_sida
from vinagent.systembolaget import normalisera, sok_url

INLAGG = """Här kommer mina anteckningar från provningen av släppet den 13 november.
90180 Savennières Roche aux Moines Domaine aux Moines 2023 539 kr 600 flaskor
N: Hyacint, tulpan, jasmin, melon och rökt korv.
M: Melon, pomerans, tulpan. Elegant med tung fet frukt och fin syra. 90-92p
95631 Blanc de Noirs Millésime Philippe Fourrier 2018 919 kr 240 flaskor (1500 ml)
N: Syren, citronzest.
M: Citron, röda äpplen. Blommigt och mycket ungt. 88-90p
93081 Côte de Brouilly Cuvée Mélanie Domaine Daniel Bouland 2025 239 kr 840 flaskor
M: Blåbär, hallon. Fräscht med snygg balans.
"""

TRADSIDA = """<html><body>
<article class="message" data-author="Patrik" data-content="post-1">
 <a href="/threads/x.1/post-1">#1</a>
 <div class="bbWrapper">90180 Savennières Domaine aux Moines 2023 539 kr<br>M: Fint. 91p</div>
</article>
<article class="message" data-author="Anna" data-content="post-2">
 <div class="bbWrapper"><blockquote>90180 citat 70p</blockquote>Köpte 90180 och 93081 direkt!</div>
</article>
</body></html>"""


def test_tolka_poang():
    assert finewines.tolka_poang("Elegant. 90-92p") == 91
    assert finewines.tolka_poang("Snyggt 89 – 91 p") == 90
    assert finewines.tolka_poang("Ger det 93p") == 93
    assert finewines.tolka_poang("Kostar 239 kr, 2025") is None
    assert finewines.tolka_poang("12p") is None


def test_tolka_rubrik_skiljer_argang_och_pris():
    r = finewines.tolka_rubrik("De Saint-Gall Blanc de Blancs Grand Cru Brut 2019 579 kr 1 200 flaskor")
    assert r == {"namn": "De Saint-Gall Blanc de Blancs Grand Cru Brut 2019", "pris": 579,
                 "flaskor": 1200, "argang": "2019"}
    assert finewines.tolka_rubrik("Sassicaia 2023 3 499 kr")["pris"] == 3499
    assert finewines.tolka_rubrik("Fourrier 2018 919 kr 240 flaskor (1500 ml)")["volym_ml"] == 1500


def test_tolka_inlagg_delar_per_artikelnummer():
    block, namnda = finewines.tolka_inlagg(INLAGG)
    assert set(block) == {"90180", "95631", "93081"}
    assert block["90180"]["poang"] == 91
    assert block["90180"]["rubrik"]["pris"] == 539
    assert block["93081"]["poang"] is None
    assert "Hyacint" in block["90180"]["text"]
    assert namnda == set()


def test_tradtitel():
    assert finewines.tolka_tradtitel("Tillfälligt sortiment 20261204") == (
        "Tillfälligt sortiment", date(2026, 12, 4))
    assert finewines.tolka_tradtitel("Webblansering 20261126") == ("Webblansering", date(2026, 11, 26))
    assert finewines.tolka_tradtitel("Kortare tid att hämta ut beställningar") is None


def test_inlagg_fran_html_hoppar_over_citat_och_raknar_omnamnanden():
    inlagg = finewines.inlagg_fran_html(TRADSIDA)
    assert [i["forfattare"] for i in inlagg] == ["Patrik", "Anna"]
    assert "citat" not in inlagg[1]["text"]
    trad = {"titel": "Tillfälligt sortiment 20261113", "typ": "Tillfälligt sortiment",
            "datum": date(2026, 11, 13), "url": "https://www.finewines.se/threads/x.1/"}
    res = finewines.sammanstall(trad, inlagg)
    assert res["90180"]["recensioner"][0]["poang"] == 91
    assert res["90180"]["omnamnanden"] == 1
    assert res["93081"]["omnamnanden"] == 1
    assert res["93081"]["recensioner"] == []


SB_PRODUKT = {
    "productNumber": "9018001", "productNumberShort": "90180",
    "productNameBold": "Savennières Roche aux Moines", "productNameThin": "Domaine aux Moines",
    "producerName": "Domaine aux Moines", "productLaunchDate": "2026-11-13T00:00:00",
    "assortmentText": "Tillfälligt sortiment", "isWebLaunch": False, "price": 539, "volume": 750,
    "alcoholPercentage": 13.5, "country": "Frankrike", "originLevel1": "Loire",
    "originLevel2": "Anjou-Saumur", "categoryLevel1": "Vin", "categoryLevel2": "Vitt vin",
    "categoryLevel3": "Fruktigt & Smakrikt", "grapes": ["Chenin Blanc"], "vintage": "2023",
    "taste": "Fruktig smak.", "tasteSymbolsList": ["Fisk"], "isOrganic": False,
    "images": [{"imageUrl": "https://product-cdn.systembolaget.se/productimages/1/1"}],
}


def test_sok_url():
    url = sok_url(date(2026, 12, 3), date(2026, 12, 3), 2, "rott-vin")
    assert url.startswith("https://www.systembolaget.se/sortiment/vin/rott-vin/?sortiment=")
    assert "Tillf%C3%A4lligt+sortiment_eller_Webblanseringar" in url
    assert url.endswith("saljstart-fran=2026-12-03&saljstart-till=2026-12-03&p=2")


def _viner():
    block, _ = finewines.tolka_inlagg(INLAGG)
    trad = {"titel": "Tillfälligt sortiment 20261113", "typ": "Tillfälligt sortiment",
            "datum": date(2026, 11, 13), "url": "https://www.finewines.se/threads/x.1/"}
    anteckningar = finewines.sammanstall(trad, [{"forfattare": "Patrik", "url": None, "text": INLAGG}])
    sb = [normalisera(SB_PRODUKT)]
    return slå_ihop(sb, anteckningar, date(2026, 11, 1), date(2026, 12, 31)), block


def test_sla_ihop_kopplar_forum_och_lagger_till_forumviner():
    viner, _ = _viner()
    per_nr = {v["nr"]: v for v in viner}
    assert per_nr["90180"]["kalla"] == "systembolaget"
    assert per_nr["90180"]["flaskor"] == 600
    assert per_nr["90180"]["recensioner"][0]["poang"] == 91
    assert per_nr["90180"]["bild"] == "https://product-cdn.systembolaget.se/productimages/1/1"
    assert per_nr["95631"]["kalla"] == "finewines"   # inte hos Systembolaget ännu
    assert per_nr["95631"]["volym_ml"] == 1500
    assert per_nr["95631"]["pris"] == 919


def test_betyg_och_kopforslag():
    viner, _ = _viner()
    pref = {"favoritdruvor": ["Chenin Blanc"], "maxpris": 800, "minbetyg_kopforslag": 90}
    idag = date(2026, 11, 10)
    bedomda = {v["nr"]: betyg.bedom(v, pref, idag) for v in viner}
    sav = bedomda["90180"]
    assert sav["betyg"] == 91 and sav["betyg_kalla"] == "finewines"
    assert sav["kopforslag"]
    assert "Din stil" in sav["etiketter"]
    # för dyr enligt maxpris
    assert not bedomda["95631"]["kopforslag"]


def test_uppskattning_blir_aldrig_kopforslag():
    v = normalisera(SB_PRODUKT | {"productNumberShort": "11111", "price": 2000})
    v.update(recensioner=[], omnamnanden=5)
    b = betyg.bedom(v, {"minbetyg_kopforslag": 80}, date(2026, 11, 10))
    assert b["betyg_kalla"] == "uppskattning"
    assert b["betyg"] <= 90
    assert not b["kopforslag"]


def test_begransa_kopforslag():
    viner = [{"lansering": "2026-12-04", "kopforslag": True, "rank": r} for r in range(10)]
    betyg.begransa_kopforslag(viner, 3)
    assert [v["rank"] for v in viner if v["kopforslag"]] == [7, 8, 9]


def test_bygg_sida():
    from datetime import datetime
    viner, _ = _viner()
    pref = {"minbetyg_kopforslag": 90}
    viner = [betyg.bedom(v, pref, date(2026, 11, 10)) for v in viner]
    html = bygg_sida(viner, date(2026, 11, 10), datetime(2026, 11, 10, 8, 0), pref)
    assert html.startswith("<!doctype html>")
    assert "Savennières Roche aux Moines" in html
    assert "fredag 13 november" in html.lower()
    assert "Köpförslag" in html
    assert '<option value="2026-11-13">Fredag 13 november' in html
    assert 'id="f-sort"' in html
    assert 'id="instl"' in html and '"minbetyg_kopforslag": 90' in html
    assert 'data-druva="Chenin Blanc"' in html
    # flaskbild från Systembolaget, och tecknad flaska för forumviner utan bild
    assert 'src="https://product-cdn.systembolaget.se/productimages/1/1_100.webp"' in html
    assert 'class="flaska  tom"' in html


# ---------------- Munskänkarna ----------------
from vinagent import munskankarna
from vinagent.main import koppla_munskankarna

MK_SIDA = """<ul>
<li class="medium-3 groupedlist"><div class="c-wine-info"><div class="c-wine-info__left">
 <div class="c-wine-bottle__greybox"><h4>BETYG</h4><div class="wine-points text-center">17,5</div>
 <div class="c-wine-info__price text-center">319:-</div></div>
 <div class="c-wine-info__stats"><div class="c-wine-info__stat" name="category"><img src="/ws_2.svg"/><span>Mer än prisvärt</span></div></div>
 <div class="c-wine-info__typical text-center mt-20"><img src="/typical_bl.svg"/><p>Druv- eller distrikttypisk</p></div></div>
 <div class="c-wine-info__content"><h3><a href="/sv/vinlocus/tillfalligt-sortiment-27-november-2026/chateau-coutet-2022">Chateau Coutet Premier Cru 2022</a></h3>
 Producent: Chateau Coutet Systembolaget: 9547602 Stor doft av aprikos och honung. 612 fl. Druvor: 94% semillon</div></div></li>
<li class="medium-3 groupedlist"><div class="c-wine-info"><div class="wine-points">16,5</div>
 <div class="c-wine-info__stat"><span>Ej prisvärt</span></div>
 <h3><a href="/sv/vinlocus/tillfalligt-sortiment-27-november-2026/barolo">Barolo Bricco delle Viole 2022</a></h3>
 Systembolaget: 9490101 Finstämd doft av hallon. 900 fl.</div></li>
<li class="medium-3 groupedlist"><div class="wine-points">15</div> Utan artikelnummer</li>
</ul>"""


def test_tolka_provning():
    p = munskankarna.tolka_provning("https://www.munskankarna.se/sv/vinlocus/tillfalligt-sortiment-27-november-2026")
    assert p["typ"] == "tillfalligt-sortiment" and p["start"] == date(2026, 11, 27) and not p["hel_manad"]
    assert munskankarna.tolka_provning("https://x/sv/vinlocus/hitlista-26-november-2026")["typ"] == "hitlista"
    assert munskankarna.tolka_provning("https://x/sv/vinlocus/webbviner-december-2026") is None
    assert munskankarna.tolka_provning("https://x/sv/vinlocus/temaprovning-champagne-2026") is None


def test_tolka_munskankarnas_lista():
    mk = munskankarna.tolka_lista(MK_SIDA, "https://x/prov")
    assert set(mk) == {"9547602", "9490101"}
    c = mk["9547602"]
    assert c["betyg"] == 17.5 and c["prisvarde"] == "Mer än prisvärt" and c["typisk"]
    assert c["text"].startswith("Stor doft av aprikos") and "Druvor" not in c["text"]
    assert c["url"] == "https://www.munskankarna.se/sv/vinlocus/tillfalligt-sortiment-27-november-2026/chateau-coutet-2022"
    assert mk["9490101"]["prisvarde"] == "Ej prisvärt" and not mk["9490101"]["typisk"]


def _vin(nr, artikelnr, pris, forum=None):
    return {"nr": nr, "artikelnr": artikelnr, "namn": "Vin " + nr, "pris": pris, "volym_ml": 750,
            "lansering": "2026-11-27", "druvor": [], "land": "", "region": "", "typ": "Rött vin",
            "argang": "2022", "omnamnanden": 0,
            "recensioner": [{"poang": forum, "text": "", "forfattare": "P", "url": ""}] if forum else []}


def test_munskankarna_paverkar_kopforslag_och_fynd():
    mk = munskankarna.tolka_lista(MK_SIDA)
    viner = [_vin("95476", "9547602", 319),            # bara Munskänkarna, 17,5 och mer än prisvärt
             _vin("94901", "9490101", 629, forum=93),  # forumet 93, Munskänkarna ej prisvärt
             _vin("95631", "", 919, forum=86)]         # bara i forumet, inget MK
    koppla_munskankarna(viner, mk)
    pref = {"minbetyg_kopforslag": 90, "maxpris": 800, "munskankarna_min": 16.5}
    b = {v["nr"]: betyg.bedom(v, pref, date(2026, 11, 20)) for v in viner}
    assert b["95476"]["kopforslag"] and "Fynd" in b["95476"]["etiketter"]
    assert b["95476"]["betyg_kalla"] == "uppskattning"     # ingen forumpoäng att visa
    assert b["94901"]["kopforslag"]
    assert b["95631"]["munskankarna"] is None and not b["95631"]["kopforslag"]
    # för högt minimibetyg eller för dyrt stoppar Munskänkarnas köpförslag
    assert not betyg.bedom(dict(viner[0]), pref | {"munskankarna_min": 18}, date(2026, 11, 20))["kopforslag"]
    assert not betyg.bedom(dict(viner[0]), pref | {"maxpris": 300}, date(2026, 11, 20))["kopforslag"]


def test_forumvin_utan_artikelnummer_matchar_pa_fem_siffror():
    viner = [_vin("94901", "", 629, forum=93)]
    koppla_munskankarna(viner, munskankarna.tolka_lista(MK_SIDA))
    assert viner[0]["munskankarna"]["betyg"] == 16.5


def test_oense_och_sidan_visar_munskankarna():
    from datetime import datetime
    mk = munskankarna.tolka_lista(MK_SIDA)
    v = _vin("94901", "9490101", 629, forum=93)
    v["recensioner"][0]["poang"] = 95   # forumet: klart fynd, Munskänkarna: ej prisvärt
    koppla_munskankarna([v], mk)
    v = betyg.bedom(v, {"minbetyg_kopforslag": 90}, date(2026, 11, 20))
    assert v["oense"]
    v.update(bild=None, url="u", sortiment="Tillfälligt sortiment", smak="", passar_till=[], trad=None,
             preferenstraffar=v["preferenstraffar"], stil="", flaskor=900, producent="")
    html = bygg_sida([v], date(2026, 11, 20), datetime(2026, 11, 20, 8), {})
    assert "16,5" in html and "/20 MK" in html and "MK: Ej prisvärt" in html
    assert "Forumet och Munskänkarna tycker olika" in html
    assert "Finstämd doft av hallon" in html and 'id="f-mk"' in html
