# ===================== IMPORTS =====================
import customtkinter as ctk
import tkinter as tk
from utils import sweetalert as messagebox
from PIL import Image, ImageTk, ImageFilter, ImageDraw
import os
import sys
import subprocess
from utils import theme
import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "images")
SESSION_FILE = os.path.join(BASE_DIR, "database", ".session")
if os.path.exists(SESSION_FILE):
    try:
        os.remove(SESSION_FILE)
    except Exception:
        pass

# ===================== THEME & PALETTE =====================

BG = "#F9F9F9"
CARD_BG = "#FFFFFF"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
PRIMARY = "#10312B"
HOVER_TINT = "#F3F7F6"
FONT_FAMILY = "Segoe UI"

# ===================== WINDOW SETUP =====================

loading = ctk.CTk()
loading.attributes("-fullscreen", True)
loading.bind("<Escape>", lambda event: theme.exit_program(loading))
loading.title("Admin Dashboard")
loading.configure(bg=BG)

loading.update()
SCREEN_W = loading.winfo_screenwidth()
SCREEN_H = loading.winfo_screenheight()

# ===================== HEADER & CANVAS =====================

canvas = tk.Canvas(loading, width=SCREEN_W, height=SCREEN_H, bg=BG, highlightthickness=0, bd=0)
canvas.pack(fill="both", expand=True)

theme.draw_header(loading, canvas)

def sign_out():
    def finish_sign_out():
        try:
            subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "login.py")], cwd=BASE_DIR)
        except Exception as exc:
            messagebox.showerror("Sign Out Error", f"Could not open login screen: {exc}")
        loading.destroy()
    theme.fade_out(loading, finish_sign_out)

exit_btn = ctk.CTkButton(
    loading, text="✕", font=(FONT_FAMILY, 20, "bold"), width=40, height=40,
    corner_radius=8, fg_color=PRIMARY, text_color="white", hover_color="#E81123",
    command=lambda: theme.exit_program(loading)
)
canvas.create_window(SCREEN_W - 20, 30, window=exit_btn, anchor="e")

signout_btn = ctk.CTkButton(
    loading, text="Sign Out", font=(FONT_FAMILY, 12, "bold"), width=100, height=40,
    corner_radius=8, fg_color=PRIMARY, text_color="white", hover_color="#1B5349",
    command=sign_out
)
canvas.create_window(SCREEN_W - 75, 30, window=signout_btn, anchor="e")

# ===================== BACKGROUND CYCLING =====================

BACKGROUND_IMAGES = [
    os.path.join(BASE_DIR, "images", "outside.png"),
    os.path.join(BASE_DIR, "images", "outside3.png"),
    os.path.join(BASE_DIR, "images", "outside2.png"),
    os.path.join(BASE_DIR, "images", "forest.png"),
]
current_bg_index = 0

