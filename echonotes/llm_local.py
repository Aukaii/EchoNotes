"""Resumo do texto transcrito usando um LLM pequeno rodando localmente dentro
do próprio processo (llama.cpp via llama-cpp-python) — sem instalar nada
separado, sem internet depois do primeiro download do modelo.
"""
from __future__ import annotations

import os
from typing import Callable

from .config import Config
from .model_manager import ensure_llm_model

_CHUNK_PROMPT = """Resuma em português os pontos principais do trecho de transcrição de aula
abaixo, em bullets curtos e objetivos. Não invente informações que não estejam no texto.

Trecho:
\"\"\"
{chunk}
\"\"\"
"""

_FINAL_PROMPT = """Você é um assistente que organiza anotações de aula para o Obsidian.
Abaixo estão resumos parciais (em ordem) de uma aula. Combine-os em um único resumo
final em Markdown, em português, com:

- Uma lista dos principais tópicos abordados (títulos ##)
- Pontos-chave em bullets, de forma objetiva, sem repetição
- Uma seção final "Termos e conceitos" com definições curtas dos termos técnicos citados

Resumos parciais:
\"\"\"
{partial_summaries}
\"\"\"
"""

_MAX_CHARS_PER_CHUNK = 6000

_llm_cache: dict[str, object] = {}


def _get_llm(variant: str, on_progress: Callable[[int, int], None] | None = None):
    if variant in _llm_cache:
        return _llm_cache[variant]

    from llama_cpp import Llama  # import tardio: evita custo de carregar a lib se não usada

    model_path = ensure_llm_model(variant, on_progress=on_progress)
    llm = Llama(
        model_path=str(model_path),
        n_ctx=8192,
        n_threads=os.cpu_count() or 4,
        verbose=False,
    )
    _llm_cache[variant] = llm
    return llm


def _chat(llm, prompt: str, max_tokens: int = 1024) -> str:
    result = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.3,
    )
    return str(result["choices"][0]["message"]["content"]).strip()


def _split_into_chunks(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        current.append(word)
        current_len += len(word) + 1
        if current_len >= max_chars:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current))
    return chunks


class SummarizerUnavailableError(RuntimeError):
    pass


def summarize(
    transcript: str,
    config: Config,
    on_model_download_progress: Callable[[int, int], None] | None = None,
) -> str:
    if not transcript.strip():
        return "_Sem fala detectada para resumir._"

    try:
        llm = _get_llm(config.llm_variant, on_progress=on_model_download_progress)
    except Exception as exc:  # noqa: BLE001 - download/carregamento do modelo pode falhar por vários motivos
        raise SummarizerUnavailableError(
            f"Não foi possível carregar o modelo de resumo local ({exc}). "
            "Verifique sua conexão (necessária apenas na primeira vez, para baixar o modelo) "
            "e espaço em disco."
        ) from exc

    chunks = _split_into_chunks(transcript, _MAX_CHARS_PER_CHUNK)
    if len(chunks) == 1:
        return _chat(llm, _CHUNK_PROMPT.format(chunk=chunks[0]), max_tokens=1024)

    partial_summaries = [_chat(llm, _CHUNK_PROMPT.format(chunk=c), max_tokens=512) for c in chunks]
    combined = "\n\n".join(f"- Trecho {i + 1}: {s}" for i, s in enumerate(partial_summaries))
    return _chat(llm, _FINAL_PROMPT.format(partial_summaries=combined), max_tokens=1536)
