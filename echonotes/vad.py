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
    max_segment_ms: int = 6000
    # Janela (no fim do buffer) onde procuramos o ponto mais silencioso para
    # cortar um segmento forçado (fala sem pausas de verdade). Mesmo fala
    # contínua tem micro-quedas de energia entre palavras/sílabas; cortar
    # exatamente nesse ponto em vez de num frame arbitrário evita partir uma
    # palavra ao meio, o que confunde muito o Whisper (ele passou a alucinar/
    # embaralhar o texto todo do trecho quando o corte caía no meio de uma
    # sílaba, mesmo com o áudio capturado perfeitamente íntegro).
    soft_cut_lookback_ms: int = 1000

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
                return self._flush(soft_cut=True)
            return None

        if not self._buffer:
            # Silêncio antes de qualquer fala começar: não há nada para
            # bufferizar ainda.
            return None

        # BUG CRÍTICO (corrigido aqui): um frame abaixo do limiar no meio de
        # um trecho que já começou NÃO pode ser descartado. Antes, esse
        # frame era simplesmente jogado fora (nunca ia pro buffer), e só a
        # contagem de silêncio avançava - então uma sílaba mais fraca, uma
        # pausa curta entre palavras ou uma consoante mais suave no meio de
        # uma frase arrancava um pedacinho real do áudio, colando as partes
        # vizinhas direto uma na outra. Repetido dezenas de vezes ao longo de
        # um trecho, isso produz um áudio literalmente picotado/recortado -
        # e por isso a transcrição saía com palavras sem nexo, mesmo com a
        # captura de áudio 100% íntegra: o Whisper estava transcrevendo
        # corretamente um áudio que já chegava até ele mutilado.
        self._buffer.append(frame)
        self._silence_ms += self.frame_ms
        if self._silence_ms >= self.silence_ms_to_close_segment:
            return self._flush(soft_cut=False)
        return None

    def flush_remaining(self) -> np.ndarray | None:
        """Deve ser chamado ao parar a gravação para não perder o último trecho."""
        if self._buffer:
            return self._flush(soft_cut=False)
        return None

    def _flush(self, soft_cut: bool) -> np.ndarray | None:
        if not self._buffer:
            self._speech_ms = 0
            self._silence_ms = 0
            return None

        cut_index = self._find_quietest_cut_point() if soft_cut else len(self._buffer)
        emitted, remainder = self._buffer[:cut_index], self._buffer[cut_index:]

        segment = np.concatenate(emitted) if emitted else None
        # O buffer agora pode conter frames de silêncio intercalados (pausas
        # curtas no meio da fala, ou o silêncio final que fechou o
        # segmento), então a duração de fala precisa ser recontada a partir
        # do conteúdo real, e não apenas do tamanho do buffer.
        finished_speech_ms = self._speech_ms_of(emitted)

        self._buffer = remainder
        self._speech_ms = self._speech_ms_of(remainder)
        self._silence_ms = 0

        if segment is None or finished_speech_ms < self.min_segment_ms:
            return None
        return segment

    def _speech_ms_of(self, frames: list[np.ndarray]) -> int:
        return sum(self.frame_ms for f in frames if frame_rms(f) > self.energy_threshold)

    def _find_quietest_cut_point(self) -> int:
        """Retorna o índice (exclusivo) onde cortar o buffer atual: o fim do
        frame de menor energia dentro da janela `soft_cut_lookback_ms` no fim
        do buffer, sem nunca deixar o segmento emitido menor que
        min_segment_ms."""
        lookback_frames = max(1, self.soft_cut_lookback_ms // self.frame_ms)
        min_frames = max(1, self.min_segment_ms // self.frame_ms)
        window_start = max(min_frames, len(self._buffer) - lookback_frames)
        if window_start >= len(self._buffer):
            return len(self._buffer)

        energies = [frame_rms(f) for f in self._buffer[window_start:]]
        quietest_offset = int(np.argmin(energies))
        return window_start + quietest_offset + 1
