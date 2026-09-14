"""Interface gráfica (tkinter, incluso no Python padrão do Windows).

Pensada para ser simples de usar: a tela principal só tem o essencial
(título, pasta de destino, iniciar/parar); tudo o que é técnico fica
escondido em "Configurações avançadas". Na primeira execução, o app baixa
sozinho o modelo de resumo (sem precisar instalar nada à parte).
"""
from __future__ import annotations

import logging
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .app import TranscriptionSession
from .config import LLM_VARIANTS, Config
from .logging_setup import LOG_PATH, setup_logging
from .model_manager import is_llm_model_ready, ensure_llm_model
from .transcriber import Transcriber
from . import updater

logger = logging.getLogger(__name__)

UPDATE_CHECK_INTERVAL_MS = 6 * 60 * 60 * 1000  # 6 horas


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: "MainWindow") -> None:
        super().__init__(parent.root)
        self.parent = parent
        self.title("Configurações avançadas")
        self.resizable(False, False)
        self.transient(parent.root)
        self.grab_set()

        pad = {"padx": 10, "pady": 6}
        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, **pad)

        ttk.Label(frame, text="Qualidade da transcrição (Whisper):").grid(row=0, column=0, sticky="w")
        self.whisper_var = tk.StringVar(value=parent.config.whisper_model)
        ttk.Combobox(
            frame, textvariable=self.whisper_var,
            values=["tiny", "base", "small", "medium", "large-v3"],
            state="readonly", width=20,
        ).grid(row=0, column=1, sticky="w", padx=6)

        ttk.Label(frame, text="Modelo de resumo (LLM local):").grid(row=1, column=0, sticky="w")
        self.llm_var = tk.StringVar(value=parent.config.llm_variant)
        ttk.Combobox(
            frame, textvariable=self.llm_var,
            values=list(LLM_VARIANTS.keys()),
            state="readonly", width=28,
        ).grid(row=1, column=1, sticky="w", padx=6)

        ttk.Label(frame, text="Limiar de detecção de fala:").grid(row=2, column=0, sticky="w")
        self.energy_var = tk.DoubleVar(value=parent.config.energy_threshold)
        self.energy_value_label = ttk.Label(frame, text=f"{parent.config.energy_threshold:.4f}", width=8)
        ttk.Scale(
            frame,
            from_=0.002,
            to=0.05,
            variable=self.energy_var,
            orient="horizontal",
            length=160,
            command=lambda _v: self.energy_value_label.configure(text=f"{self.energy_var.get():.4f}"),
        ).grid(row=2, column=1, sticky="w", padx=6)
        self.energy_value_label.grid(row=2, column=2, sticky="w")
        ttk.Label(
            frame,
            text="Mais à esquerda = detecta sons mais baixos. Veja o nível ao\n"
            "vivo na tela principal durante a gravação para calibrar.",
            foreground="#777",
            font=("Segoe UI", 8),
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 6))

        self.auto_update_var = tk.BooleanVar(value=parent.config.auto_update_check)
        ttk.Checkbutton(
            frame, text="Verificar atualizações automaticamente", variable=self.auto_update_var
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(6, 0))

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", **pad)
        ttk.Button(buttons, text="Salvar", command=self._save).pack(side="right")
        ttk.Button(buttons, text="Cancelar", command=self.destroy).pack(side="right", padx=6)

    def _save(self) -> None:
        cfg = self.parent.config
        cfg.whisper_model = self.whisper_var.get()
        cfg.llm_variant = self.llm_var.get()
        cfg.energy_threshold = round(self.energy_var.get(), 4)
        cfg.auto_update_check = self.auto_update_var.get()
        cfg.save()
        self.destroy()


