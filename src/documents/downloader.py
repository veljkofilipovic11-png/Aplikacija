from __future__ import annotations

import re
from pathlib import Path

from config import settings
from src.collector.http_client import build_client, download_binary
from src.collector.models import Tender


def _safe_filename(name: str) -> str:
    name = re.sub(r"[^\w\-.]+", "_", name).strip("_")
    return name or "dokument"


def download_tender_documents(tender: Tender) -> Tender:
    """Preuzima sve PDF priloge tendera u data/downloads/<tender_id>/."""
    tender_dir = settings.DOWNLOADS_DIR / _safe_filename(tender.summary.tender_id)
    tender_dir.mkdir(parents=True, exist_ok=True)

    with build_client() as client:
        for doc in tender.documents:
            file_name = _safe_filename(doc.file_name)
            if not file_name.lower().endswith(".pdf"):
                file_name += ".pdf"
            dest_path = tender_dir / file_name

            download_binary(client, doc.download_url, dest_path)
            doc.local_path = str(dest_path)

    return tender
