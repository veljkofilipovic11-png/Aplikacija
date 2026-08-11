import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

PORTAL_BASE_URL = os.getenv("PORTAL_BASE_URL", "https://jnportal.ujn.gov.rs")
OGLASI_URL = f"{PORTAL_BASE_URL}/oglasi-svi"

PLAYWRIGHT_HEADLESS = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true"
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))

PROXY_PROVIDER = os.getenv("PROXY_PROVIDER", "none")  # none | scrapingbee | zenrows
SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY", "")
ZENROWS_API_KEY = os.getenv("ZENROWS_API_KEY", "")

DOWNLOADS_DIR = Path(os.getenv("DOWNLOADS_DIR", DATA_DIR / "downloads"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "tenders.db"))

DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# CPV kodovi relevantni za proizvodnju namestaja i opremanje enterijera.
# Sifrarnik je javni EU/Srbija standard (nije nagadjanje) - dopuni po potrebi
# preko /cpv stranice portala.
CPV_CODES = {
    "39100000": "Namestaj",
    "39110000": "Sedista, stolice i srodni proizvodi, i njihovi delovi",
    "39120000": "Stolovi, ormani, pisaci stolovi i police za knjige",
    "39130000": "Kancelarijski namestaj",
    "39140000": "Namestaj za domacinstvo (kuhinje, spavace sobe)",
    "39141000": "Kuhinjski namestaj i aparati",
    "39150000": "Razni namestaj i oprema",
    "39151000": "Razni namestaj",
    "39153000": "Namestaj za konferencijske sale",
    "39156000": "Namestaj za prijemne prostorije i cekaonice",
    "39160000": "Skolski namestaj",
    "39170000": "Namestaj za prodavnice",
}

# Realisticni Chrome User-Agent - DevExpress/ASP.NET stranice ponekad
# serviraju drugaciji (osiromaseni) markup botovima/starim UA-ovima.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

RELEVANCE_THRESHOLD = int(os.getenv("RELEVANCE_THRESHOLD", "7"))
