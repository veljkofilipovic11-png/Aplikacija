"""
Laki HTTP klijent za sve sto NE zahteva izvrsavanje JavaScript-a:
- detalj-stranica tendera (obican server-rendered HTML)
- preuzimanje PDF priloga preko /GetDocument.ashx

Portal (jnportal.ujn.gov.rs) NEMA Cloudflare (provereno) - ali je ASP.NET
WebForms aplikacija, pa je bitno da klijent drzi kolacice (sesiju) izmedju
poziva, jer se npr. 'userToken' za preuzimanje dokumenata cita iz iste
sesije u kojoj je ucitana detalj-stranica.

Proxy fallback (ScrapingBee/ZenRows) je ovde pripremljen kao opcija za
slucaj da portal kasnije uvede rate-limit po IP adresi. Nije aktivan po
defaultu (PROXY_PROVIDER=none u .env).
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from config import settings


def build_headers(referer: str | None = None) -> dict:
    headers = {
        "User-Agent": settings.DEFAULT_USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    return headers


def build_client() -> httpx.Client:
    """
    Kreira httpx.Client koji cuva kolacice (sesiju) izmedju poziva.
    Kada je PROXY_PROVIDER podesen, zahtevi se preusmeravaju kroz
    ScrapingBee/ZenRows proxy endpoint umesto direktno na portal.
    """
    if settings.PROXY_PROVIDER == "scrapingbee":
        return httpx.Client(
            base_url="https://app.scrapingbee.com",
            headers=build_headers(),
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            http2=True,
            follow_redirects=True,
        )
    if settings.PROXY_PROVIDER == "zenrows":
        return httpx.Client(
            base_url="https://api.zenrows.com",
            headers=build_headers(),
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
            http2=True,
            follow_redirects=True,
        )
    return httpx.Client(
        base_url=settings.PORTAL_BASE_URL,
        headers=build_headers(referer=settings.PORTAL_BASE_URL),
        timeout=settings.REQUEST_TIMEOUT_SECONDS,
        http2=True,
        follow_redirects=True,
    )


def _proxied_url(target_url: str) -> str:
    """Umotava ciljni URL u ScrapingBee/ZenRows query parametar."""
    if settings.PROXY_PROVIDER == "scrapingbee":
        return f"/api/v1/?api_key={settings.SCRAPINGBEE_API_KEY}&url={target_url}"
    if settings.PROXY_PROVIDER == "zenrows":
        return f"/v1/?apikey={settings.ZENROWS_API_KEY}&url={target_url}"
    return target_url


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def fetch_html(client: httpx.Client, url: str) -> str:
    """GET zahtev koji vraca sirovi HTML. Radi retry sa eksponencijalnim backoff-om."""
    request_url = _proxied_url(url) if settings.PROXY_PROVIDER != "none" else url
    response = client.get(request_url)
    response.raise_for_status()
    return response.text


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def download_binary(client: httpx.Client, url: str, dest_path) -> None:
    """Preuzima fajl (PDF) na disk, strimovano (ne ucitava sve u memoriju)."""
    request_url = _proxied_url(url) if settings.PROXY_PROVIDER != "none" else url
    with client.stream("GET", request_url) as response:
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