def cycle_background():
    global current_bg_index
    try:
        # Only update the background if the dashboard is actively visible
        if loading.state() == 'normal':
            img_path = BACKGROUND_IMAGES[current_bg_index]
            if os.path.exists(img_path):
                bg = Image.open(img_path).convert("RGBA")
                bg = bg.filter(ImageFilter.GaussianBlur(radius=8))
                bg = bg.resize((SCREEN_W, SCREEN_H), Image.Resampling.LANCZOS)
                
                # Rich cinematic dark overlay over entire screen
                overlay = Image.new("RGBA", bg.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                draw.rectangle([0, 0, SCREEN_W, SCREEN_H], fill=(6, 15, 12, 160))
                
                final_bg = Image.alpha_composite(bg, overlay)
                
                photo = ImageTk.PhotoImage(final_bg)
                loading.bg_photo = photo 

                canvas.delete("bg")
                canvas.create_image(0, 0, image=photo, anchor="nw", tags="bg")
                canvas.tag_lower("bg")
                
            current_bg_index = (current_bg_index + 1) % len(BACKGROUND_IMAGES)
    except Exception as e:
        print(f"Background error: {e}")

    if len(BACKGROUND_IMAGES) > 1:
        loading.after(10000, cycle_background)

cycle_background()

# ===================== MODULE LAUNCHER =====================

is_launching = False

def on_box_click(module_name):
    global is_launching
    if is_launching:
        return
    is_launching = True
    
    script_map = {
        "Books Inventory": "bookinventory.py",
        "User Management": "usermanagement.py",
        "Student Borrowing": "studentborrowing.py",
        "About": "aboutsection.py",
        "Analytics Reports": "analytics.py",
        "Fine Management": "finemanagement.py",
    }
    def launch_module():
        loading.withdraw()
        try:
            if module_name == "Books Inventory":
                from modules.admin import bookinventory as mod
            elif module_name == "User Management":
                from modules.admin import usermanagement as mod
            elif module_name == "Student Borrowing":
                from modules.admin import studentborrowing as mod
            elif module_name == "About":
                from modules.admin import aboutsection as mod
            elif module_name == "Analytics Reports":
                from modules.admin import analytics as mod
            elif module_name == "Fine Management":
                from modules.admin import finemanagement as mod
            else:
                return

            child_window = mod.open_screen(loading)
            if child_window:
                loading.wait_window(child_window)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch module:\n{e}")
            
        loading.deiconify()
        
        def on_fade_in_complete():
            global is_launching
            is_launching = False
            
        # We need a custom fade_in that resets the flag, or just reset it after a delay
        theme.fade_in(loading)
        loading.after(500, on_fade_in_complete)

    theme.fade_out(loading, launch_module)

# ===================== ICON PROCESSING =====================
def _corner_background_color(img):
    w, h = img.size
    corners = [img.getpixel((0, 0)), img.getpixel((w - 1, 0)),
               img.getpixel((0, h - 1)), img.getpixel((w - 1, h - 1))]
    r = sum(c[0] for c in corners) / 4
    g = sum(c[1] for c in corners) / 4
    b = sum(c[2] for c in corners) / 4
    return (r, g, b)

def process_icon(path, size, fg_color=(16, 49, 43, 255)):
    if not os.path.exists(path):
        return None
    img = Image.open(path).convert("RGBA").resize(size, Image.Resampling.LANCZOS)
    w, h = img.size
    pixels = img.load()
    alpha_values = [pixels[x, y][3] for x in range(0, w, 4) for y in range(0, h, 4)]
    has_real_alpha = min(alpha_values) < 250
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out_px = out.load()
    foreground_count = 0
    total = w * h
    if has_real_alpha:
        for y in range(h):
            for x in range(w):
                a = pixels[x, y][3]
                if a > 10: foreground_count += 1
                out_px[x, y] = (fg_color[0], fg_color[1], fg_color[2], a)
    else:
        bg_r, bg_g, bg_b = _corner_background_color(img)
        tolerance = 60
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                dist = ((r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2) ** 0.5
                if dist <= tolerance:
                    out_px[x, y] = (0, 0, 0, 0)
                else:
                    edge_alpha = min(255, int(((dist - tolerance) / 30) * 255))
                    if edge_alpha > 10: foreground_count += 1
                    out_px[x, y] = (fg_color[0], fg_color[1], fg_color[2], edge_alpha)
    if foreground_count / total > 0.65:
        return None
    return out

def fallback_icon(label_text, size, fg_color=(16, 49, 43, 255)):
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad = int(w * 0.12)
    draw.ellipse([pad, pad, w - pad, h - pad], outline=fg_color, width=3)
    letter = (label_text.strip() or "?")[0].upper()
    bbox = draw.textbbox((0, 0), letter)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((w - tw) / 2 - bbox[0], (h - th) / 2 - bbox[1]), letter, fill=fg_color)
    return img

def draw_rounded_rect(cnv, x1, y1, x2, y2, radius=16, **kwargs):
    points = [
        x1 + radius, y1, x2 - radius, y1, x2, y1, x2, y1 + radius,
        x2, y2 - radius, x2, y2, x2 - radius, y2, x1 + radius, y2,
        x1, y2, x1, y2 - radius, x1, y1 + radius, x1, y1,
    ]
    return cnv.create_polygon(points, smooth=True, **kwargs)

# ===================== UI RENDERING =====================

# 1. Gorgeous Greeting Text
hour = datetime.datetime.now().hour
if hour < 12: greeting = "Good morning,"
elif hour < 17: greeting = "Good afternoon,"
else: greeting = "Good evening,"

canvas.create_text(
    SCREEN_W // 2, 160,
    text=f"{greeting} Administrator.",
    font=(FONT_FAMILY, 34, "bold"),
    fill="white"
)
canvas.create_text(
    SCREEN_W // 2, 205,
    text="Select a module below to manage the library system.",
    font=(FONT_FAMILY, 14),
    fill="#D1D5DB"
)

MODULES = [
    {"text": "Books Inventory",   "image_file": "healtheworld.png", "desc": "Add, update, or remove books from the library catalog."},
    {"text": "Student Borrowing", "image_file": "bookborrow1.png",  "desc": "Manage book checkouts, returns, and track student loans."},
    {"text": "User Management",   "image_file": "usermanagement.png", "desc": "Control admin access and manage student accounts."},
    {"text": "Fine Management",   "image_file": "fine.png",         "desc": "Track overdue books and process student penalty fees."},
    {"text": "About",             "image_file": "systemsetting.png",  "desc": "System information, version details, and developer credits."},
    {"text": "Analytics Reports", "image_file": "anal.png",         "desc": "View library statistics, trends, and generate reports."},
]

cols, rows = 2, 3
card_w = 440
card_h = 120
spacing_x = 40
spacing_y = 30

grid_w = (cols * card_w) + ((cols - 1) * spacing_x)
grid_h = (rows * card_h) + ((rows - 1) * spacing_y)

start_x = (SCREEN_W - grid_w) // 2
start_y = 280

loading.card_images = []
hover_states = {}

for i, config in enumerate(MODULES):
    c = i % cols
    r = i // cols
    
    img_path = os.path.join(IMG_DIR, config["image_file"])
    icon_img = process_icon(img_path, (52, 52))
    if icon_img is None:
        icon_img = fallback_icon(config["text"], (52, 52))
        
    try:
        btn_image = ImageTk.PhotoImage(icon_img)
        loading.card_images.append(btn_image)
    except Exception:
        btn_image = None
    
    # Calculate box
    cx = start_x + (c * (card_w + spacing_x)) + (card_w // 2)
    cy = start_y + (r * (card_h + spacing_y)) + (card_h // 2)
    
    x1 = cx - (card_w // 2)
    y1 = cy - (card_h // 2)
    x2 = cx + (card_w // 2)
    y2 = cy + (card_h // 2)
    
    item_tag = f"module_{i}"
    hover_states[item_tag] = False
    
    # Shadow (Solid color instead of stipple to prevent Windows Tkinter crashes)
    canvas.create_polygon(
        [x1+20, y1+20, x2-20, y1+20, x2, y1+40, x2, y2, x2-20, y2+10, x1+20, y2+10, x1, y2, x1, y1+40],
        smooth=True, fill="#111111", tags=f"shadow_{item_tag}"
    )
    
    # Draw card background
    tile_id = draw_rounded_rect(
        canvas, x1, y1, x2, y2, radius=20,
        fill=CARD_BG, outline="", tags=item_tag
    )
    
    # Icon placement (left side)
    icon_x = x1 + 60
    if btn_image:
        canvas.create_image(icon_x, cy, image=btn_image, tags=item_tag)
        
    # Text placement (right of icon)
    text_x = x1 + 120
    canvas.create_text(
        text_x, cy - 14,
        text=config['text'],
        font=(FONT_FAMILY, 16, "bold"),
        fill=TEXT_MAIN,
        anchor="w",
        tags=item_tag
    )
    
    canvas.create_text(
        text_x, cy + 14,
        text=config['desc'],
        font=(FONT_FAMILY, 10),
        fill=TEXT_SUB,
        anchor="w",
        width=280, # wrap text
        tags=item_tag
    )
    
    # Hover animations (color change only, removed buggy movement)
    def on_enter(event, tid=item_tag):
        if not hover_states[tid]:
            hover_states[tid] = True
            for item in canvas.find_withtag(tid):
                if canvas.type(item) == "polygon":
                    canvas.itemconfig(item, fill=HOVER_TINT)
            canvas.config(cursor="hand2")

    def on_leave(event, tid=item_tag):
        if hover_states[tid]:
            hover_states[tid] = False
            for item in canvas.find_withtag(tid):
                if canvas.type(item) == "polygon":
                    canvas.itemconfig(item, fill=CARD_BG)
            canvas.config(cursor="")

    canvas.tag_bind(item_tag, "<Button-1>", lambda event, name=config["text"]: on_box_click(name))
    canvas.tag_bind(item_tag, "<Enter>", on_enter)
    canvas.tag_bind(item_tag, "<Leave>", on_leave)
    
    # Fix shadow layer so it stays behind the card
    canvas.tag_lower(f"shadow_{item_tag}")

loading.after(50, lambda: canvas.tag_lower("bg"))

# ===================== RUN =====================
loading.mainloop()
