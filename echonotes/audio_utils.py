"""Utilitários de processamento de áudio sem dependências pesadas (só numpy),
para poderem ser testados sem instalar faster-whisper/soundcard."""
from __future__ import annotations

import numpy as np


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
    new_len = max(1, int(round(audio.shape[0] * factor)))
    old_idx = np.linspace(0, audio.shape[0] - 1, num=audio.shape[0])
    new_idx = np.linspace(0, audio.shape[0] - 1, num=new_len)
    return np.interp(new_idx, old_idx, audio).astype(np.float32)
