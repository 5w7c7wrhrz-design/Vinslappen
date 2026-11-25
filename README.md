# Vinsläppen

Går varje morgon igenom Systembolagets **tillfälliga sortiment** och **webblanseringar**,
listar alla viner per säljstartsdatum, betygsätter dem och föreslår vad som är värt att köpa.
Resultatet blir en webbsida som fungerar bra i mobilen. Helt gratis: ingen AI-tjänst och inga
API-nycklar, bara GitHub Actions.

## Så fungerar det

1. **Kommande släpp.** Agenten öppnar Systembolagets sortimentssidor för vin i en vanlig
   (osynlig) webbläsare, filtrerat på tillfälligt sortiment och webblanseringar med säljstart
   från 7 dagar bakåt till 60 dagar framåt. Den läser namn, producent, pris, druvor, årgång,
   område, smakbeskrivning och säljstart.
2. **Provningsanteckningar.** Forumet
   [Lanseringar från Systembolaget](https://www.finewines.se/forums/lanseringar-fran-systembolaget.51/)
   på finewines.se har en tråd per släpp, där forumets provare skriver anteckningar med
   Systembolagets artikelnummer och poäng som "88-90p". Agenten läser trådarna, kopplar
   anteckningarna till rätt vin via artikelnumret och räknar hur ofta vinet nämns i svaren.
   Forumet provar ofta släppen innan Systembolaget visar dem, så sådana viner kommer med ändå.
3. **Munskänkarna.** Munskänkarnas vindatabas
   [Vinlocus](https://www.munskankarna.se/sv/vinlocus/) har en provning per släpp i tillfälligt
   sortiment, med betyg av 20, prisvärdhet och en skriven bedömning. De kopplas till vinerna via
   Systembolagets artikelnummer och visas i en blå ruta under forumets betyg, utan omräkning.
   Munskänkarna provar inte webblanseringarna (deras "webbviner" är importörernas egna
   webbutiker), och en provning syns först när de publicerat den.
4. **Betyg** på 100-poängsskalan:
   - provat på forumet: medelvärdet av poängen (intervallet 88-90 räknas som 89),
   - inte provat: en försiktig **uppskattning** utifrån pris, område, ålder och hur mycket vinet
     diskuteras. Den visas i grått och blir aldrig köpförslag på egen hand.
5. **Prisvärde** jämför betyget med vad man brukar få för pengarna (ungefär +2 poäng per
   prisfördubbling från 85 poäng vid 150 kr). +3 eller mer ger etiketten *Fynd*, liksom
   Munskänkarnas "Fynd i sin prisklass" och "Mer än prisvärt". Tycker forumet och Munskänkarna
   tydligt olika om betyg eller prisvärdhet visas en gul markering.
6. **Köpförslag** är viner som forumet gett minst ditt minimibetyg (eller ett poäng under om de
   är ett fynd eller i din stil), eller som Munskänkarna gett minst 16,5 av 20, inom ditt maxpris.
   Högst sex per släpp, de bästa först.
7. **Webbsidan** visar köpförslagen överst och sedan varje släpp med alla viner, betyg,
   forumets anteckningar, Systembolagets smakbeskrivning och länkar till Systembolaget,
   forumtråden och en Vivino-sökning. Varje vin visas med Systembolagets flaskbild (en tecknad
   flaska i vinets färg när bild saknas), och en större bild när man fäller ut vinet. Du kan välja ett enskilt släppdatum, sortera på betyg,
   prisvärde eller pris och filtrera på typ, maxpris och köpförslag. Ett valt datum hamnar i
   adressen (t.ex. `#d-2026-11-27`), så länken går att spara eller skicka vidare.

Vivino tillåter inte automatiska anrop, så Vivinobetyg hämtas inte. Varje vin har i stället
en länk som söker upp vinet på Vivino.

## Varukorg per släpp

Tryck på **+** vid ett vin för att lägga det i varukorgen för sitt släpp och välj antal flaskor.
Listen längst ner visar korgen för släppet du tittar på. **Visa** öppnar varukorgen med summa,
varningar för små upplagor och knapparna:

- **Lägg till i kalendern**: skapar en kalenderhändelse på säljstarten med dina viner, och
  påminnelser kvällen före kl 19 och 15 minuter före. Ändrar du korgen efteråt visas det, och du
  lägger till den igen (ta bort den gamla händelsen).
- **Kopiera lista**: artikelnummer, antal och pris, att klistra in var du vill.
- **Öppna hos Systembolaget**: länkar till varje vin. Systembolaget kan inte ta emot en varukorg
  utifrån, så själva beställningen gör du hos dem.

**Mina varukorgar** visar alla släpp du planerat köp i, och **Bara min varukorg** döljer allt annat.
Varukorgarna sparas i webbläsaren du använder och rensas 30 dagar efter släppet.

## Dina preferenser

**På sidan:** tryck på *Mina preferenser* i filterraden. Där väljer du favoritdruvor (skriv eller
tryck på druvorna från släppen), länder och områden, producenter, maxpris, lägsta betyg och
antal köpförslag per släpp. Köpförslag, *Din stil* och sorteringen räknas om direkt. Inställningarna
sparas i webbläsaren du använder, så de följer inte med till en annan telefon eller dator.

**Som standard för alla:** tryck på *Kopiera som preferenser.json* och klistra in texten i
[`vinagent/preferenser.json`](vinagent/preferenser.json) på GitHub (pennan uppe till höger). Nästa körning använder
dem då som utgångsläge. Fälten:

| Fält | Betydelse |
|---|---|
| `favoritdruvor` | Druvor du gillar, t.ex. `"Nebbiolo"`. Ger etiketten *Din stil* och lyfter vinet i listan. |
| `favoritomraden` | Länder eller områden, t.ex. `"Piemonte"`, `"Tyskland"`. |
| `favoritproducenter` | Producenter du följer, t.ex. `"Bouland"`. |
| `maxpris` | Dyrare viner blir inte köpförslag (de syns ändå i listan). |
| `minbetyg_kopforslag` | Lägsta forumbetyg för ett köpförslag. |
| `max_kopforslag_per_slapp` | Hur många köpförslag per släppdatum som mest. |
| `munskankarna_min` | Lägsta betyg av 20 hos Munskänkarna som ger köpförslag (16,5). |

## Installation

1. **Slå på GitHub Pages:** Repo → *Settings* → *Pages* → under *Build and deployment*, välj
   källan **GitHub Actions**. Pages är gratis för publika repon. Sidan sparas dessutom efter
   varje körning under *Actions* → *Vinagent* → körningen → *Artifacts* → **vinslappen**.
2. **Kör en gång för hand:** *Actions* → *Vinagent* → *Run workflow*.
3. Sidan finns sedan på adressen som visas under *Settings* → *Pages* (och i körningens
   sammanfattning). Lägg den på hemskärmen i mobilen: Dela → *Lägg till på hemskärmen*.

Agenten körs sedan automatiskt varje morgon.

## Köra lokalt

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m vinagent --ut site          # öppna site/index.html
python -m vinagent --dagar 30 --bakat 0
python -m pytest tests/test_vinagent.py
```

## Begränsningar

- Systembolaget publicerar ett släpp några veckor i förväg, så längre fram är listan tom.
- Om Systembolaget eller forumet byter utseende på sina sidor kan agenten behöva justeras.
  Forumet nere stoppar inte körningen: listan byggs då utan anteckningar.
- Agenten pausar en sekund mellan sidorna för att inte belasta sajterna.
- Betygen speglar forumprovarnas smak. Läs anteckningarna innan du köper.
