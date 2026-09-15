"""Utilitários de processamento de áudio. Usa scipy (reamostragem
polifásica, com filtro anti-aliasing) em vez de interpolação linear
simples, que introduzia artefatos audíveis e provavelmente piorava a
transcrição em vez de ajudar."""
from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy.signal import resample_poly


def stretch_duration(audio: np.ndarray, factor: float) -> np.ndarray:
    """Estica a duração de `audio` multiplicando por `factor` (factor > 1
    produz um áudio mais longo/mais lento). Não preserva o tom (pitch) —
    usado só para compensar vídeos reproduzidos em velocidade acelerada
    (1.25x-2x) antes de transcrever: o Whisper foi treinado majoritariamente
    com fala em velocidade normal e perde precisão com fala muito rápida.
    Como esse áudio nunca é reproduzido (só transcrito), a mudança de tom
    não tem nenhum efeito perceptível para quem usa o app.
    """
    if factor == 1.0 or audio.size == 0:
        return audio
    ratio = Fraction(factor).limit_denominator(100)
    stretched = resample_poly(audio, up=ratio.numerator, down=ratio.denominator)
    return stretched.astype(np.float32)
