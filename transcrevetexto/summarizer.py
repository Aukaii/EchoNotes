"""Resumo do texto transcrito usando um modelo local via Ollama
(https://ollama.com) — gratuito e offline. Se o Ollama não estiver
disponível, o app continua funcionando e apenas não gera o resumo."""
from __future__ import annotations

import requests

PROMPT_TEMPLATE = """Você é um assistente que organiza anotações de aula para o Obsidian.
Abaixo está a transcrição bruta, em português, de uma aula/vídeo. Gere um resumo em
Markdown, em português, com:

- Uma lista dos principais tópicos abordados (títulos ##)
- Pontos-chave em bullets, de forma objetiva
- Uma seção final "Termos e conceitos" com definições curtas dos termos técnicos citados

Não invente informações que não estejam na transcrição. Não repita a transcrição
inteira, apenas resuma.

Transcrição:
\"\"\"
{transcript}
\"\"\"
"""


class SummarizerUnavailableError(RuntimeError):
    pass


def summarize(
    transcript: str,
    model: str = "llama3.1",
    base_url: str = "http://localhost:11434",
    timeout: float = 300.0,
) -> str:
    if not transcript.strip():
        return "_Sem fala detectada para resumir._"

    prompt = PROMPT_TEMPLATE.format(transcript=transcript.strip())
    try:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise SummarizerUnavailableError(
            f"Não foi possível falar com o Ollama em {base_url} (modelo '{model}'). "
            f"Verifique se o Ollama está instalado e rodando (`ollama serve`) e se o "
            f"modelo foi baixado (`ollama pull {model}`)."
        ) from exc

    data = response.json()
    return str(data.get("response", "")).strip()
