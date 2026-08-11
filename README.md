# Furnicom Procurement Tracker

Automatizovan sistem za pracenje javnih nabavki (namestaj / enterijer) za
**Furnicom Interiors 018** - pretraga Portala javnih nabavki Srbije
(jnportal.ujn.gov.rs), preuzimanje konkursne dokumentacije, AI analiza
relevantnosti i notifikacije.

## Status

- [x] KORAK 1 - Data Collector (pretraga po CPV kodovima)
- [x] KORAK 2 - PDF Downloader & Text Extractor
- [x] Mobilni dashboard (pregled tendera, rucno pokretanje, podesavanja sa telefona)
- [ ] KORAK 3 - AI Evaluator (OpenAI `gpt-4o-mini`)
- [ ] KORAK 4 - Notification System (Telegram / email)
- [ ] Dnevni raspored (APScheduler / cron)

## Arhitektura

```
config/settings.py         konfiguracija, CPV kodovi, dashboard lozinka, .env ucitavanje
src/collector/
  models.py                 TenderSummary / TenderDocument / Tender
  http_client.py             httpx klijent za sve sto NIJE JS-renderovano (detalji, PDF)
  browser_client.py          Playwright - SAMO za pretragu/listing (DevExpress grid)
  scraper.py                 orkestracija: browser -> lista -> http detalji
src/documents/
  downloader.py               preuzimanje PDF priloga (GetDocument.ashx)
  extractor.py                 pdfplumber ekstrakcija teksta iz PDF-a
src/storage/db.py            SQLite: tenderi, podesavanja (CPV/prag/pauza), istorija pokretanja
src/pipeline.py             jedina putanja pokretanja pretrage - koristi je CLI i dashboard
src/api/
  main.py                    FastAPI app (login, tenderi, podesavanja, pokretanje pretrage)
  auth.py                     lozinka -> potpisan token (Bearer), za pristup sa telefona
static/                     mobilni dashboard (obican HTML/JS, bez build koraka)
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

## Mobilni dashboard (upravljanje sa telefona)

Jednostavna web stranica (radi u bilo kom mobilnom browseru) za pregled
tendera, rucno pokretanje pretrage i izmenu podesavanja (CPV kodovi, prag
relevantnosti, pauza) - bez potrebe da se dira server ili `.env`.

### Pokretanje

```bash
# u .env obavezno podesi:
#   DASHBOARD_PASSWORD=<jaka lozinka>
#   DASHBOARD_SECRET_KEY=<generisi: python -c "import secrets; print(secrets.token_hex(32))">

uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

Otvori `http://<ip-adresa-servera>:8000` u browseru na telefonu i prijavi
se lozinkom iz `.env`.

### Deploy na Render (besplatno) - korak po korak

U repo je dodat `render.yaml` koji Render cita automatski ("Blueprint"),
tako da ne moras rucno da podesavas build/start komande.

1. Otvori [render.com](https://render.com) i napravi nalog (najlakse preko GitHub naloga - istog kojim je povezan repo `veljkofilipovic11-png/aplikacija`).
2. Klikni **New +** -> **Blueprint**.
3. Izaberi repo `veljkofilipovic11-png/aplikacija` i granu `claude/public-procurement-tracker-8dr8u4`.
4. Render prepoznaje `render.yaml` i prikazuje servis `furnicom-procurement-tracker` sa planom **Free**. Trazi da popunis dva polja (oznacena kao "secret"):
   - `DASHBOARD_PASSWORD` -> izmisli jaku lozinku (npr. iz password menadzera), zapamti je za prijavu na telefonu.
   - `DASHBOARD_SECRET_KEY` -> nasumican string, npr:
     ```
     4cb8d599fd43c2a9a139d9781c1fa4b14871bd16240b215417531f256d8fc455
     ```
     (ovo je generisano samo za tebe, ne mora dalje da se cuva u tajnosti kao sto lozinka mora, ali slobodno zameni svojim ako zelis).
5. Klikni **Apply** / **Deploy**. Prvi build traje 5-10 minuta (instalira i Chromium za Playwright).
6. Kad build zavrsi, Render ti daje link oblika `https://furnicom-procurement-tracker.onrender.com` - otvori ga na telefonu i prijavi se lozinkom iz koraka 4.

**Vazna ogranicenja besplatnog plana** (da ne bude iznenadjenje):

- **"Zaspivanje"**: posle ~15 minuta bez saobracaja servis se gasi; sledece otvaranje na telefonu ceka 30-60s dok se "probudi". Normalno za povremenu proveru, nije prakticno za nesto sto mora da odgovori trenutno.
- **Fajl-sistem se brise pri svakom restartu/spavanju** - besplatan plan nema trajni disk, sto znaci da SQLite baza (`data/tenders.db`) i preuzeti PDF-ovi **nestaju svaki put kad se servis ugasi i ponovo probudi**. Za sada (dok testiramo KORAK 1+2 i sam dashboard) to nije opasno - najgore sto se desi je da se isti tenderi ponovo prikazu/preuzmu. Ali **pre nego sto ukljucimo KORAK 4 (notifikacije)**, moramo ovo resiti, jer bi inace mogao da dobijes duplirane notifikacije za isti tender - najjednostavnije resenje tada je Render Starter plan (~7$/mesec) + mali disk (~1$/mesec) da baza ostane trajna. Javi mi kad stignemo do tog koraka pa prebacujemo.
- **Playwright (Chromium) trosi dosta RAM-a** na masini koja ima samo 512MB - moguce je da pretraga povremeno pukne zbog nedostatka memorije. Ako se to desava redovno, to je znak da je vreme za placeni plan.

### Alternative (kasnije, ako free plan postane ogranicavajuc)

- **Tvoj racunar + [Tailscale](https://tailscale.com)** (besplatan VPN) - server radi na tvojoj masini, bez "spavanja" i bez ogranicenja diska, ali racunar mora da bude upaljen.
- **Placen VPS** (Hetzner/DigitalOcean, ~5€/mesec) - uvek upaljen, trajan disk, bez "budjenja". Najbolja opcija kad sistem pocne da radi svako jutro u produkciji.

U svim slucajevima vazi: obavezno jaka `DASHBOARD_PASSWORD` i HTTPS (Render/Railway/Fly.io ga daju automatski; kod VPS-a ili Tailscale-a ga sam podesavas ili se oslanjas na VPN enkripciju). Autentifikacija dashboard-a je namerno jednostavna (jedna deljena lozinka, jer je ovo interni alat za jednog korisnika) - nije zamena za pravi multi-user auth sistem ako se dashboard ikad deli sa vise ljudi.

### API pregled

| Endpoint | Opis |
|---|---|
| `POST /api/login` | `{"password": "..."}` -> `{"token": "..."}` |
| `GET /api/tenders?min_score=7` | lista tendera (opciono filtrirano po AI oceni) |
| `GET /api/tenders/{id}` | detalji jednog tendera + dokumenti |
| `GET /api/settings` / `PUT /api/settings` | CPV kodovi, prag relevantnosti, pauza |
| `POST /api/run` | pokrece pretragu u pozadini (409 ako je vec u toku) |
| `GET /api/status` | da li je pretraga u toku, poslednje pokretanje, broj tendera |

Kolona `relevance_score` u bazi je vec spremna za KORAK 3 (AI evaluator) -
kad se doda, dashboard ce automatski prikazivati ocene i filter "Samo
relevantni" bez ikakve izmene frontend-a.
