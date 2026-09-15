"""Transcrição local com faster-whisper (offline, gratuito, sem enviar áudio
para nenhum servidor)."""
from __future__ import annotations

import logging
import os

import numpy as np
from faster_whisper import WhisperModel

from .audio_utils import stretch_duration

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000


def _default_cpu_threads() -> int:
    """Deixa pelo menos 2 núcleos livres para a thread de captura de áudio
    (tempo real, sensível a atraso) não ser esmagada pela transcrição, que
    usa CPU pesado. Sem isso, a captura pode perder áudio de verdade sob
    carga, corrompendo a transcrição sem gerar nenhum erro visível."""
    total = os.cpu_count() or 4
    return max(1, total - 2)


class Transcriber:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "pt",
        playback_speed: float = 1.0,
        cpu_threads: int | None = None,
    ) -> None:
        self.language = language
        self.playback_speed = playback_speed
        if device == "cpu" and cpu_threads is None:
            cpu_threads = _default_cpu_threads()
        logger.info("Carregando Whisper (device=%s, cpu_threads=%s)", device, cpu_threads)
        self._model = WhisperModel(
            model_size, device=device, compute_type=compute_type, cpu_threads=cpu_threads or 0
        )

    def transcribe_segment(self, audio: np.ndarray) -> str:
        """Transcreve um trecho de áudio mono float32 (-1..1) em 16kHz."""
        if self.playback_speed != 1.0:
            original_s = audio.shape[0] / _SAMPLE_RATE
            audio = stretch_duration(audio, self.playback_speed)
            logger.info(
                "Compensando velocidade %.2fx: %.2fs capturados -> %.2fs enviados ao Whisper",
                self.playback_speed,
                original_s,
                audio.shape[0] / _SAMPLE_RATE,
            )
        segments, _info = self._model.transcribe(
            audio,
            language=self.language,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()
