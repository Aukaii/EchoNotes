"""Detecção de fala baseada em energia (VAD simples, sem dependências nativas).

Não usamos webrtcvad para evitar problemas de compilação/roda-em-qualquer-lugar
no Windows; um VAD por energia é suficiente para segmentar frases de uma aula
gravada por loopback (sinal limpo, sem ruído de ambiente).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


def frame_rms(frame: np.ndarray) -> float:
    if frame.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(frame, dtype=np.float64))))


@dataclass
class SegmentChunker:
    """Recebe frames de áudio (mono, float32, -1..1) e agrupa trechos de fala
    contíguos em "segmentos" prontos para transcrever, delimitados por silêncio.
    """

    sample_rate: int
    frame_ms: int = 30
    energy_threshold: float = 0.010
    silence_ms_to_close_segment: int = 700
    min_segment_ms: int = 300
    max_segment_ms: int = 15000

    _buffer: list[np.ndarray] = field(default_factory=list, init=False)
    _silence_ms: int = field(default=0, init=False)
    _speech_ms: int = field(default=0, init=False)

    def push(self, frame: np.ndarray) -> np.ndarray | None:
        """Alimenta um frame de áudio. Retorna um segmento finalizado (np.ndarray)
        quando um trecho de fala é seguido por silêncio suficiente, ou quando a
        fala contínua atinge max_segment_ms (fala sem pausas nunca fecharia um
        segmento sozinha, o que impediria a transcrição ao vivo e degradaria
        muito a qualidade do Whisper em áudios muito longos).
        """
        is_speech = frame_rms(frame) > self.energy_threshold

        if is_speech:
            self._buffer.append(frame)
            self._speech_ms += self.frame_ms
            self._silence_ms = 0
            if self._speech_ms >= self.max_segment_ms:
                return self._flush()
            return None

        if self._buffer:
            self._silence_ms += self.frame_ms
            if self._silence_ms >= self.silence_ms_to_close_segment:
                return self._flush()
        return None

    def flush_remaining(self) -> np.ndarray | None:
        """Deve ser chamado ao parar a gravação para não perder o último trecho."""
        if self._buffer:
            return self._flush()
        return None

    def _flush(self) -> np.ndarray | None:
        segment = np.concatenate(self._buffer) if self._buffer else None
        finished_speech_ms = self._speech_ms
        self._buffer = []
        self._speech_ms = 0
        self._silence_ms = 0
        if segment is None or finished_speech_ms < self.min_segment_ms:
            return None
        return segment
