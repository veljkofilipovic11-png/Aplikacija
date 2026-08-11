from __future__ import annotations

import logging

import pdfplumber

from src.collector.models import Tender

logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: str) -> str:
    """Vraca sav tekst iz PDF-a (spojene stranice, prazan string ako je PDF skeniran/bez teksta)."""
    text_parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def extract_tender_documents(tender: Tender) -> Tender:
    """KORAK 2: puni `extracted_text` za svaki preuzeti dokument tendera."""
    for doc in tender.documents:
        if not doc.local_path:
            continue
        try:
            doc.extracted_text = extract_text_from_pdf(doc.local_path)
        except Exception as exc:  # pdfplumber moze da pukne na osteceni/skenirani PDF
            logger.warning("Ne mogu da procitam PDF %s: %s", doc.local_path, exc)
            doc.extracted_text = ""
    return tender
