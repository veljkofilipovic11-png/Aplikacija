"""
Jedina putanja kroz koju se pokrece prikupljanje tendera - koristi je i
scripts/run_collector.py (CLI) i mobilni dashboard (dugme "Pokreni pretragu"),
da logika ne bude duplirana na dva mesta.
"""

from __future__ import annotations

import logging

from config import settings as app_settings
from src.collector.scraper import collect_tenders_for_cpv_codes, fetch_tender_documents
from src.documents.downloader import download_tender_documents
from src.documents.extractor import extract_tender_documents
from src.storage import db

logger = logging.getLogger(__name__)


def run_pipeline(cpv_codes: dict[str, str] | None = None, max_pages_per_code: int = 2) -> dict:
    """KORAK 1 + KORAK 2 nad svim CPV kodovima; upisuje nove tendere u bazu."""
    db.init_db()

    if cpv_codes is None:
        cpv_codes = db.get_app_settings().get("cpv_codes") or app_settings.CPV_CODES

    run_id = db.start_run()
    found = 0
    new_count = 0
    try:
        summaries = collect_tenders_for_cpv_codes(cpv_codes, max_pages_per_code=max_pages_per_code)
        found = len(summaries)

        for summary in summaries:
            if db.get_tender(summary.tender_id):
                continue  # vec obradjen u ranijem pokretanju

            tender = fetch_tender_documents(summary)
            tender = download_tender_documents(tender)
            tender = extract_tender_documents(tender)
            db.upsert_tender(tender)
            new_count += 1

        db.finish_run(run_id, status="success", tenders_found=found, new_tenders=new_count)
    except Exception as exc:
        logger.exception("Pokretanje pretrage nije uspelo")
        db.finish_run(
            run_id, status="error", tenders_found=found, new_tenders=new_count, error_message=str(exc)
        )
        raise

    return {"found": found, "new": new_count}
