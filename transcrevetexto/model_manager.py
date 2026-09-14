"""Baixa e mantém em cache local os modelos usados pelo app, para que o
usuário nunca precise instalar nada manualmente.

- Whisper (faster-whisper): baixado e cacheado automaticamente pela própria
  biblioteca `huggingface_hub` no primeiro uso (não precisa de código aqui).
- LLM de resumo (GGUF, para llama.cpp): baixado por este módulo para
  `~/.transcrevetexto/models/`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import requests

from .config import LLM_VARIANTS, MODELS_DIR

ProgressCallback = Callable[[int, int], None]  # (bytes_baixados, bytes_totais)


def llm_model_path(variant: str) -> Path:
    info = LLM_VARIANTS[variant]
    return MODELS_DIR / info["file"]


def is_llm_model_ready(variant: str) -> bool:
    return llm_model_path(variant).exists()


def ensure_llm_model(variant: str, on_progress: ProgressCallback | None = None) -> Path:
    """Garante que o arquivo GGUF do modelo de resumo esteja em disco,
    baixando-o (com retomada simples) se necessário."""
    info = LLM_VARIANTS[variant]
    dest = llm_model_path(variant)
    if dest.exists():
        return dest

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    url = f"https://huggingface.co/{info['repo']}/resolve/main/{info['file']}?download=true"
    tmp_path = dest.with_suffix(dest.suffix + ".part")

    with requests.get(url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with open(tmp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)

    tmp_path.rename(dest)
    return dest
