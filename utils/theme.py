from tkinter import *
from utils import sweetalert as messagebox
from utils import sweetalert
messagebox = sweetalert  # SweetAlert2-styled popups (see sweetalert.py)
from PIL import Image, ImageTk
import customtkinter as ctk
import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===================== SHARED COLOR PALETTE =====================
# Every screen should pull colors from here instead of redefining its own
# copy. That way a single palette tweak (e.g. rebranding) only needs to
# happen in one place.

PRIMARY = "#10312B"
PRIMARY_HOVER = "#1B5349"
WHITE = "#FFFFFF"
BLACK = "#000000"
LIGHT_BG = "#F9F9F9"
BORDER_GRAY = "#CCCCCC"
TEXT_GRAY = "#555555"

# ===================== SHARED FONTS =====================

LOGO_FONT = ("Segoe UI", 20, "bold")
LABEL_FONT = ("Segoe UI", 15, "bold")
ENTRY_FONT = ("Segoe UI", 18)
BUTTON_FONT = ("Segoe UI", 15, "bold")

# ===================== SIZES =====================

HEADER_HEIGHT = 60

LOGO_WIDTH = 320
LOGO_HEIGHT = 40

EXIT_WIDTH = 50
EXIT_HEIGHT = 50


# ===================== FUNCTIONS =====================

def exit_program(window):
    """Exit without asking for confirmation.
    
    The user requested direct transitions without prompts.
    """
    window.destroy()


def bind_mousewheel(scrollable_widget, target_canvas):
    """Cross-platform mouse-wheel scrolling.

    <MouseWheel> with event.delta only fires on Windows/macOS. Linux
    (X11) sends <Button-4>/<Button-5> instead, so without this, scrolling
    silently does nothing for a chunk of users.
    """

    def _on_windows_mac(event):
        step = -1 if event.delta > 0 else 1
        target_canvas.yview_scroll(step, "units")

    def _on_linux_up(event):
        target_canvas.yview_scroll(-1, "units")

    def _on_linux_down(event):
        target_canvas.yview_scroll(1, "units")

    scrollable_widget.bind_all("<MouseWheel>", _on_windows_mac)
    scrollable_widget.bind_all("<Button-4>", _on_linux_up)
    scrollable_widget.bind_all("<Button-5>", _on_linux_down)


