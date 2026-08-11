# Furnicom Procurement Tracker

Automatizovan sistem za pracenje javnih nabavki (namestaj / enterijer) za
**Furnicom Interiors 018** - pretraga Portala javnih nabavki Srbije
(jnportal.ujn.gov.rs), preuzimanje konkursne dokumentacije, AI analiza
relevantnosti i notifikacije.

## Status

- [x] KORAK 1 - Data Collector (pretraga po CPV kodovima)
- [x] KORAK 2 - PDF Downloader & Text Extractor
- [ ] KORAK 3 - AI Evaluator (OpenAI `gpt-4o-mini`)
- [ ] KORAK 4 - Notification System (Telegram / email)
- [ ] Dnevni raspored (APScheduler / cron)

## Arhitektura

```
config/settings.py         konfiguracija, CPV kodovi, .env ucitavanje
src/collector/
  models.py                 TenderSummary / TenderDocument / Tender
  http_client.py             httpx klijent za sve sto NIJE JS-renderovano (detalji, PDF)
  browser_client.py          Playwright - SAMO za pretragu/listing (DevExpress grid)
  scraper.py                 orkestracija: browser -> lista -> http detalji
src/documents/
  downloader.py               preuzimanje PDF priloga (GetDocument.ashx)
  extractor.py                 pdfplumber ekstrakcija teksta iz PDF-a
src/storage/db.py            SQLite evidencija vec obradjenih tendera (dedupe)
scripts/run_collector.py     CLI za testiranje Koraka 1+2 end-to-end
```

## Vazna tehnicka napomena (procitaj pre pokretanja)

Portal **nema Cloudflare** (provereno HTTP header-ima). Pravi izazov je
sto je portal klasicna **ASP.NET WebForms + DevExpress ASPxGridView**
aplikacija - lista oglasa se filtrira kroz interne "callback" postback
zahteve koji nisu dokumentovani i lako se menjaju. Zbog toga:

- **Pretraga/listing** (`browser_client.py`) ide preko **Playwright**
  (headless Chromium) - to je jedini nacin da se to pouzdano odigra bez
  reversovanja internog protokola.
- **Detalji tendera i preuzimanje PDF-a** (`http_client.py`,
  `downloader.py`) idu preko obicnog **httpx**, bez browsera - ovo je
  potvrdjeno u samom JS kodu portala: dokumenti se preuzimaju preko
  `GET /GetDocument.ashx?id={DmsId}&userToken={uiUserToken}`, gde
  `uiUserToken` dolazi iz hidden input polja na detalj-strani.

### Selektori u `browser_client.py` moraju da se potvrde

Nisam mogao da izvrsim JavaScript portala u ovom okruzenju da procitam
tacne CSS/ID selektore filter polja (CPV input, dugme za pretragu,
tabela rezultata) - DevExpress ih generise dinamicki u browseru, pa ih
nema u sirovom HTML-u koji sam mogao da preuzmem. `_LOCATORS` recnik na
vrhu `browser_client.py` sadrzi najbolju pretpostavku i mora se potvrditi:

```bash
playwright codegen https://jnportal.ujn.gov.rs/oglasi-svi
```

Otvori filter panel, unesi CPV kod (npr. `39130000`), klikni pretragu -
codegen ce generisati tacan kod sa pravim selektorima, koje samo
prekopiras u `_LOCATORS`. Takodje mozes pokrenuti pretragu sa
`debug_log_requests=True` (vidi `search_by_cpv`) da u konzoli vidis da li
grid ima stabilan JSON callback endpoint koji bi kasnije mogao da zameni
ceo Playwright korak (brze, lakse za odrzavanje).

## Instalacija

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

pip install -r requirements.txt
playwright install chromium     # preuzima headless Chromium binarni fajl

cp .env.example .env            # popuni po potrebi (proxy, OpenAI, Telegram - kasnije)
```

## Pokretanje (test Korak 1 + Korak 2)

```bash
python scripts/run_collector.py --cpv 39130000 --max-pages 1
```

Ovo ce:
1. Pretraziti portal za dati CPV kod (Playwright),
2. Za svaki pronadjeni tender otvoriti detalj-stranicu i pronaci PDF priloge (httpx),
3. Preuzeti PDF-ove u `data/downloads/<tender_id>/`,
4. Izvuci tekst iz svakog PDF-a (pdfplumber) i ispisati broj karaktera.

Rezultat (izvuceni tekst) jos se ne salje AI-ju niti se notifikacije
salju - to su sledeci koraci (3 i 4), koje radimo posle potvrde da
pretraga i preuzimanje rade ispravno na tvojoj masini.

## Proxy fallback (opciono)

Portal trenutno nema Cloudflare, pa `PROXY_PROVIDER=none` (default) radi
direktno. Ako portal kasnije uvede rate-limit po IP adresi, u `.env`
podesi:

```
PROXY_PROVIDER=scrapingbee   # ili zenrows
SCRAPINGBEE_API_KEY=...
```

`http_client.py` vec ima logiku da u tom slucaju automatski provuce sve
zahteve kroz ScrapingBee/ZenRows API bez izmene ostatka koda.
