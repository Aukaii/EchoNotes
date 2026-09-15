"""Resolve caminhos de arquivos estáticos (ícones etc.), tanto rodando a
partir do código-fonte quanto empacotado pelo PyInstaller (--onefile),
onde os arquivos ficam extraídos em uma pasta temporária (sys._MEIPASS)."""
from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative
