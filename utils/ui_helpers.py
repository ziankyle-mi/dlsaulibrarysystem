import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

def create_modal_window(parent, title, width, height, bg_color):
    """
    Creates a centered, non-resizable modal Toplevel window using CTk.
    """
    modal = ctk.CTkToplevel(parent)
    modal.title(title)
    modal.configure(fg_color=bg_color)
    modal.transient(parent)
    modal.grab_set()
    modal.resizable(False, False)

    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    modal.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    return modal

def add_form_field(container, label_text, bg_color, fg_color, show=None, font=("Segoe UI", 11), label_font=("Segoe UI", 10, "bold")):
    """
    Creates a standard CTkLabel and CTkEntry pair. Returns the CTkEntry widget.
    """
    ctk.CTkLabel(container, text=label_text, font=label_font,
                 fg_color=bg_color, text_color=fg_color).pack(anchor="w", pady=(8, 2))
    
    if show:
        entry = ctk.CTkEntry(container, font=font, show=show, height=36, border_width=1, corner_radius=6, text_color="#111827")
    else:
        entry = ctk.CTkEntry(container, font=font, height=36, border_width=1, corner_radius=6, text_color="#111827")
        
    entry.pack(fill="x", pady=(0, 2))
    return entry