class FirstRunDialog(tk.Toplevel):
    """Mostrado apenas quando o modelo de resumo ainda não foi baixado."""

    def __init__(self, parent: "MainWindow", on_done) -> None:
        super().__init__(parent.root)
        self.title("Preparando o EchoNotes")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # não deixa fechar durante o download
        self.transient(parent.root)
        self.grab_set()

        self.parent = parent
        self.on_done = on_done

        pad = {"padx": 20, "pady": 10}
        ttk.Label(
            self,
            text="Preparando tudo para o primeiro uso...\nIsso só acontece uma vez.",
            justify="center",
        ).pack(**pad)

        self.status_var = tk.StringVar(value="Baixando modelo de resumo local...")
        ttk.Label(self, textvariable=self.status_var).pack(**pad)

        self.progress = ttk.Progressbar(self, length=320, mode="determinate", maximum=100)
        self.progress.pack(**pad)

        threading.Thread(target=self._prepare, daemon=True).start()

    def _prepare(self) -> None:
        def on_progress(done: int, total: int) -> None:
            pct = (done / total * 100) if total else 0
            mb_done, mb_total = done / (1024 * 1024), total / (1024 * 1024)
            self.after(0, lambda: self.progress.configure(value=pct))
            self.after(
                0,
                lambda: self.status_var.set(
                    f"Baixando modelo de resumo... {mb_done:.0f} MB / {mb_total:.0f} MB"
                ),
            )

        try:
            ensure_llm_model(self.parent.config.llm_variant, on_progress=on_progress)
            self.after(0, lambda: self.status_var.set("Preparando modelo de transcrição (Whisper)..."))
            self.after(0, lambda: self.progress.configure(mode="indeterminate"))
            self.after(0, self.progress.start)
            Transcriber(
                model_size=self.parent.config.whisper_model,
                device=self.parent.config.whisper_device,
                compute_type=self.parent.config.whisper_compute_type,
                language=self.parent.config.language,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha na preparação inicial (download de modelos)")
            self.after(0, lambda: messagebox.showerror("Erro na preparação", str(exc)))
        finally:
            self.after(0, self._finish)

    def _finish(self) -> None:
        self.grab_release()
        self.destroy()
        self.on_done()


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = Config.load()
        self.session: TranscriptionSession | None = None
        self._recording = False

        root.title(f"EchoNotes v{__version__}")
        root.geometry("760x600")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()

        if is_llm_model_ready(self.config.llm_variant):
            self._after_ready()
        else:
            self.root.withdraw()
            root.after(100, lambda: FirstRunDialog(self, self._show_main_after_first_run))

    def _show_main_after_first_run(self) -> None:
        self.root.deiconify()
        self._after_ready()

    def _after_ready(self) -> None:
        if self.config.auto_update_check:
            threading.Thread(target=self._check_update_background, daemon=True).start()
            self.root.after(UPDATE_CHECK_INTERVAL_MS, self._schedule_periodic_update_check)

    def _schedule_periodic_update_check(self) -> None:
        threading.Thread(target=self._check_update_background, daemon=True).start()
        self.root.after(UPDATE_CHECK_INTERVAL_MS, self._schedule_periodic_update_check)

    def _check_update_background(self) -> None:
        info = updater.check_for_update()
        if info is not None:
            self.root.after(0, lambda: self._show_update_banner(info))

    def _show_update_banner(self, info: "updater.UpdateInfo") -> None:
        self.update_banner.configure(text=f"Nova versão disponível: {info.version}")
        self.update_button.configure(command=lambda: self._apply_update(info))
        self.update_frame.pack(fill="x", before=self.top_frame)

    def _apply_update(self, info: "updater.UpdateInfo") -> None:
        if not updater.is_frozen():
            messagebox.showinfo(
                "Atualização",
                "Atualização automática só funciona na versão instalada (.exe).\n"
                "Rodando a partir do código-fonte, atualize com `git pull`.",
            )
            return
        if not messagebox.askyesno("Atualizar", f"Baixar e instalar a versão {info.version} agora?"):
            return

        progress_win = tk.Toplevel(self.root)
        progress_win.title("Atualizando...")
        progress_win.protocol("WM_DELETE_WINDOW", lambda: None)
        status_var = tk.StringVar(value="Baixando atualização...")
        ttk.Label(progress_win, textvariable=status_var).pack(padx=20, pady=10)
        bar = ttk.Progressbar(progress_win, length=300, maximum=100)
        bar.pack(padx=20, pady=10)

        def on_progress(done: int, total: int) -> None:
            pct = (done / total * 100) if total else 0
            self.root.after(0, lambda: bar.configure(value=pct))

        def do_update() -> None:
            try:
                updater.download_and_apply_update(info, on_progress=on_progress)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha ao aplicar atualização automática")
                self.root.after(0, lambda: messagebox.showerror("Erro ao atualizar", str(exc)))
                self.root.after(0, progress_win.destroy)

        threading.Thread(target=do_update, daemon=True).start()

    def _build_widgets(self) -> None:
        pad = {"padx": 10, "pady": 6}

        self.update_frame = ttk.Frame(self.root, style="Update.TFrame")
        self.update_banner = ttk.Label(self.update_frame, text="")
        self.update_banner.pack(side="left", padx=10, pady=4)
        self.update_button = ttk.Button(self.update_frame, text="Atualizar agora")
        self.update_button.pack(side="right", padx=10, pady=4)
        # update_frame só é exibido (.pack) quando uma atualização é encontrada

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)
        self.top_frame = top

        ttk.Label(top, text="Título da aula:").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="Aula sem título")
        ttk.Entry(top, textvariable=self.title_var, font=("Segoe UI", 11)).grid(
            row=0, column=1, sticky="we", padx=6
        )

        ttk.Label(top, text="Salvar em:").grid(row=1, column=0, sticky="w")
        self.output_dir_var = tk.StringVar(value=self.config.output_dir)
        ttk.Entry(top, textvariable=self.output_dir_var).grid(row=1, column=1, sticky="we", padx=6)
        ttk.Button(top, text="Escolher pasta...", command=self._choose_dir).grid(row=1, column=2)

        top.columnconfigure(1, weight=1)

        control = ttk.Frame(self.root)
        control.pack(fill="x", **pad)
        self.toggle_button = tk.Button(
            control,
            text="▶  Iniciar gravação",
            command=self._toggle_recording,
            font=("Segoe UI", 13, "bold"),
            bg="#2e7d32",
            fg="white",
            activebackground="#1b5e20",
            activeforeground="white",
            height=2,
        )
        self.toggle_button.pack(side="left", fill="x", expand=True)
        ttk.Button(control, text="⚙ Configurações", command=self._open_settings).pack(side="left", padx=10)

        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(self.root, textvariable=self.status_var, foreground="#555").pack(fill="x", **pad)

        level_frame = ttk.Frame(self.root)
        level_frame.pack(fill="x", **pad)
        ttk.Label(level_frame, text="Nível de áudio:").pack(side="left")
        self.level_bar = ttk.Progressbar(level_frame, length=200, maximum=0.05, mode="determinate")
        self.level_bar.pack(side="left", padx=6)
        self.level_label_var = tk.StringVar(value="-- (limiar: --)")
        ttk.Label(level_frame, textvariable=self.level_label_var, foreground="#777").pack(side="left")

        ttk.Label(self.root, text="Transcrição ao vivo:").pack(anchor="w", **pad)
        self.transcript_box = tk.Text(self.root, wrap="word", state="disabled", font=("Segoe UI", 10))
        self.transcript_box.pack(fill="both", expand=True, **pad)

    def _open_settings(self) -> None:
        SettingsDialog(self)

    def _choose_dir(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.output_dir_var.get())
        if chosen:
            self.output_dir_var.set(chosen)

    def _append_transcript(self, text: str, start_seconds: float) -> None:
        def do_append() -> None:
            self.transcript_box.configure(state="normal")
            self.transcript_box.insert("end", f"{text}\n")
            self.transcript_box.see("end")
            self.transcript_box.configure(state="disabled")

        self.root.after(0, do_append)

    def _set_status(self, status: str) -> None:
        self.root.after(0, lambda: self.status_var.set(status))

    def _on_level(self, level: float, threshold: float) -> None:
        def do_update() -> None:
            self.level_bar.configure(value=min(level, 0.05))
            marker = "🔊 fala" if level > threshold else "silêncio"
            self.level_label_var.set(f"{level:.4f} (limiar: {threshold:.4f}) — {marker}")

        self.root.after(0, do_update)

    def _toggle_recording(self) -> None:
        if self._recording:
            self._stop()
        else:
            self._start()

    def _start(self) -> None:
        self.config.output_dir = self.output_dir_var.get()
        self.config.save()

        self.transcript_box.configure(state="normal")
        self.transcript_box.delete("1.0", "end")
        self.transcript_box.configure(state="disabled")

        self.session = TranscriptionSession(
            self.config,
            on_partial_text=self._append_transcript,
            on_status=self._set_status,
            on_level=self._on_level,
        )

        def do_start() -> None:
            try:
                self.session.start()
                self.root.after(0, lambda: self._set_recording_state(True))
            except Exception as exc:  # noqa: BLE001 - mostra qualquer erro de captura/modelo ao usuário
                logger.exception("Falha ao iniciar a gravação")
                self._set_status(f"Erro ao iniciar: {exc}")
                self.root.after(0, lambda: self._set_recording_state(False))

        self.toggle_button.configure(state="disabled")
        threading.Thread(target=do_start, daemon=True).start()

    def _set_recording_state(self, recording: bool) -> None:
        self._recording = recording
        if recording:
            self.toggle_button.configure(text="■  Parar e salvar", bg="#c62828", activebackground="#8e0000")
        else:
            self.toggle_button.configure(text="▶  Iniciar gravação", bg="#2e7d32", activebackground="#1b5e20")
        self.toggle_button.configure(state="normal")

    def _stop(self) -> None:
        if self.session is None:
            return
        self.toggle_button.configure(state="disabled")

        def do_stop() -> None:
            try:
                path = self.session.stop_and_save(self.title_var.get())
                self._set_status(f"Salvo em: {path}")
                self.root.after(0, lambda: messagebox.showinfo("Concluído", f"Nota salva em:\n{path}"))
            except Exception as exc:  # noqa: BLE001
                logger.exception("Falha ao finalizar e salvar a gravação")
                self._set_status(f"Erro ao salvar: {exc}")
            finally:
                self.root.after(0, lambda: self._set_recording_state(False))

        threading.Thread(target=do_stop, daemon=True).start()

    def _on_close(self) -> None:
        if self._recording and self.session is not None:
            if not messagebox.askyesno("Gravação em andamento", "Parar a gravação e sair?"):
                return
            self.session.stop_and_save(self.title_var.get())
        self.root.destroy()


def _report_callback_exception(exc, val, tb) -> None:
    """Substitui o handler padrão do Tkinter, que só imprime no console
    (invisível no .exe empacotado com --noconsole)."""
    logger.error("Exceção não tratada em um callback do Tkinter", exc_info=(exc, val, tb))
    messagebox.showerror("Erro inesperado", f"{val}\n\nDetalhes em: {LOG_PATH}")


def main() -> None:
    setup_logging()
    logger.info("Iniciando EchoNotes v%s", __version__)
    root = tk.Tk()
    root.report_callback_exception = _report_callback_exception
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
