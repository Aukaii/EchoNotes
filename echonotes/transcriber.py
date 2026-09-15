"""Transcrição local com faster-whisper (offline, gratuito, sem enviar áudio
para nenhum servidor)."""
from __future__ import annotations

import logging

import numpy as np
from faster_whisper import WhisperModel

from .audio_utils import stretch_duration

logger = logging.getLogger(__name__)

_SAMPLE_RATE = 16000


class Transcriber:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "pt",
        playback_speed: float = 1.0,
    ) -> None:
        self.language = language
        self.playback_speed = playback_speed
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)

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
