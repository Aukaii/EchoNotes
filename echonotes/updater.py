"""Checagem e aplicação de atualizações automáticas, usando os Releases do
GitHub como fonte. Funciona de verdade (substitui o próprio executável)
apenas quando o app está empacotado como .exe (PyInstaller); rodando a partir
do código-fonte, só avisa que há uma versão nova disponível.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from . import __version__

GITHUB_REPO = "Aukaii/EchoNotes"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
ASSET_NAME = "EchoNotes.exe"


@dataclass
class UpdateInfo:
    version: str
    download_url: str
    notes: str


def _parse_version(tag: str) -> tuple[int, ...]:
    cleaned = tag.lstrip("vV")
    parts = []
    for p in cleaned.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_for_update(timeout: float = 10.0) -> UpdateInfo | None:
    """Retorna informações da nova versão se houver uma mais recente que a
    instalada, ou None (sem atualização, ou falha de rede/silenciosa)."""
    try:
        response = requests.get(API_URL, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException:
        return None

    latest_tag = str(data.get("tag_name", "")).strip()
    if not latest_tag:
        return None

    if _parse_version(latest_tag) <= _parse_version(__version__):
        return None

    asset_url = None
    for asset in data.get("assets", []):
        if asset.get("name") == ASSET_NAME:
            asset_url = asset.get("browser_download_url")
            break

    if not asset_url:
        return None

    return UpdateInfo(version=latest_tag, download_url=asset_url, notes=str(data.get("body", "")))


def is_frozen() -> bool:
    """True quando rodando como .exe empacotado pelo PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def download_and_apply_update(info: UpdateInfo, on_progress=None) -> None:
    """Baixa o novo .exe e agenda a substituição do executável atual, depois
    encerra o processo. Só funciona quando `is_frozen()` é True."""
    if not is_frozen():
        raise RuntimeError(
            "Atualização automática só está disponível na versão empacotada (.exe). "
            "Rodando a partir do código-fonte, atualize com `git pull`."
        )

    current_exe = Path(sys.executable)
    tmp_dir = Path(tempfile.mkdtemp(prefix="echonotes_update_"))
    new_exe = tmp_dir / ASSET_NAME

    with requests.get(info.download_url, stream=True, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        with open(new_exe, "wb") as f:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                f.write(chunk)
                downloaded += len(chunk)
                if on_progress:
                    on_progress(downloaded, total)

    # Script batch: espera o processo atual encerrar, troca o .exe e reabre.
    # Necessário porque o Windows não deixa sobrescrever um .exe em execução.
    updater_script = tmp_dir / "apply_update.bat"
    updater_script.write_text(
        "\n".join(
            [
                "@echo off",
                "timeout /t 2 /nobreak > NUL",
                f'copy /Y "{new_exe}" "{current_exe}" > NUL',
                f'start "" "{current_exe}"',
                f'rmdir /S /Q "{tmp_dir}"',
            ]
        ),
        encoding="utf-8",
    )

    subprocess.Popen(
        ["cmd", "/c", str(updater_script)],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
        close_fds=True,
    )
    sys.exit(0)
