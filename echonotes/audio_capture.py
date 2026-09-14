"""Captura o áudio que está saindo do Windows (loopback), ou seja, tudo que
toca pelos alto-falantes: navegador, players, videoconferência, etc.

Usa a biblioteca `soundcard`, que no Windows abre o dispositivo de saída
padrão em modo loopback via WASAPI (sem precisar de driver de áudio virtual).
"""
from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from typing import Callable

import numpy as np
import soundcard as sc

logger = logging.getLogger(__name__)


@dataclass
class LoopbackRecorder:
    """Grava o áudio de saída do sistema em uma thread separada e entrega
    frames de tamanho fixo (mono, float32, -1..1) por uma fila.
    """

    sample_rate: int = 16000
    frame_ms: int = 30
    on_error: Callable[[Exception], None] | None = None

    def __post_init__(self) -> None:
        self._frame_samples = int(self.sample_rate * self.frame_ms / 1000)
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
        try:
            speaker = sc.default_speaker()
            logger.info("Dispositivo de saída padrão: %s", speaker.name)
            mic = sc.get_microphone(id=str(speaker.name), include_loopback=True)
            with mic.recorder(samplerate=self.sample_rate) as recorder:
                logger.info("Loopback aberto com sucesso (samplerate=%d)", self.sample_rate)
                leftover = np.empty((0,), dtype=np.float32)
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=self._frame_samples)
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
