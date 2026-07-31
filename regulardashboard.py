import customtkinter as ctk
import tkinter as tk
from utils import sweetalert as messagebox
from PIL import Image, ImageTk, ImageFilter, ImageDraw, ImageOps
import os
import sys
import subprocess
import datetime
from utils import theme
from utils import student_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "images")

# ===================== THEME & PALETTE =====================

BG = "#F9F9F9"
CARD_BG = "#FFFFFF"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
PRIMARY = "#10312B"
HOVER_TINT = "#F3F7F6"
FONT_FAMILY = "Segoe UI"
BORDER_SOFT = "#E5E7EB"

# ===================== WINDOW SETUP =====================

loading = ctk.CTk()
loading.attributes("-fullscreen", True)
loading.bind("<Escape>", lambda event: theme.exit_program(loading))
loading.title("Student Dashboard")
loading.configure(bg=BG)

loading.update()
SCREEN_W = loading.winfo_screenwidth()
SCREEN_H = loading.winfo_screenheight()

# ===================== SESSION =====================
SESSION_FILE = os.path.join(BASE_DIR, "database", ".session")

def _load_and_clear_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                email = f.read().strip()
            os.remove(SESSION_FILE)
            if email:
                return email
        except Exception:
            pass
    return sys.argv[1] if len(sys.argv) > 1 else ""

logged_in_email = _load_and_clear_session()
student_db.logged_in_email = logged_in_email

user_info = student_db.get_current_user_info(logged_in_email)
user_name = user_info['name']

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

profile_bubble_window = None

def render_profile_bubble():
    global profile_bubble_window
    u_info = student_db.get_current_user_info(logged_in_email)
    pic_path = u_info.get('profile_picture')
    
    first_name = (u_info.get('name') or 'Student').split()[0]
    
    hour = datetime.datetime.now().hour
    if hour < 12:
        time_g = "Good morning"
    elif hour < 18:
        time_g = "Good afternoon"
    else:
        time_g = "Good evening"
        
    greeting_str = f"{time_g}, {first_name}! 👋"
    
    sz = 40
    scale = 4
    high_sz = sz * scale
    
    avatar_img = None
    if pic_path and os.path.exists(pic_path):
        try:
            img = Image.open(pic_path).convert("RGBA")
            img = ImageOps.fit(img, (high_sz, high_sz), Image.Resampling.LANCZOS)
            mask = Image.new("L", (high_sz, high_sz), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, high_sz, high_sz), fill=255)
            img.putalpha(mask)
            ring = Image.new("RGBA", (high_sz, high_sz), (0, 0, 0, 0))
            ImageDraw.Draw(ring).ellipse((2, 2, high_sz-2, high_sz-2), outline=(255, 255, 255, 255), width=6)
            out = Image.alpha_composite(img, ring)
            out = out.resize((sz, sz), Image.Resampling.LANCZOS)
            avatar_img = ImageTk.PhotoImage(out)
        except Exception:
            avatar_img = None
            
    if not avatar_img:
        img = Image.new("RGBA", (high_sz, high_sz), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, high_sz, high_sz), fill=(16, 49, 43, 255), outline=(255, 255, 255, 255), width=6)
        initials = "".join([p[0].upper() for p in u_info.get('name', 'User').split()[:2]]) or "U"
        try:
            font = theme.load_display_font(56, True)
            bbox = draw.textbbox((0, 0), initials, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((high_sz - tw)/2 - bbox[0], (high_sz - th)/2 - bbox[1]), initials, fill="white", font=font)
        except Exception:
            pass
        out = img.resize((sz, sz), Image.Resampling.LANCZOS)
        avatar_img = ImageTk.PhotoImage(out)
        
    loading.profile_photo = avatar_img
    
    if profile_bubble_window:
        canvas.delete(profile_bubble_window)
        
    profile_btn = ctk.CTkButton(
        loading, image=avatar_img, text=f" {greeting_str} ", compound="left",
        font=(FONT_FAMILY, 12, "bold"), text_color="white", height=40, corner_radius=20,
        fg_color="#173832", hover_color="#1B5349", bg_color=PRIMARY,
        command=lambda: on_box_click("Account Settings")
    )
    profile_bubble_window = canvas.create_window(SCREEN_W - 190, 30, window=profile_btn, anchor="e")

