"""Orquestra captura de áudio -> segmentação (VAD) -> transcrição -> resumo
-> gravação do arquivo .md final."""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime
from pathlib import Path

from .audio_capture import LoopbackRecorder
from .config import Config
from .obsidian_writer import TranscriptSegment, build_markdown
from .summarizer import SummarizerUnavailableError, summarize
from .transcriber import Transcriber
from .vad import SegmentChunker


class TranscriptionSession:
    """Uma sessão de gravação: do start() ao stop_and_save()."""

    def __init__(self, config: Config, on_partial_text=None, on_status=None) -> None:
        self.config = config
        self.on_partial_text = on_partial_text or (lambda text, ts: None)
        self.on_status = on_status or (lambda status: None)

        self._recorder = LoopbackRecorder(sample_rate=config.sample_rate)
        self._chunker = SegmentChunker(
            sample_rate=config.sample_rate,
            energy_threshold=config.energy_threshold,
            silence_ms_to_close_segment=config.silence_ms_to_close_segment,
            min_segment_ms=config.min_segment_ms,
        )
        self._transcriber: Transcriber | None = None
        self._segments: list[TranscriptSegment] = []
        self._start_time: float = 0.0
        self._worker_thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._segment_queue: "queue.Queue[tuple[float, object]]" = queue.Queue()

    def start(self) -> None:
        self.on_status("Carregando modelo Whisper...")
        self._transcriber = Transcriber(
            model_size=self.config.whisper_model,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type,
            language=self.config.language,
        )
        self._start_time = time.monotonic()
        self._stopping.clear()
        self._recorder.start()
        self._worker_thread = threading.Thread(target=self._run, daemon=True)
        self._worker_thread.start()
        self.on_status("Gravando e transcrevendo...")

    def _run(self) -> None:
        assert self._transcriber is not None
        for frame in self._recorder.frames():
            if self._stopping.is_set():
                break
            segment_start = time.monotonic() - self._start_time
            audio = self._chunker.push(frame)
            if audio is not None:
                self._handle_segment(segment_start, audio)

        final_audio = self._chunker.flush_remaining()
        if final_audio is not None:
            self._handle_segment(time.monotonic() - self._start_time, final_audio)

    def _handle_segment(self, approx_start_seconds: float, audio) -> None:
        assert self._transcriber is not None
        text = self._transcriber.transcribe_segment(audio)
        if not text:
            return
        duration = audio.shape[0] / self.config.sample_rate
        start = max(0.0, approx_start_seconds - duration)
        self._segments.append(TranscriptSegment(start_seconds=start, text=text))
        self.on_partial_text(text, start)

    def stop_and_save(self, title: str) -> Path:
        self.on_status("Finalizando gravação...")
        self._stopping.set()
        self._recorder.stop()
        if self._worker_thread is not None:
            self._worker_thread.join(timeout=30)

        transcript_text = "\n".join(seg.text for seg in self._segments)

        summary: str | None = None
        self.on_status("Gerando resumo (Ollama)...")
        try:
            summary = summarize(
                transcript_text,
                model=self.config.ollama_model,
                base_url=self.config.ollama_url,
            )
        except SummarizerUnavailableError as exc:
            summary = None
            self.on_status(str(exc))

        markdown = build_markdown(
            title=title,
            segments=self._segments,
            summary=summary,
            tags=self.config.tags,
            recorded_at=datetime.now(),
        )

        output_dir = Path(self.config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip() or "aula"
        filename = f"{datetime.now().strftime('%Y-%m-%d %H-%M')} - {safe_title}.md"
        output_path = output_dir / filename
        output_path.write_text(markdown, encoding="utf-8")

        self.on_status(f"Salvo em: {output_path}")
        return output_path
