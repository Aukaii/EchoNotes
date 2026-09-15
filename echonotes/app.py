"""Orquestra captura de áudio -> segmentação (VAD) -> transcrição -> resumo
-> gravação do arquivo .md final."""
from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

from .audio_capture import LoopbackRecorder
from .audio_utils import save_wav
from .config import Config
from .llm_local import SummarizerUnavailableError, summarize
from .obsidian_writer import TranscriptSegment, build_markdown
from .transcriber import Transcriber
from .vad import SegmentChunker, frame_rms

logger = logging.getLogger(__name__)

# A cada quantos frames (de frame_ms cada) reportar o nível de áudio à GUI.
# Frames chegam a cada ~30ms; reportar todos seria mais atualização do que
# qualquer interface precisa e sobrecarregaria a thread principal do tkinter.
_LEVEL_REPORT_EVERY_N_FRAMES = 5


class TranscriptionSession:
    """Uma sessão de gravação: do start() ao stop_and_save()."""

    def __init__(self, config: Config, on_partial_text=None, on_status=None, on_level=None) -> None:
        self.config = config
        self.on_partial_text = on_partial_text or (lambda text, ts: None)
        self.on_status = on_status or (lambda status: None)
        self.on_level = on_level or (lambda level, threshold: None)

        self._recorder = LoopbackRecorder(sample_rate=config.sample_rate, on_error=self._on_recorder_error)
        self._chunker = SegmentChunker(
            sample_rate=config.sample_rate,
            energy_threshold=config.energy_threshold,
            silence_ms_to_close_segment=config.silence_ms_to_close_segment,
            min_segment_ms=config.min_segment_ms,
            max_segment_ms=config.max_segment_ms,
        )
        self._transcriber: Transcriber | None = None
        self._segments: list[TranscriptSegment] = []
        self._start_time: float = 0.0
        self._worker_thread: threading.Thread | None = None
        self._stopping = threading.Event()
        self._segment_queue: "queue.Queue[tuple[float, object]]" = queue.Queue()
        self._frame_count = 0
        self._segment_index = 0
        self._debug_audio_dir: Path | None = None
        if config.debug_save_audio:
            from .config import APP_DIR

            self._debug_audio_dir = APP_DIR / "debug_audio" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    def start(self) -> None:
        self.on_status("Carregando modelo Whisper...")
        self._transcriber = Transcriber(
            model_size=self.config.whisper_model,
            device=self.config.whisper_device,
            compute_type=self.config.whisper_compute_type,
            language=self.config.language,
            playback_speed=self.config.playback_speed,
        )
        self._start_time = time.monotonic()
        self._stopping.clear()
        self._recorder.start()
        self._worker_thread = threading.Thread(target=self._run, daemon=True)
        self._worker_thread.start()
        self.on_status("Gravando e transcrevendo...")

    def _on_recorder_error(self, exc: Exception) -> None:
        self.on_status(f"Erro na captura de áudio: {exc}")

    def _run(self) -> None:
        assert self._transcriber is not None
        for frame in self._recorder.frames():
            if self._stopping.is_set():
                break

            self._frame_count += 1
            if self._frame_count % _LEVEL_REPORT_EVERY_N_FRAMES == 0:
                self.on_level(frame_rms(frame), self.config.energy_threshold)

            segment_start = time.monotonic() - self._start_time
            try:
                audio = self._chunker.push(frame)
                if audio is not None:
                    self._handle_segment(segment_start, audio)
            except Exception:  # noqa: BLE001 - um segmento ruim não pode derrubar a sessão inteira
                logger.exception("Falha ao processar um segmento de áudio; continuando a gravação")
                self.on_status("Aviso: falha ao transcrever um trecho (veja o log). Continuando...")

        try:
            final_audio = self._chunker.flush_remaining()
            if final_audio is not None:
                self._handle_segment(time.monotonic() - self._start_time, final_audio)
        except Exception:  # noqa: BLE001
            logger.exception("Falha ao processar o último trecho de áudio")

    def _handle_segment(self, approx_start_seconds: float, audio) -> None:
        assert self._transcriber is not None
        if self._debug_audio_dir is not None:
            self._segment_index += 1
            self._debug_audio_dir.mkdir(parents=True, exist_ok=True)
            wav_path = self._debug_audio_dir / f"segmento_{self._segment_index:03d}.wav"
            try:
                save_wav(wav_path, audio, self.config.sample_rate)
                logger.info("Áudio bruto do trecho salvo em: %s", wav_path)
            except Exception:  # noqa: BLE001 - diagnóstico não pode quebrar a transcrição
                logger.exception("Falha ao salvar áudio de diagnóstico")
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
        self.on_status("Gerando resumo (modelo local)...")
        try:
            summary = summarize(transcript_text, self.config)
        except SummarizerUnavailableError as exc:
            logger.exception("Falha ao gerar o resumo local")
            summary = f"_Resumo automático indisponível: {exc}_"
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
