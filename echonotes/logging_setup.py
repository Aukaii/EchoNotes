"""Configura logging em arquivo. Necessário porque o .exe empacotado roda
com --noconsole: sem isso, qualquer exceção em uma thread de fundo
(captura de áudio, transcrição, resumo) desaparece sem deixar rastro."""
from __future__ import annotations

import logging

from .config import APP_DIR

LOG_PATH = APP_DIR / "echonotes.log"


def setup_logging() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_PATH),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