render_profile_bubble()

# ===================== BACKGROUND CYCLING =====================

BACKGROUND_IMAGES = [
    os.path.join(BASE_DIR, "images", "login1pic.png"),
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
    
    def launch_module():
        loading.withdraw()
        try:
            if module_name == "Library Catalog":
                from modules.student import student_catalog as mod
            elif module_name == "My Borrowings":
                from modules.student import student_borrowings as mod
            elif module_name == "Fines & Payments":
                from modules.student import student_fines as mod
            elif module_name == "Account Settings":
                from modules.student import student_settings as mod
            else:
                return

            child_window = mod.open_screen(loading, logged_in_email)
            if child_window:
                loading.wait_window(child_window)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch module:\n{e}")
            
        loading.deiconify()
        render_profile_bubble()
        
        def on_fade_in_complete():
            global is_launching
            is_launching = False
            
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
    SCREEN_W // 2, 85,
    text=f"{greeting} {user_name}.",
    font=(FONT_FAMILY, 34, "bold"),
    fill="white"
)

# Fetch Stats
current_borrowings = student_db.get_student_current_borrowings(logged_in_email)
active_borrows = [b for b in current_borrowings if b[5] in ('borrowed', 'return_requested')]
total_borrowed_count = len(active_borrows)

due_soon_count = 0
due_today_or_past = 0
today = datetime.date.today()

for b in active_borrows:
    try:
        due_date = datetime.datetime.strptime(b[4], "%Y-%m-%d").date()
        diff = (due_date - today).days
        if diff <= 2:
            due_soon_count += 1
        if diff <= 0:
            due_today_or_past += 1
    except Exception:
        pass

total_fines = student_db.get_student_total_fines(logged_in_email)

