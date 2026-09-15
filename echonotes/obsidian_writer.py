"""Monta o arquivo .md final, compatível com o formato de notas do Obsidian
(front matter YAML + corpo em Markdown)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


def format_timestamp(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    total_minutes, secs = divmod(int(td.total_seconds()), 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


@dataclass
class TranscriptSegment:
    start_seconds: float
    text: str


def _slugify_tag(tag: str) -> str:
    return tag.strip().replace(" ", "-")


def build_markdown(
    title: str,
    segments: list[TranscriptSegment],
    summary: str | None,
    tags: list[str],
    recorded_at: datetime | None = None,
) -> str:
    recorded_at = recorded_at or datetime.now()
    front_matter_tags = ", ".join(_slugify_tag(t) for t in tags)

    lines: list[str] = []
    lines.append("---")
    lines.append(f'title: "{title}"')
    lines.append(f"date: {recorded_at.strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"tags: [{front_matter_tags}]")
    lines.append("source: EchoNotes")
    lines.append("---")
    lines.append("")
    lines.append(f"# {title}")
    lines.append("")

    if summary:
        # O resumo já vem estruturado (tópicos, dicas, termos) do LLM local — inserido
        # direto, sem envolver numa seção "Resumo" genérica.
        lines.append(summary.strip())
    else:
        lines.append("_Resumo automático indisponível. Veja a transcrição completa abaixo._")
    lines.append("")

    lines.append("## 📝 Transcrição completa")
    lines.append("")
    if segments:
        # Callout dobrável do Obsidian ("[!quote]-"): mantém a nota enxuta por padrão,
        # com a transcrição bruta disponível a um clique de distância.
        lines.append("> [!quote]- Clique para expandir a transcrição com marcações de tempo")
        for seg in segments:
            ts = format_timestamp(seg.start_seconds)
            lines.append(f"> **[{ts}]** {seg.text.strip()}")
            lines.append(">")
        lines.append("")
    else:
        lines.append("_Nenhuma fala detectada._")
        lines.append("")

    return "\n".join(lines)
