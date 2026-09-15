"""Captura o áudio que está saindo do Windows (loopback), ou seja, tudo que
toca pelos alto-falantes: navegador, players, videoconferência, etc.

Usa a biblioteca `soundcard`, que no Windows abre o dispositivo de saída
padrão em modo loopback via WASAPI (sem precisar de driver de áudio virtual).
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np
import soundcard as sc

logger = logging.getLogger(__name__)


@dataclass
class LoopbackRecorder:
    """Grava o áudio de saída do sistema em uma thread separada e entrega
    frames de tamanho fixo (mono, float32, -1..1) por uma fila.

    Lê em blocos maiores (`read_chunk_ms`) em vez de um frame por vez: cada
    chamada a `recorder.record()` bloqueia até ter os dados, então ler em
    blocos pequenos (ex.: 30ms) exige um ritmo de chamadas muito apertado —
    qualquer atraso do interpretador Python nesse meio tempo (ex.: a thread
    de transcrição consumindo CPU) arrisca estourar o buffer do WASAPI e
    perder áudio de verdade, o que corrompe a transcrição sem gerar erro
    nenhum. Blocos maiores dão bem mais folga.
    """

    sample_rate: int = 16000
    frame_ms: int = 30
    read_chunk_ms: int = 200
    on_error: Callable[[Exception], None] | None = None

    def __post_init__(self) -> None:
        self._frame_samples = int(self.sample_rate * self.frame_ms / 1000)
        self._read_samples = int(self.sample_rate * self.read_chunk_ms / 1000)
        self._queue: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def frames(self):
        """Gerador: produz frames enquanto a gravação estiver ativa (bloqueia
        aguardando o próximo frame)."""
        while not self._stop_event.is_set() or not self._queue.empty():
            try:
                yield self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

    def _run(self) -> None:
        self._raise_thread_priority()
        try:
            speaker = sc.default_speaker()
            logger.info("Dispositivo de saída padrão: %s", speaker.name)
            mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            with mic.recorder(samplerate=self.sample_rate) as recorder:
                logger.info(
                    "Loopback aberto com sucesso (samplerate=%d, leitura a cada %dms)",
                    self.sample_rate,
                    self.read_chunk_ms,
                )
                leftover = np.empty((0,), dtype=np.float32)
                expected_interval = self.read_chunk_ms / 1000
                while not self._stop_event.is_set():
                    read_start = time.monotonic()
                    data = recorder.record(numframes=self._read_samples)
                    read_elapsed = time.monotonic() - read_start
                    if read_elapsed > expected_interval * 2.5:
                        logger.warning(
                            "Leitura de áudio demorou %.2fs (esperado ~%.2fs) - risco de "
                            "perda de áudio por sobrecarga de CPU (provavelmente a "
                            "transcrição competindo por CPU)",
                            read_elapsed,
                            expected_interval,
                        )
                    if data.ndim > 1:
                        data = data.mean(axis=1)
                    data = data.astype(np.float32)
                    leftover = np.concatenate([leftover, data])
                    while leftover.shape[0] >= self._frame_samples:
                        self._queue.put(leftover[: self._frame_samples])
                        leftover = leftover[self._frame_samples :]
        except Exception as exc:  # noqa: BLE001 - precisa chegar até a GUI/log, nunca morrer em silêncio
            logger.exception("Falha na captura de áudio (loopback)")
            if self.on_error is not None:
                self.on_error(exc)

    @staticmethod
    def _raise_thread_priority() -> None:
        """Eleva a prioridade desta thread no Windows (técnica padrão para
        captura de áudio em tempo real), para que ela seja agendada mesmo
        com a CPU ocupada pela transcrição. Não crítico: se falhar (ex.:
        rodando fora do Windows), a captura continua funcionando normalmente,
        só fica mais vulnerável a perda de áudio sob carga pesada."""
        try:
            import ctypes

            THREAD_PRIORITY_TIME_CRITICAL = 15
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetThreadPriority(kernel32.GetCurrentThread(), THREAD_PRIORITY_TIME_CRITICAL)
        except Exception:  # noqa: BLE001
            logger.debug("Não foi possível elevar a prioridade da thread de captura", exc_info=True)
