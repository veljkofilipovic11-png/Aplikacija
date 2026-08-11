"""
Playwright wrapper - koristi se SAMO za korak pretrage/liste oglasa, jer je
to DevExpress ASPxGridView (postback/callback grid) koji se ne moze pouzdano
"gadjati" golim HTTP zahtevima bez reversovanja internog, nedokumentovanog
protokola. Sve posle ovoga (detalj tendera, PDF) ide preko http_client.py
bez browsera.

VAZNA NAPOMENA (procitaj pre prvog pokretanja):
Nisam mogao da izvrsim JavaScript portala iz ovog okruzenja da bih procitao
tacne CSS/ID selektore filter polja (CPV, datum, itd.) - DevExpress grid
gradi te elemente dinamicki u browseru, pa ih nema u sirovom HTML-u. Zato:

1) Selektori ispod (`_LOCATORS`) su NAJBOLJA PRETPOSTAVKA na osnovu
   uobicajenih DevExpress oznaka i moraju se potvrditi/ispraviti pre
   produkcijske upotrebe.
2) Najbrzi nacin da se to uradi: pokreni lokalno
       playwright codegen https://jnportal.ujn.gov.rs/oglasi-svi
   otvori filter panel, upisi CPV kod i klikni pretragu - codegen ce
   ispisati prave selektore koje samo prekopiras ovde.
3) `search_by_cpv()` ukljucuje network-logging rezim (`debug_log_requests=True`)
   koji ispisuje sve XHR/callback pozive grida u konzolu - to je najbrzi nacin
   da se otkrije da li grid ima stabilan JSON callback endpoint koji bi kasnije
   mogao da zameni ceo Playwright korak (brze i lakse za odrzavanje).

Kod je pisan tako da sve OSTALO (pokretanje browsera, cekanje ucitavanja,
parsiranje rezultata iz tabele, paginacija) vec radi - potrebno je samo
podesiti selektore filter polja.
"""

from __future__ import annotations

from playwright.sync_api import Browser, Page, sync_playwright

from config import settings
from src.collector.models import TenderSummary

# TODO: potvrditi/ispraviti preko `playwright codegen` (vidi napomenu iznad)
_LOCATORS = {
    "cpv_filter_input": "input[id*='CPV' i], input[placeholder*='CPV' i]",
    "search_button": "button:has-text('Pretraga'), button:has-text('Pretrazi')",
    "results_grid": ".dxgvControl, table[id*='Grid']",
    "result_rows": ".dxgvControl tbody tr.dxgvDataRow, table[id*='Grid'] tbody tr",
    "next_page_button": ".dxp-button[aria-label*='next' i], a.dxp-lite[title*='Sled' i]",
}


class PortalBrowser:
    def __init__(self, headless: bool | None = None):
        self.headless = settings.PLAYWRIGHT_HEADLESS if headless is None else headless
        self._playwright = None
        self._browser: Browser | None = None
        self._page: Page | None = None

    def __enter__(self) -> "PortalBrowser":
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self.headless)
        context = self._browser.new_context(
            user_agent=settings.DEFAULT_USER_AGENT,
            locale="sr-RS",
        )
        self._page = context.new_page()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def search_by_cpv(
        self, cpv_code: str, max_pages: int = 3, debug_log_requests: bool = False
    ) -> list[TenderSummary]:
        assert self._page is not None, "Koristi 'with PortalBrowser() as browser:'"
        page = self._page

        if debug_log_requests:
            page.on(
                "response",
                lambda r: print(f"[net] {r.status} {r.request.method} {r.url}")
                if "oglasi" in r.url.lower() or "callback" in r.url.lower()
                else None,
            )

        page.goto(settings.OGLASI_URL, wait_until="networkidle")
        page.locator(_LOCATORS["cpv_filter_input"]).first.fill(cpv_code)
        page.locator(_LOCATORS["search_button"]).first.click()
        page.wait_for_load_state("networkidle")

        results: list[TenderSummary] = []
        for page_num in range(1, max_pages + 1):
            page.locator(_LOCATORS["results_grid"]).first.wait_for(state="visible")
            rows = page.locator(_LOCATORS["result_rows"]).all()
            for row in rows:
                results.append(self._parse_row(row, cpv_code))

            next_button = page.locator(_LOCATORS["next_page_button"]).first
            if page_num >= max_pages or not next_button.is_visible():
                break
            next_button.click()
            page.wait_for_load_state("networkidle")

        return results

    @staticmethod
    def _parse_row(row, cpv_code: str) -> TenderSummary:
        cells = row.locator("td").all_inner_texts()
        link = row.locator("a").first
        detail_href = link.get_attribute("href") or ""
        detail_url = (
            detail_href
            if detail_href.startswith("http")
            else f"{settings.PORTAL_BASE_URL}/{detail_href.lstrip('/')}"
        )
        # TODO: redosled kolona (cells[0], cells[1], ...) treba uskladiti
        # sa stvarnim redosledom kolona u gridu nakon provere selektora.
        return TenderSummary(
            tender_id=detail_href.split("=")[-1] if "=" in detail_href else detail_href,
            title=cells[0] if len(cells) > 0 else "",
            cpv_code=cpv_code,
            buyer=cells[1] if len(cells) > 1 else None,
            publish_date=cells[2] if len(cells) > 2 else None,
            deadline=cells[3] if len(cells) > 3 else None,
            detail_url=detail_url,
        )
