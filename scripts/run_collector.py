"""
Test skripta za KORAK 1 (pretraga) + KORAK 2 (preuzimanje PDF-a i ekstrakcija teksta).

Pokretanje:
    python scripts/run_collector.py --cpv 39130000 --max-pages 1

KORAK 3 (AI ocena) i KORAK 4 (notifikacije) jos nisu povezani - ova skripta
samo ispisuje sta je pronadjeno i cuva izvuceni tekst, da se pipeline moze
proveriti pre nego sto dodamo OpenAI/Telegram deo.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from src.collector.scraper import collect_tenders_for_cpv_codes, fetch_tender_documents
from src.documents.downloader import download_tender_documents
from src.documents.extractor import extract_tender_documents
from src.storage.db import init_db, is_seen, mark_seen
from src.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretraga i preuzimanje tendera sa Portala javnih nabavki")
    parser.add_argument("--cpv", action="append", help="CPV kod (moze vise puta). Default: svi iz settings.CPV_CODES")
    parser.add_argument("--max-pages", type=int, default=1, help="Max broj stranica rezultata po CPV kodu")
    parser.add_argument("--skip-seen", action="store_true", help="Preskoci tendere koji su vec obradjeni ranije")
    args = parser.parse_args()

    setup_logging()
    init_db()

    cpv_codes = {code: settings.CPV_CODES.get(code, "") for code in args.cpv} if args.cpv else None

    logger.info("KORAK 1: pretraga portala...")
    summaries = collect_tenders_for_cpv_codes(cpv_codes, max_pages_per_code=args.max_pages)
    logger.info("Pronadjeno %d tendera.", len(summaries))

    for summary in summaries:
        if args.skip_seen and is_seen(summary.tender_id):
            logger.info("Preskacem vec obradjen tender: %s", summary.tender_id)
            continue

        logger.info("Obradjujem tender %s - %s", summary.tender_id, summary.title)

        tender = fetch_tender_documents(summary)
        logger.info("  Pronadjeno %d dokumenata.", len(tender.documents))

        tender = download_tender_documents(tender)
        tender = extract_tender_documents(tender)

        for doc in tender.documents:
            char_count = len(doc.extracted_text or "")
            logger.info("  %s -> %d karaktera izvucenog teksta", doc.file_name, char_count)

        mark_seen(summary.tender_id)

    logger.info("Gotovo.")


if __name__ == "__main__":
    main()
