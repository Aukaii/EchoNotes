from datetime import datetime

from echonotes.obsidian_writer import TranscriptSegment, build_markdown, format_timestamp


def test_format_timestamp_minutes_seconds():
    assert format_timestamp(65) == "01:05"


def test_format_timestamp_hours():
    assert format_timestamp(3725) == "01:02:05"


def test_build_markdown_has_frontmatter_and_sections():
    segments = [TranscriptSegment(start_seconds=0, text="Olá turma."), TranscriptSegment(start_seconds=12, text="Hoje vamos falar de X.")]
    summary = "## 📌 Tópicos principais\n\n### Introdução\n- Ponto 1\n- Ponto 2"
    md = build_markdown(
        title="Aula de teste",
        segments=segments,
        summary=summary,
        tags=["transcricao", "aula"],
        recorded_at=datetime(2026, 1, 1, 10, 30),
    )
    assert md.startswith("---")
    assert 'title: "Aula de teste"' in md
    assert "tags: [transcricao, aula]" in md
    assert "## 📌 Tópicos principais" in md
    assert "## 📝 Transcrição completa" in md
    assert "> [!quote]-" in md
    assert "> **[00:00]** Olá turma." in md
    assert "> **[00:12]** Hoje vamos falar de X." in md


def test_build_markdown_without_summary_shows_placeholder():
    md = build_markdown(title="X", segments=[], summary=None, tags=["a"])
    assert "Resumo automático indisponível" in md
    assert "Nenhuma fala detectada" in md
