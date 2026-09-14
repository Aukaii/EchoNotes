"""Interface gráfica simples (tkinter, incluso no Python padrão do Windows)."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .app import TranscriptionSession
from .config import Config


class MainWindow:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config = Config.load()
        self.session: TranscriptionSession | None = None
        self._recording = False

        root.title("transcreveTexto")
        root.geometry("720x560")
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_widgets()

    def _build_widgets(self) -> None:
        pad = {"padx": 8, "pady": 4}

        top = ttk.Frame(self.root)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Título da aula:").grid(row=0, column=0, sticky="w")
        self.title_var = tk.StringVar(value="Aula sem título")
        ttk.Entry(top, textvariable=self.title_var, width=50).grid(row=0, column=1, sticky="we", padx=4)

        ttk.Label(top, text="Pasta de destino (vault do Obsidian):").grid(row=1, column=0, sticky="w")
        self.output_dir_var = tk.StringVar(value=self.config.output_dir)
        ttk.Entry(top, textvariable=self.output_dir_var, width=50).grid(row=1, column=1, sticky="we", padx=4)
        ttk.Button(top, text="Escolher...", command=self._choose_dir).grid(row=1, column=2)

        ttk.Label(top, text="Modelo Whisper:").grid(row=2, column=0, sticky="w")
        self.whisper_model_var = tk.StringVar(value=self.config.whisper_model)
        ttk.Combobox(
            top,
            textvariable=self.whisper_model_var,
            values=["tiny", "base", "small", "medium", "large-v3"],
            state="readonly",
            width=15,
        ).grid(row=2, column=1, sticky="w")

        ttk.Label(top, text="Modelo Ollama (resumo):").grid(row=3, column=0, sticky="w")
        self.ollama_model_var = tk.StringVar(value=self.config.ollama_model)
        ttk.Entry(top, textvariable=self.ollama_model_var, width=25).grid(row=3, column=1, sticky="w")

        top.columnconfigure(1, weight=1)

        control = ttk.Frame(self.root)
        control.pack(fill="x", **pad)
        self.start_button = ttk.Button(control, text="Iniciar gravação", command=self._start)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(control, text="Parar e salvar", command=self._stop, state="disabled")
        self.stop_button.pack(side="left", padx=8)

        self.status_var = tk.StringVar(value="Pronto.")
        ttk.Label(self.root, textvariable=self.status_var, foreground="#555").pack(fill="x", **pad)

        ttk.Label(self.root, text="Transcrição ao vivo:").pack(anchor="w", **pad)
        self.transcript_box = tk.Text(self.root, wrap="word", state="disabled")
        self.transcript_box.pack(fill="both", expand=True, **pad)

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

    def _start(self) -> None:
        self.config.output_dir = self.output_dir_var.get()
        self.config.whisper_model = self.whisper_model_var.get()
        self.config.ollama_model = self.ollama_model_var.get()
        self.config.save()

        self.transcript_box.configure(state="normal")
        self.transcript_box.delete("1.0", "end")
        self.transcript_box.configure(state="disabled")

        self.session = TranscriptionSession(
            self.config, on_partial_text=self._append_transcript, on_status=self._set_status
        )

        def do_start() -> None:
            try:
                self.session.start()
            except Exception as exc:  # noqa: BLE001 - mostra qualquer erro de captura/modelo ao usuário
                self._set_status(f"Erro ao iniciar: {exc}")
                self.root.after(0, lambda: self._set_recording_state(False))

        self._set_recording_state(True)
        threading.Thread(target=do_start, daemon=True).start()

    def _set_recording_state(self, recording: bool) -> None:
        self._recording = recording
        self.start_button.configure(state="disabled" if recording else "normal")
        self.stop_button.configure(state="normal" if recording else "disabled")

    def _stop(self) -> None:
        if self.session is None:
            return
        self._set_recording_state(False)

        def do_stop() -> None:
            try:
                path = self.session.stop_and_save(self.title_var.get())
                self._set_status(f"Salvo em: {path}")
                self.root.after(0, lambda: messagebox.showinfo("Concluído", f"Nota salva em:\n{path}"))
            except Exception as exc:  # noqa: BLE001
                self._set_status(f"Erro ao salvar: {exc}")

        threading.Thread(target=do_stop, daemon=True).start()

    def _on_close(self) -> None:
        if self._recording and self.session is not None:
            if not messagebox.askyesno("Gravação em andamento", "Parar a gravação e sair?"):
                return
            self.session.stop_and_save(self.title_var.get())
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
