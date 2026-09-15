import json

from echonotes import config as config_module
from echonotes.config import Config


def _use_tmp_config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    monkeypatch.setattr(config_module, "CONFIG_PATH", path)
    return path


def test_load_without_file_returns_defaults(tmp_path, monkeypatch):
    _use_tmp_config(tmp_path, monkeypatch)
    cfg = Config.load()
    assert cfg.max_segment_ms == 6000


def test_load_preserves_user_chosen_fields(tmp_path, monkeypatch):
    path = _use_tmp_config(tmp_path, monkeypatch)
    path.write_text(json.dumps({"energy_threshold": 0.0234, "language": "en"}), encoding="utf-8")
    cfg = Config.load()
    assert cfg.energy_threshold == 0.0234
    assert cfg.language == "en"


def test_load_migrates_legacy_max_segment_ms(tmp_path, monkeypatch):
    # Configs salvos antes da v0.4.2 têm max_segment_ms=15000 (o padrão
    # antigo, nunca exposto na interface). Como o usuário nunca escolheu
    # esse valor de propósito, ele deve ser silenciosamente atualizado para
    # o novo padrão em vez de ficar preso para sempre no valor antigo.
    path = _use_tmp_config(tmp_path, monkeypatch)
    path.write_text(json.dumps({"max_segment_ms": 15000}), encoding="utf-8")
    cfg = Config.load()
    assert cfg.max_segment_ms == Config().max_segment_ms
    assert cfg.max_segment_ms != 15000
