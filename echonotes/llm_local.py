"""Resumo do texto transcrito usando um LLM pequeno rodando localmente dentro
do próprio processo (llama.cpp via llama-cpp-python) — sem instalar nada
separado, sem internet depois do primeiro download do modelo.
"""
from __future__ import annotations

import os
from typing import Callable

from .config import Config
from .model_manager import ensure_llm_model

_CHUNK_PROMPT = """Você está extraindo notas de estudo a partir de um trecho de transcrição
de aula. Leia o trecho abaixo e extraia, em português:

1. Tópicos abordados nesse trecho e os pontos-chave de cada um — seja específico e preciso,
   sem inventar nada que não esteja no texto.
2. Dicas, avisos ou comentários relevantes que quem fala tenha feito (ex.: "isso cai na
   prova", "presta atenção nisso", recomendações práticas) — só inclua se estiver
   realmente no texto, não invente dicas genéricas.
3. Termos técnicos ou siglas citados, com uma definição curta baseada no contexto.

Seja objetivo, resuma com suas próprias palavras em vez de copiar frases inteiras. Se o
trecho não tiver nada relevante para algum desses três pontos, pode omitir esse ponto.

Trecho:
\"\"\"
{chunk}
\"\"\"
"""

_FINAL_PROMPT = """Você é um assistente que organiza anotações de aula em notas de estudo
para o Obsidian. Abaixo estão extrações parciais (em ordem cronológica) de uma aula. Combine
tudo em notas finais, únicas, em português, seguindo EXATAMENTE esta estrutura Markdown (não
inclua nenhum título de nível 1 "#", não inclua front matter, comece direto em "## 📌"):

## 📌 Tópicos principais

### <nome do tópico 1>
- ponto-chave objetivo e específico
- ponto-chave objetivo e específico

### <nome do tópico 2>
- ...

(um "###" para cada tópico realmente abordado na aula, quantos forem necessários; não
repita o mesmo ponto em mais de um tópico)

## 💡 Dicas e comentários

> [!tip] <dica curta em poucas palavras>
> Explicação da dica em 1-2 frases, baseada no que foi dito.

(uma citação "> [!tip]" por dica encontrada nas extrações; se nenhuma dica ou comentário
relevante foi feito na aula, escreva apenas "_Nenhuma dica específica mencionada nesta
aula._" nesta seção — não invente dicas)

## 📚 Termos e conceitos

- **<termo>**: definição curta e precisa
- **<termo>**: definição curta e precisa

(se não houver termos técnicos relevantes, escreva "_Nenhum termo técnico relevante._")

Regra mais importante: não invente informações que não estejam nas extrações abaixo. Seja
preciso e específico, evite generalidades vagas.

Extrações parciais:
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

    # Sempre passa por duas etapas (extração por trecho + composição final), mesmo para
    # transcrições curtas de um só trecho: é o que garante a estrutura de notas do Obsidian
    # (tópicos, dicas, termos) de forma consistente, em vez de só um resumo cru quando a
    # aula é curta.
    chunks = _split_into_chunks(transcript, _MAX_CHARS_PER_CHUNK)
    partial_extracts = [_chat(llm, _CHUNK_PROMPT.format(chunk=c), max_tokens=768) for c in chunks]
    combined = "\n\n".join(f"--- Trecho {i + 1} ---\n{s}" for i, s in enumerate(partial_extracts))
    return _chat(llm, _FINAL_PROMPT.format(partial_summaries=combined), max_tokens=2048)