# --- Feature 3: Due Soon Banner (Modern Pill Design) ---
if due_soon_count > 0:
    banner_color = theme.WARNING if due_today_or_past == 0 else "#EF4444" 
    banner_text = f"⚠  {due_soon_count} book(s) due within 2 days!" if due_today_or_past == 0 else f"⚠  {due_today_or_past} book(s) overdue — fines may apply!"
    
    banner_w = 480
    banner_h = 44
    banner_x = SCREEN_W // 2
    banner_y = 140
    
    # Shadow
    draw_rounded_rect(canvas, banner_x - banner_w//2, banner_y - banner_h//2 + 4, banner_x + banner_w//2, banner_y + banner_h//2 + 4, radius=22, fill="", outline="", tags=("banner_win", "shadow"))
    # In Tkinter standard canvas, fake drop shadow by drawing multiple semi-transparent rectangles or a dark gray offset.
    # We will just draw a subtle dark offset.
    draw_rounded_rect(canvas, banner_x - banner_w//2, banner_y - banner_h//2 + 2, banner_x + banner_w//2, banner_y + banner_h//2 + 2, radius=22, fill="#000000", outline="", tags="banner_win")
    
    # Main Pill
    draw_rounded_rect(canvas, banner_x - banner_w//2, banner_y - banner_h//2, banner_x + banner_w//2, banner_y + banner_h//2, radius=22, fill=banner_color, outline="", tags="banner_win")
    
    # Text
    canvas.create_text(banner_x, banner_y, text=banner_text, font=(FONT_FAMILY, 13, "bold"), fill="white", tags="banner_win")
    
    # Close Button (X)
    close_x = banner_x + banner_w//2 - 25
    canvas.create_text(close_x, banner_y, text="✕", font=(FONT_FAMILY, 14, "bold"), fill="white", tags=("banner_win", "banner_close"))
    
    def dismiss_banner(event):
        canvas.delete("banner_win")
        
    def on_close_hover(event):
        canvas.config(cursor="hand2")
        canvas.itemconfigure("banner_close", fill="#FCA5A5" if due_today_or_past > 0 else "#FDE68A")
        
    def on_close_leave(event):
        canvas.config(cursor="")
        canvas.itemconfigure("banner_close", fill="white")
        
    canvas.tag_bind("banner_close", "<Button-1>", dismiss_banner)
    canvas.tag_bind("banner_close", "<Enter>", on_close_hover)
    canvas.tag_bind("banner_close", "<Leave>", on_close_leave)

# --- Feature 2: At a Glance Stats Dashboard (Drawn directly on canvas for true transparency) ---
stat_w, stat_h = 180, 85
stat_spacing = 15
num_stats = 3
total_stats_w = (num_stats * stat_w) + ((num_stats - 1) * stat_spacing)

# We want to center the whole block
stats_start_x = (SCREEN_W - total_stats_w) // 2
stats_y = 220

# Draw Books Borrowed
cx = stats_start_x + (stat_w // 2)
draw_rounded_rect(canvas, cx - stat_w//2, stats_y - stat_h//2, cx + stat_w//2, stats_y + stat_h//2, radius=12, fill=CARD_BG, outline=BORDER_SOFT)
canvas.create_text(cx, stats_y - 10, text=str(total_borrowed_count), font=(FONT_FAMILY, 28, "bold"), fill=PRIMARY)
canvas.create_text(cx, stats_y + 20, text="BOOKS BORROWED", font=(FONT_FAMILY, 10, "bold"), fill=TEXT_SUB)

# Draw Due Soon / Overdue
cx += stat_w + stat_spacing
draw_rounded_rect(canvas, cx - stat_w//2, stats_y - stat_h//2, cx + stat_w//2, stats_y + stat_h//2, radius=12, fill=CARD_BG, outline=BORDER_SOFT)
val_color = "#EF4444" if due_soon_count > 0 else PRIMARY
canvas.create_text(cx, stats_y - 10, text=str(due_soon_count), font=(FONT_FAMILY, 28, "bold"), fill=val_color)
canvas.create_text(cx, stats_y + 20, text="DUE SOON / OVERDUE", font=(FONT_FAMILY, 10, "bold"), fill=TEXT_SUB)

# Draw Unpaid Fines
cx += stat_w + stat_spacing
draw_rounded_rect(canvas, cx - stat_w//2, stats_y - stat_h//2, cx + stat_w//2, stats_y + stat_h//2, radius=12, fill=CARD_BG, outline=BORDER_SOFT)
val_color = "#EF4444" if total_fines > 0 else PRIMARY
canvas.create_text(cx, stats_y - 10, text=f"₱{total_fines}", font=(FONT_FAMILY, 28, "bold"), fill=val_color)
canvas.create_text(cx, stats_y + 20, text="UNPAID FINES", font=(FONT_FAMILY, 10, "bold"), fill=TEXT_SUB)

MODULES = [
    {"text": "Library Catalog",   "image_file": "healtheworld.png", "desc": "Browse our collection and borrow new books."},
    {"text": "My Borrowings",     "image_file": "bookborrow1.png",  "desc": "Return normal books, and view your current/past borrowings."},
    {"text": "Fines & Payments",  "image_file": "fine.png",         "desc": "Pay penalties for overdue/damaged books. (Return overdue books here!)"},
    {"text": "Account Settings",  "image_file": "usermanagement.png", "desc": "Update your profile picture and change your password."},
]

cols, rows = 2, 2
card_w = 440
card_h = 120
spacing_x = 40
spacing_y = 30

grid_w = (cols * card_w) + ((cols - 1) * spacing_x)
grid_h = (rows * card_h) + ((rows - 1) * spacing_y)

start_x = (SCREEN_W - grid_w) // 2
start_y = 330

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
    
    # Shadow
    canvas.create_polygon(
        [x1+20, y1+20, x2-20, y1+20, x2, y1+40, x2, y2, x2-20, y2+10, x1+20, y2+10, x1, y2, x1, y1+40],
        smooth=True, fill="#111111", tags=f"shadow_{item_tag}"
    )
    
    # Draw card background
    tile_id = draw_rounded_rect(
        canvas, x1, y1, x2, y2, radius=20,
        fill=CARD_BG, outline="", tags=item_tag
    )
    
    # Icon placement
    icon_x = x1 + 60
    if btn_image:
        canvas.create_image(icon_x, cy, image=btn_image, tags=item_tag)
        
    # Text placement
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
        width=280,
        tags=item_tag
    )
    
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
    
    canvas.tag_lower(f"shadow_{item_tag}")

loading.after(50, lambda: canvas.tag_lower("bg"))

# ===================== RUN =====================
loading.mainloop()
