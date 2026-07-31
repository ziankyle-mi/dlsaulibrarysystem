"""
sweetalert.py — SweetAlert2-styled popups for Tkinter (Modernized with CustomTkinter).

Drop-in replacement for tkinter.messagebox. Exposes the same function
names/signatures (showinfo, showerror, showwarning, askyesno,
askokcancel) so existing call sites don't need to change.
"""

import tkinter as tk
import customtkinter as ctk

PRIMARY = "#10312B"
PRIMARY_HOVER = "#1B5349"
WHITE = "#FFFFFF"
LIGHT_BG = "#F3F7F6"
BORDER_GRAY = "#E3EAE8"
TEXT_GRAY = "#52605D"
TEXT_MAIN = "#111827"

SUCCESS_COLOR = "#10B981"
ERROR_COLOR = "#EF4444"
WARNING_COLOR = "#F59E0B"
QUESTION_COLOR = PRIMARY

TITLE_FONT = ("Segoe UI", 18, "bold")
MESSAGE_FONT = ("Segoe UI", 12)
BUTTON_FONT = ("Segoe UI", 12, "bold")

CARD_WIDTH = 420
CARD_PAD = 30
ICON_RADIUS = 28


def _draw_icon(canvas, cx, cy, kind):
    """Draws the SweetAlert-style icon circle (check / x / ! / ?)."""
    color = {
        "success": SUCCESS_COLOR,
        "error": ERROR_COLOR,
        "warning": WARNING_COLOR,
        "question": QUESTION_COLOR,
    }.get(kind, QUESTION_COLOR)

    r = ICON_RADIUS
    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=color, width=3)

    if kind == "success":
        canvas.create_line(cx - 12, cy+2, cx - 4, cy + 10, fill=color, width=4, capstyle="round", joinstyle="round")
        canvas.create_line(cx - 4, cy + 10, cx + 14, cy - 10, fill=color, width=4, capstyle="round", joinstyle="round")
    elif kind == "error":
        canvas.create_line(cx - 10, cy - 10, cx + 10, cy + 10, fill=color, width=4, capstyle="round")
        canvas.create_line(cx - 10, cy + 10, cx + 10, cy - 10, fill=color, width=4, capstyle="round")
    elif kind == "warning":
        canvas.create_line(cx, cy - 12, cx, cy + 4, fill=color, width=4, capstyle="round")
        canvas.create_oval(cx - 3, cy + 10, cx + 3, cy + 16, fill=color, outline="")
    else:  # question
        canvas.create_text(cx, cy, text="📖", fill=color, font=("Segoe UI", 24, "bold"))


def _show(kind, title, message, parent=None, buttons=None):
    """
    Core modal builder using CustomTkinter.
    """
    root = parent or tk._default_root
    if buttons is None:
        buttons = [("OK", True, "primary")]

    top = ctk.CTkToplevel(root)
    top.withdraw()
    top.overrideredirect(True)
    top.attributes("-topmost", True)
    # Chroma key transparency trick for Windows frameless windows
    try:
        top.wm_attributes("-transparentcolor", "#000001")
        top.configure(fg_color="#000001")
    except:
        top.configure(fg_color=WHITE)

    result = {"value": None}

    def make_click(value):
        def _click(_event=None):
            result["value"] = value
            top.destroy()
        return _click

    card = ctk.CTkFrame(
        top, fg_color=WHITE,
        border_color=BORDER_GRAY, border_width=1,
        corner_radius=16
    )
    card.pack(fill="both", expand=True, padx=4, pady=4)

    # Padding inside card
    inner = ctk.CTkFrame(card, fg_color="transparent")
    inner.pack(fill="both", expand=True, padx=CARD_PAD, pady=CARD_PAD)

    # Icon Canvas
    icon_canvas = tk.Canvas(inner, width=ICON_RADIUS*2 + 10, height=ICON_RADIUS*2 + 10, bg=WHITE, highlightthickness=0)
    icon_canvas.pack(pady=(0, 15))
    _draw_icon(icon_canvas, ICON_RADIUS + 5, ICON_RADIUS + 5, kind)

    ctk.CTkLabel(inner, text=title, font=TITLE_FONT, text_color=TEXT_MAIN).pack(pady=(0, 10))
    ctk.CTkLabel(
        inner, text=message, font=MESSAGE_FONT, text_color=TEXT_GRAY,
        justify="center", wraplength=CARD_WIDTH - (CARD_PAD * 2)
    ).pack(pady=(0, 24))

    button_row = ctk.CTkFrame(inner, fg_color="transparent")
    button_row.pack(fill="x")
    
    # Calculate button spacing
    for index, (label, value, style) in enumerate(buttons):
        bg = PRIMARY if style == "primary" else LIGHT_BG
        fg = WHITE if style == "primary" else PRIMARY
        hover = PRIMARY_HOVER if style == "primary" else BORDER_GRAY

        btn = ctk.CTkButton(
            button_row, text=label, command=make_click(value),
            font=BUTTON_FONT, fg_color=bg, text_color=fg, hover_color=hover,
            corner_radius=8, height=40
        )
        btn.pack(side="left", fill="x", expand=True, padx=(0 if index == 0 else 8, 0))

    top.update_idletasks()

    win_w = max(CARD_WIDTH, top.winfo_reqwidth())
    win_h = top.winfo_reqheight()
    if root is not None:
        px = root.winfo_rootx()
        py = root.winfo_rooty()
        pw = root.winfo_width()
        ph = root.winfo_height()
        x = px + (pw - win_w) // 2
        y_pos = py + (ph - win_h) // 2
    else:
        sw = top.winfo_screenwidth()
        sh = top.winfo_screenheight()
        x = (sw - win_w) // 2
        y_pos = (sh - win_h) // 2

    top.geometry(f"{win_w}x{win_h}+{x}+{y_pos}")
    top.deiconify()
    top.lift()
    top.focus_force()

    try:
        top.attributes("-alpha", 0.0)
        top.update_idletasks()
        for i in range(1, 11):
            top.attributes("-alpha", i / 10)
            top.update()
            top.after(10)
    except Exception:
        pass

    top.grab_set()
    top.bind("<Return>", lambda e: make_click(buttons[0][1])())
    top.bind("<Escape>", lambda e: make_click(buttons[-1][1] if len(buttons) > 1 else None)())
    top.protocol("WM_DELETE_WINDOW", make_click(None))

    top.wait_window()
    return result["value"]


# ===================== messagebox-compatible API =====================

def showinfo(title, message, parent=None, **kwargs):
    return _show("success", title, message, parent, [("OK", True, "primary")])

def showerror(title, message, parent=None, **kwargs):
    return _show("error", title, message, parent, [("OK", True, "primary")])

def showwarning(title, message, parent=None, **kwargs):
    return _show("warning", title, message, parent, [("OK", True, "primary")])

def askyesno(title, message, parent=None, **kwargs):
    result = _show("question", title, message, parent,
                    [("No", False, "secondary"), ("Yes", True, "primary")])
    return bool(result)

def askokcancel(title, message, parent=None, **kwargs):
    result = _show("question", title, message, parent,
                    [("Cancel", False, "secondary"), ("OK", True, "primary")])
    return bool(result)
