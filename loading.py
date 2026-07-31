# ==========================================
# 1. IMPORTS & CONFIGURATION
# ==========================================
import customtkinter as ctk
from tkinter import Canvas
from PIL import Image, ImageTk, ImageFilter, ImageEnhance
import sys
import subprocess
import os

try:
    from utils import theme
except ImportError as e:
    theme = None

# Initialize CustomTkinter globally
ctk.set_appearance_mode("Dark")

# ==========================================
# 2. CONSTANTS & STYLING
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PRIMARY = "#10312B"
PRIMARY_HOVER = "#1A4A41"
WHITE = "#FFFFFF"
LIGHT_GRAY = "#DDDDDD"
BLACK = "#000000"
GOLD = "#F59E0B"
GOLD_HOVER = "#FCD34D"
DARK_TEXT = "#111827"

# We use standard tuples for fonts to avoid initialization errors before root window exists
PRE_TITLE_FONT = ("Segoe UI", 18)
HERO_FONT = ("Segoe UI", 56, "bold")
SUB_TITLE_FONT = ("Segoe UI", 16)
BUTTON_FONT = ("Segoe UI", 16, "bold")
FOOTER_FONT = ("Segoe UI", 11)

HEADER_HEIGHT = 60
EXIT_WIDTH = 50
EXIT_HEIGHT = 50
LOGO_WIDTH = 320
LOGO_HEIGHT = 40
BUTTON_WIDTH = 350
BUTTON_HEIGHT = 60

# ==========================================
# 3. WINDOW SETUP
# ==========================================
loading = ctk.CTk()
loading.attributes("-fullscreen", True)
loading.title("Loading Screen")

loading.bind(
    "<Escape>",
    lambda event: (
        theme.exit_program(loading) if theme else (loading.destroy(), sys.exit())
    ),
)
loading.bind("<Return>", lambda event: enter_main())

loading.update()
SCREEN_W = loading.winfo_screenwidth()
SCREEN_H = loading.winfo_screenheight()

canvas = Canvas(loading, width=SCREEN_W, height=SCREEN_H, bd=0, highlightthickness=0)
canvas.pack(fill="both", expand=True)


# ==========================================
# 4. CORE FUNCTIONS
# ==========================================
def enter_main():
    loading.withdraw()  # Hide immediately to yield focus to the new window
    subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "login.py")])
    loading.after(500, loading.destroy)


def draw_exit_button():
    exit_btn = ctk.CTkButton(
        loading,
        text="✕",
        font=("Segoe UI", 20, "bold"),
        width=40,
        height=40,
        corner_radius=8,
        fg_color=PRIMARY,
        text_color="white",
        hover_color="#E81123",
        command=lambda: (
            theme.exit_program(loading) if theme else (loading.destroy(), sys.exit())
        ),
    )
    canvas.create_window(SCREEN_W - 20, HEADER_HEIGHT // 2, window=exit_btn, anchor="e")


# ==========================================
# 5. BACKGROUND CYCLER
# ==========================================
BACKGROUND_IMAGES = [
    os.path.join(BASE_DIR, "images", "Pic1.png"),
    os.path.join(BASE_DIR, "images", "Pic2.png"),
    os.path.join(BASE_DIR, "images", "outside3.png"),
    os.path.join(BASE_DIR, "images", "outside.png"),
    os.path.join(BASE_DIR, "images", "outside2.png"),
]

current_bg_index = 0


def cycle_background():
    global current_bg_index
    bg = Image.open(BACKGROUND_IMAGES[current_bg_index])
    bg = bg.filter(ImageFilter.GaussianBlur(radius=4))

    # Smooth darkening
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.35)

    bg = bg.resize((SCREEN_W, SCREEN_H))

    photo = ImageTk.PhotoImage(bg)
    loading.bg_photo = photo

    canvas.delete("bg")
    canvas.create_image(0, 0, image=photo, anchor="nw", tags="bg")
    canvas.tag_lower("bg")

    current_bg_index = (current_bg_index + 1) % len(BACKGROUND_IMAGES)
    loading.after(10000, cycle_background)


