from __future__ import annotations

from bs4 import BeautifulSoup

from config import settings
from src.collector.browser_client import PortalBrowser
from src.collector.http_client import build_client, fetch_html
from src.collector.models import Tender, TenderDocument, TenderSummary


def collect_tenders_for_cpv_codes(
    cpv_codes: dict[str, str] | None = None, max_pages_per_code: int = 3
) -> list[TenderSummary]:
    """KORAK 1: pretraga portala za svaki CPV kod, vraca listu sazetaka."""
    cpv_codes = cpv_codes or settings.CPV_CODES
    all_results: list[TenderSummary] = []
    seen_ids: set[str] = set()

    with PortalBrowser() as browser:
        for cpv_code in cpv_codes:
            summaries = browser.search_by_cpv(cpv_code, max_pages=max_pages_per_code)
            for summary in summaries:
                if summary.tender_id not in seen_ids:
                    seen_ids.add(summary.tender_id)
                    all_results.append(summary)

    return all_results


def fetch_tender_documents(summary: TenderSummary) -> Tender:
    """
    Otvara detalj-stranicu tendera (obican HTML, bez browsera) i
    izvlaci listu PDF priloga preko GetDocument.ashx handlera.

    Potvrdjeno u JS kodu portala:
        /GetDocument.ashx?id={DmsId}&userToken={uiUserToken}
    gde 'uiUserToken' dolazi iz hidden input polja na strani, a sesija
    (kolacici) mora biti ista koja je ucitala detalj-stranicu.
    """
    tender = Tender(summary=summary)

    with build_client() as client:
        html = fetch_html(client, summary.detail_url)
        soup = BeautifulSoup(html, "html.parser")

        token_input = soup.find("input", id="uiUserToken")
        user_token = token_input.get("value") if token_input else None

        estimated_value_el = soup.find(string=lambda s: s and "Procenjena vrednost" in s)
        if estimated_value_el:
            tender.estimated_value = estimated_value_el.find_parent().get_text(strip=True)

        # Linkovi ka prilozima obicno imaju 'GetDocument.ashx' ili DmsId u href/data atributu.
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "GetDocument.ashx" in href or "DmsId" in href:
                download_url = (
                    href if href.startswith("http") else f"{settings.PORTAL_BASE_URL}/{href.lstrip('/')}"
                )
                if user_token and "userToken=" not in download_url:
                    separator = "&" if "?" in download_url else "?"
                    download_url = f"{download_url}{separator}userToken={user_token}"

                dms_id = href.split("id=")[-1].split("&")[0] if "id=" in href else href
                file_name = link.get_text(strip=True) or f"{dms_id}.pdf"
                tender.documents.append(
                    TenderDocument(dms_id=dms_id, file_name=file_name, download_url=download_url)
                )

    return tender
