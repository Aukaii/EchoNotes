"""Configuração do app, com persistência simples em JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

APP_DIR = Path.home() / ".echonotes"
CONFIG_PATH = APP_DIR / "config.json"
MODELS_DIR = APP_DIR / "models"

# Variantes disponíveis do modelo de resumo local (llama.cpp), da mais leve à
# mais precisa. Baixadas automaticamente na primeira vez que forem usadas.
LLM_VARIANTS = {
    "leve (1.5B, mais rápido)": {
        "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
        "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
    },
    "equilibrado (3B, recomendado)": {
        "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "file": "qwen2.5-3b-instruct-q4_k_m.gguf",
    },
}
DEFAULT_LLM_VARIANT = "equilibrado (3B, recomendado)"


@dataclass
class Config:
    output_dir: str = str(Path.home() / "Documents" / "EchoNotes")
    whisper_model: str = "large-v3-turbo"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    language: str = "pt"
    playback_speed: float = 1.0
    llm_variant: str = DEFAULT_LLM_VARIANT
    sample_rate: int = 16000
    silence_ms_to_close_segment: int = 700
    min_segment_ms: int = 300
    max_segment_ms: int = 6000
    energy_threshold: float = 0.010
    tags: list[str] = field(default_factory=lambda: ["transcricao", "aula"])
    auto_update_check: bool = True
    debug_save_audio: bool = False

    # Valor padrão de max_segment_ms antes da v0.4.2. Esse campo nunca foi
    # exposto nas Configurações (não há como o usuário tê-lo escolhido de
    # propósito), então um config.json antigo com exatamente esse valor é
    # migrado silenciosamente para o novo padrão — do contrário quem já usou
    # o app uma vez fica preso para sempre no valor antigo, mesmo depois de
    # atualizar, porque load() sempre prioriza o que está salvo em disco.
    _LEGACY_MAX_SEGMENT_MS = 15000

    @classmethod
    def load(cls) -> "Config":
        if CONFIG_PATH.exists():
            try:
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                filtered = {k: v for k, v in data.items() if k in known}
                if filtered.get("max_segment_ms") == cls._LEGACY_MAX_SEGMENT_MS:
                    filtered.pop("max_segment_ms")
                return cls(**{**asdict(cls()), **filtered})
            except (json.JSONDecodeError, TypeError):
                return cls()
        return cls()

    def save(self) -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