def draw_header():
    canvas.create_rectangle(0, 0, SCREEN_W, HEADER_HEIGHT, fill=PRIMARY, outline="")
    canvas.create_text(
        SCREEN_W - 100,
        HEADER_HEIGHT // 2,
        text="Library Hours: 7:00 AM – 5:00 PM  |  Help",
        font=("Segoe UI", 12),
        fill="#DDDDDD",
        anchor="e",
    )


def draw_logo():
    logo = Image.open(os.path.join(BASE_DIR, "images", "dlsaulogos1.png"))
    logo = logo.resize((LOGO_WIDTH, LOGO_HEIGHT), Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(logo)
    loading.logo_photo = photo
    canvas.create_image(15, HEADER_HEIGHT // 2, image=photo, anchor="w")


def draw_title():
    # Pre-title
    canvas.create_text(
        SCREEN_W / 2,
        (SCREEN_H / 2) - 110,
        text="De La Salle Araneta University",
        font=PRE_TITLE_FONT,
        fill="#E5E7EB",
        tags="title_main",
    )
    # Hero Shadow
    canvas.create_text(
        (SCREEN_W / 2) + 3,
        (SCREEN_H / 2) - 47,
        text="Araneta Library Information System",
        font=HERO_FONT,
        fill="black",
        tags="title_shadow",
    )
    # Hero
    canvas.create_text(
        SCREEN_W / 2,
        (SCREEN_H / 2) - 50,
        text="Araneta Library Information System",
        font=HERO_FONT,
        fill=WHITE,
        tags="title_main",
    )
    # Subtitle
    canvas.create_text(
        SCREEN_W / 2,
        (SCREEN_H / 2) + 20,
        text="Search books, pay fines, and access digital resources online.",
        font=SUB_TITLE_FONT,
        fill="#9CA3AF",
        tags="title_main",
    )


def show_enter_button():
    canvas.delete("loading_ui")
    button = ctk.CTkButton(
        loading,
        text="Access Library Portal",
        font=BUTTON_FONT,
        fg_color=GOLD,
        text_color=DARK_TEXT,
        hover_color=GOLD_HOVER,
        width=BUTTON_WIDTH,
        height=BUTTON_HEIGHT,
        corner_radius=8,
        cursor="hand2",
        command=enter_main,
    )
    canvas.create_window(SCREEN_W / 2, (SCREEN_H / 2) + 120, window=button)


def start_loading_animation():
    global progress_bar
    progress_bar = ctk.CTkProgressBar(
        loading,
        width=400,
        height=12,
        corner_radius=10,
        fg_color="#333333",
        progress_color=GOLD,
    )
    progress_bar.set(0)
    canvas.create_window(
        SCREEN_W / 2, (SCREEN_H / 2) + 120, window=progress_bar, tags="loading_ui"
    )

    # Simulate loading over 2 seconds (40 steps of 50ms)
    step = 0

    def update_progress():
        nonlocal step
        step += 1
        progress_bar.set(step / 40.0)
        if step < 40:
            loading.after(50, update_progress)
        else:
            show_enter_button()

    loading.after(100, update_progress)


def draw_footer():
    footer_height = 40
    canvas.create_rectangle(
        0, SCREEN_H - footer_height, SCREEN_W, SCREEN_H, fill="#0F0F0F", outline=""
    )
    canvas.create_text(
        SCREEN_W / 2,
        SCREEN_H - (footer_height // 2),
        text="System v1.0  •  Developed by BSCS2A Group 11",
        font=FOOTER_FONT,
        fill="#AAAAAA",
    )


# ==========================================
# 6. INITIALIZATION & RUN
# ==========================================
cycle_background()
draw_header()
draw_logo()
draw_title()
draw_exit_button()
start_loading_animation()
draw_footer()

loading.mainloop()