def load_display_font(size, bold=True):
    """Best-effort cross-platform font for PIL-drawn text (e.g. avatar
    initials). "seguiui.ttf" only exists on Windows; on macOS/Linux this
    used to silently fall back to PIL's tiny built-in bitmap font, which
    looks broken at avatar sizes. This tries a short list of common
    system fonts before giving up.
    """
    from PIL import ImageFont

    candidates = [
        "seguisb.ttf" if bold else "seguiui.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()


def enable_responsive_resize(window, canvas, min_width=1024, min_height=640):
    """Lets a screen leave fullscreen (Escape) without being stuck at a
    fixed, un-resizable size. Also keeps the background canvas filling
    the window if the user resizes it.
    """
    window.resizable(True, True)
    window.minsize(min_width, min_height)

    def _on_resize(event):
        if event.widget is window:
            canvas.configure(width=event.width, height=event.height)

    window.bind("<Configure>", _on_resize)


def draw_background(window, canvas):
    """Draw white background."""

    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    canvas.create_rectangle(
        0,
        0,
        screen_w,
        screen_h,
        fill="white",
        outline=""
    )


def draw_header(window, canvas):
    """Draw top header."""

    screen_w = window.winfo_screenwidth()

    canvas.create_rectangle(
        0,
        0,
        screen_w,
        HEADER_HEIGHT,
        fill=PRIMARY,
        outline=""
    )

    logo = Image.open(os.path.join(BASE_DIR, "images", "dlsaulogos1.png"))
    logo = logo.resize(
        (LOGO_WIDTH, LOGO_HEIGHT),
        Image.Resampling.LANCZOS
    )

    photo = ImageTk.PhotoImage(logo)

    window.logo_photo = photo

    canvas.create_image(
        15,
        HEADER_HEIGHT // 2,
        image=photo,
        anchor="w"
    )


def draw_exit_button(window, canvas):
    """Draw exit button."""

    exit_img = Image.open(os.path.join(BASE_DIR, "images", "mikkiex.png"))
    exit_img = exit_img.resize(
        (EXIT_WIDTH, EXIT_HEIGHT),
        Image.Resampling.LANCZOS
    )

    photo = ImageTk.PhotoImage(exit_img)

    window.exit_photo = photo

    exit_btn = ctk.CTkButton(
        window,
        image=photo,
        text="",
        width=EXIT_WIDTH,
        height=EXIT_HEIGHT,
        fg_color=PRIMARY,
        hover_color=PRIMARY,
        cursor="hand2",
        command=lambda: exit_program(window)
    )

    canvas.create_window(
        window.winfo_screenwidth() - 20,
        HEADER_HEIGHT // 2,
        window=exit_btn,
        anchor="e"
    )


def build_header(window, canvas):
    """Draw the common layout for every form."""

    draw_background(window, canvas)
    draw_header(window, canvas)
    draw_exit_button(window, canvas)


# ===================== WINDOW TRANSITIONS =====================
# Small fade helpers so switching between screens feels like a polished
# cross-fade instead of a hard, instant cut. Every module launch/close in
# the system can call these instead of raw destroy()/withdraw() calls.

FADE_STEPS = 15
FADE_DELAY_MS = 20  # ~300ms total fade — smooth and polished, feels real

# ---- Modal-specific animation settings ----
MODAL_FADE_STEPS = 18   # smooth, noticeable fade for modals
MODAL_FADE_DELAY_MS = 22  # ~396ms total — natural, not laggy


def animate_modal_open(window, delay_ms=0):
    """Fade-in a Toplevel modal with a natural ease-in curve.

    Optional delay_ms adds a brief pause before the animation starts so
    fast successive UI events don't feel instant-jarring.
    """
    def _start():
        try:
            window.attributes("-alpha", 0.0)
        except Exception:
            return

        def step(count=0):
            progress = count / MODAL_FADE_STEPS
            alpha = progress * progress * (3 - 2 * progress)  # smoothstep
            try:
                window.attributes("-alpha", alpha)
            except Exception:
                return
            if count < MODAL_FADE_STEPS:
                window.after(MODAL_FADE_DELAY_MS, lambda: step(count + 1))

        step()

    if delay_ms > 0:
        window.after(delay_ms, _start)
    else:
        _start()


def animate_modal_close(window, on_complete=None):
    """Fade-out a Toplevel, then call on_complete (defaults to destroy)."""
    def step(count=0):
        progress = count / MODAL_FADE_STEPS
        alpha = 1.0 - (progress * progress * (3 - 2 * progress))
        try:
            window.attributes("-alpha", max(0.0, alpha))
        except Exception:
            if on_complete:
                on_complete()
            else:
                window.destroy()
            return
        if count < MODAL_FADE_STEPS:
            window.after(MODAL_FADE_DELAY_MS, lambda: step(count + 1))
        else:
            if on_complete:
                on_complete()
            else:
                window.destroy()

    step()


def fade_in(window, steps=FADE_STEPS, delay=FADE_DELAY_MS):
    """Fade a window from fully transparent to fully opaque."""

    try:
        window.attributes("-alpha", 0.0)
    except Exception:
        return  # Some platforms/window managers don't support alpha; skip quietly

    def step(count=0):
        alpha = min(1.0, count / steps)
        try:
            window.attributes("-alpha", alpha)
        except Exception:
            return
        if count < steps:
            window.after(delay, lambda: step(count + 1))

    step()


def fade_out(window, on_complete, steps=FADE_STEPS, delay=FADE_DELAY_MS):
    """Fade a window to transparent, then run on_complete (e.g. destroy/withdraw)."""

    def step(count=0):
        alpha = max(0.0, 1.0 - (count / steps))
        try:
            window.attributes("-alpha", alpha)
        except Exception:
            on_complete()
            return
        if count < steps:
            window.after(delay, lambda: step(count + 1))
        else:
            on_complete()

    step()
def setup_modern_treeview_style():
    from tkinter import ttk
    style = ttk.Style()
    
    # Modern colors
    BG_COLOR = "#FFFFFF"
    FG_COLOR = "#111827"
    SELECTED_BG = "#ECFDF5"
    SELECTED_FG = "#10312B"
    HEADER_BG = "#F8FAFC"
    HEADER_FG = "#64748B"
    
    style.theme_use("default")
    
    style.configure("Treeview", 
                    background=BG_COLOR,
                    foreground=FG_COLOR,
                    rowheight=55,
                    fieldbackground=BG_COLOR,
                    borderwidth=0,
                    font=("Segoe UI", 12))
                    
    style.configure("Treeview.Heading", 
                    background=HEADER_BG,
                    foreground=HEADER_FG,
                    font=("Segoe UI", 11, "bold"),
                    borderwidth=0,
                    padding=(10, 15))
                    
    style.map("Treeview", 
              background=[("selected", SELECTED_BG)],
              foreground=[("selected", SELECTED_FG)])
              
    style.map("Treeview.Heading", 
              background=[("active", "#F1F5F9")])
              
    # Remove ugly borders
    style.layout("Treeview", [('Treeview.treearea', {'sticky': 'nswe'})])
