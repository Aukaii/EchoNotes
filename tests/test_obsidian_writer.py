from datetime import datetime

from echonotes.obsidian_writer import TranscriptSegment, build_markdown, format_timestamp


def test_format_timestamp_minutes_seconds():
    assert format_timestamp(65) == "01:05"


def test_format_timestamp_hours():
    assert format_timestamp(3725) == "01:02:05"


def test_build_markdown_has_frontmatter_and_treated_summary():
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
    # com resumo disponível, a nota final não inclui a transcrição bruta
    assert "Olá turma." not in md


def test_build_markdown_falls_back_to_raw_transcript_when_summary_unavailable():
    # Se o resumo falhar, a fala capturada não pode ser perdida - cai pra
    # transcrição bruta com timestamps em vez de descartar o conteúdo.
    segments = [TranscriptSegment(start_seconds=0, text="Olá turma."), TranscriptSegment(start_seconds=12, text="Hoje vamos falar de X.")]
    md = build_markdown(title="X", segments=segments, summary=None, tags=["a"])
    assert "Resumo automático indisponível" in md
    assert "**[00:00]** Olá turma." in md
    assert "**[00:12]** Hoje vamos falar de X." in md


def test_build_markdown_without_segments_shows_no_speech_placeholder():
    md = build_markdown(title="X", segments=[], summary=None, tags=["a"])
    assert "Nenhuma fala detectada" in md
