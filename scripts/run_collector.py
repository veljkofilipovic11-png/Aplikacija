"""
Test skripta za KORAK 1 (pretraga) + KORAK 2 (preuzimanje PDF-a i ekstrakcija teksta).

Pokretanje:
    python scripts/run_collector.py --cpv 39130000 --max-pages 1

Isti pipeline (src/pipeline.py) koristi i mobilni dashboard, tako da rezultat
ovde odmah bude vidljiv i na telefonu.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import run_pipeline
from src.utils.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretraga i preuzimanje tendera sa Portala javnih nabavki")
    parser.add_argument("--cpv", action="append", help="CPV kod (moze vise puta). Default: podesavanja iz baze/settings.py")
    parser.add_argument("--max-pages", type=int, default=1, help="Max broj stranica rezultata po CPV kodu")
    args = parser.parse_args()

    setup_logging()

    cpv_codes = {code: "" for code in args.cpv} if args.cpv else None

    result = run_pipeline(cpv_codes=cpv_codes, max_pages_per_code=args.max_pages)
    logger.info("Gotovo. Pronadjeno: %d, novih: %d", result["found"], result["new"])


if __name__ == "__main__":
    main()
