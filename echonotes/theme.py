"""Paleta de cores 'roxo Obsidian' e aplicação do tema na interface (tkinter/ttk)."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

PURPLE = "#7C6FF0"
PURPLE_DARK = "#5B4FD1"
PURPLE_SOFT = "#EDEBFC"
PURPLE_DARKEST = "#1E1637"
BG = "#F6F4FC"
SURFACE = "#FFFFFF"
TEXT = "#241B3A"
TEXT_MUTED = "#6B6483"
BORDER = "#DFDAF5"
DANGER = "#D64550"
DANGER_DARK = "#B23540"

FONT_FAMILY = "Segoe UI"


def apply(root: tk.Tk) -> ttk.Style:
    root.configure(bg=BG)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass  # tema 'clam' deve existir no Tk padrão do Windows; se não, mantém o default

    style.configure(".", background=BG, foreground=TEXT, font=(FONT_FAMILY, 10))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=TEXT_MUTED)
    style.configure("TCheckbutton", background=BG, foreground=TEXT)

    style.configure("TEntry", fieldbackground=SURFACE, foreground=TEXT, bordercolor=BORDER, padding=4)
    style.configure(
        "TCombobox", fieldbackground=SURFACE, background=SURFACE, foreground=TEXT, bordercolor=BORDER
    )
    style.map("TCombobox", fieldbackground=[("readonly", SURFACE)])

    style.configure("TButton", background=PURPLE, foreground=SURFACE, padding=(10, 6), borderwidth=0)
    style.map("TButton", background=[("active", PURPLE_DARK), ("disabled", BORDER)])

    style.configure("TProgressbar", background=PURPLE, troughcolor=PURPLE_SOFT, borderwidth=0)

    style.configure("TScale", background=BG, troughcolor=PURPLE_SOFT)

    style.configure("Header.TFrame", background=PURPLE_DARKEST)
    style.configure("Header.TLabel", background=PURPLE_DARKEST, foreground=SURFACE)
    style.configure("HeaderMuted.TLabel", background=PURPLE_DARKEST, foreground=PURPLE_SOFT)

    style.configure("Update.TFrame", background=PURPLE_SOFT)
    style.configure("Update.TLabel", background=PURPLE_SOFT, foreground=PURPLE_DARKEST)

    style.configure("Card.TFrame", background=SURFACE)
    style.configure("Card.TLabel", background=SURFACE, foreground=TEXT)
    style.configure("CardMuted.TLabel", background=SURFACE, foreground=TEXT_MUTED)
    style.configure("CardTitle.TLabel", background=SURFACE, foreground=PURPLE_DARK, font=(FONT_FAMILY, 11, "bold"))

    return style


def make_card(parent) -> ttk.Frame:
    """Cria um 'card': moldura com fundo branco e borda fina sobre o fundo
    lavanda da página, para dar hierarquia visual às seções da tela."""
    outer = tk.Frame(parent, bg=BORDER)
    inner = ttk.Frame(outer, style="Card.TFrame", padding=14)
    inner.pack(fill="both", expand=True, padx=1, pady=1)
    return outer, inner
