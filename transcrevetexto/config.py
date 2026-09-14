"""Configuração do app, com persistência simples em JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_DIR = Path.home() / ".transcrevetexto"
CONFIG_PATH = APP_DIR / "config.json"


@dataclass
class Config:
    output_dir: str = str(Path.home() / "Documents" / "transcreveTexto")
    whisper_model: str = "small"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    language: str = "pt"
    ollama_model: str = "llama3.1"
    ollama_url: str = "http://localhost:11434"
    sample_rate: int = 16000
    silence_ms_to_close_segment: int = 700
    min_segment_ms: int = 300
    energy_threshold: float = 0.010
    tags: list[str] = field(default_factory=lambda: ["transcricao", "aula"])

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                return cls(**{**asdict(cls()), **data})
            except (json.JSONDecodeError, TypeError):
                return cls()
        return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
