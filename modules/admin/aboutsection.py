import customtkinter as ctk
import tkinter as tk
import os
import sys
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageOps

from utils import theme
try:
    from utils import sweetalert as messagebox
except ImportError:
    pass

try:
    from modules.admin.demo_mode import open_demo_menu
except ImportError:
    open_demo_menu = None

# ===================== REFINED COLOR PALETTE =====================
PAGE_BG      = "#F8FAFC"  
CARD_BG      = "#FFFFFF"  
BORDER       = "#E2E8F0"  
BRAND        = "#10312B" 
ACCENT       = "#10B981"  
ACCENT_SOFT  = "#ECFDF5"  
TEXT_MAIN    = "#111827"  
TEXT_SUB     = "#6B7280"  
TEXT_MUTE    = "#9CA3AF"  
FONT_FAMILY  = "Segoe UI"

DEVELOPERS = [
    {"name": "Manuel Zian Kyle Piangco", "role": "Lead Documentation and Code", "file": "ziankyle.png", "tag": "Docs and Code"},
    {"name": "Joshua Enriquez",         "role": "Full Stack & Docs",  "file": "joshuatorpe.png",   "tag": "Backend"},
    {"name": "Huan Marzan",             "role": "Full Stack Developer", "file": "huanone.png",  "tag": "Full Stack/UI/UX"},
]

def get_avatar(img_dir, filename, size=200):
    path = img_dir / filename
    try:
        if not path.exists(): raise FileNotFoundError
        img = Image.open(path).convert("RGBA")
        img = ImageOps.fit(img, (size, size), centering=(0.5, 0.0))
    except:
        img = Image.new("RGBA", (size, size), (0,0,0,0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, size, size), fill=ACCENT_SOFT, outline=ACCENT, width=2)
        return ImageTk.PhotoImage(img)

    # Circular mask
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    
    output = Image.new("RGBA", (size, size), (0,0,0,0))
    output.paste(img, (0, 0), mask)
    
    # Add a clean modern ring border
    ring = Image.new("RGBA", (size, size), (0,0,0,0))
    r_draw = ImageDraw.Draw(ring)
    # Using #10B981 (16, 185, 129) for the ring
    r_draw.ellipse((2, 2, size-2, size-2), outline=(16, 185, 129, 255), width=3)
    output = Image.alpha_composite(output, ring)
    
    return ctk.CTkImage(light_image=output, dark_image=output, size=(size, size))

# ===================== MAIN APPLICATION =====================
def open_screen(parent):
    global app, main_canvas, img_refs
    
    app = ctk.CTkToplevel(parent)
    app.attributes("-fullscreen", True)
    app.configure(fg_color=PAGE_BG)
    
    def safe_destroy(event=None):
        app.withdraw()
        app.destroy()
        
    app.bind("<Escape>", lambda e: safe_destroy())
    app.title("About The Developers")
    
    SCREEN_W = app.winfo_screenwidth()
    SCREEN_H = app.winfo_screenheight()

    # TOP HEADER - Using the main dashboard BRAND color
    header_canvas = tk.Canvas(app, width=SCREEN_W, height=70, bg=BRAND, highlightthickness=0, bd=0)
    header_canvas.pack(fill="x", side="top")
    
    try:
        base_dir = Path(__file__).parent.parent.parent
        logo = Image.open(base_dir / "images" / "dlsaulogos1.png")
        logo = logo.resize((320, 40), Image.Resampling.LANCZOS)
        app.logo_photo = ImageTk.PhotoImage(logo)
        header_canvas.create_image(40, 35, image=app.logo_photo, anchor="w")
    except Exception:
        pass

    exit_btn = ctk.CTkButton(
        app, text="✕", font=(FONT_FAMILY, 20, "bold"), width=40, height=40,
        corner_radius=8, fg_color="transparent", bg_color=BRAND, text_color="white", hover_color="#E81123",
        border_width=0, command=safe_destroy
    )
    header_canvas.create_window(SCREEN_W - 30, 35, window=exit_btn, anchor="e")
    
    back_btn = ctk.CTkButton(
        app, text="RETURN TO DASHBOARD", font=(FONT_FAMILY, 10, "bold"), width=160, height=40,
        corner_radius=8, fg_color="transparent", bg_color=BRAND, text_color="white", hover_color="#1B5349",
        border_width=1, border_color="white", command=safe_destroy
    )
    header_canvas.create_window(SCREEN_W - 90, 35, window=back_btn, anchor="e")

    # SCROLLABLE CANVAS
    container = ctk.CTkFrame(app, fg_color=PAGE_BG, corner_radius=0)
    container.pack(fill="both", expand=True)

    scrollbar = tk.Scrollbar(container, orient="vertical", troughcolor=PAGE_BG, bg=BORDER, bd=0, activebackground=ACCENT)
    scrollbar.pack(side="right", fill="y")

    main_canvas = tk.Canvas(container, bd=0, highlightthickness=0, bg=PAGE_BG)
    main_canvas.pack(side="left", fill="both", expand=True)

    scrollbar.config(command=main_canvas.yview)
    main_canvas.config(yscrollcommand=scrollbar.set)
    theme.bind_mousewheel(app, main_canvas)

    # Add background grid lines for architectural feel but light theme
    for i in range(0, 3000, 100):
        main_canvas.create_line(0, i, 4000, i, fill="#F1F5F9", width=1)
        main_canvas.create_line(i, 0, i, 4000, fill="#F1F5F9", width=1)

    content_frame = ctk.CTkFrame(main_canvas, fg_color=PAGE_BG, corner_radius=0)
    CONTENT_WIDTH = min(1200, SCREEN_W - 100) 
    content_id = main_canvas.create_window(SCREEN_W // 2, 40, window=content_frame, width=CONTENT_WIDTH, anchor="n")

    def _recenter(event):
        main_canvas.itemconfig(content_id, width=min(1200, event.width - 100))
        main_canvas.coords(content_id, event.width // 2, 40)
    main_canvas.bind("<Configure>", _recenter)

    # CONTENT
    img_dir = Path(__file__).parent.parent.parent / "images"
    app.img_refs = [] 

    ctk.CTkLabel(
        content_frame, text="// DLSAU LIBRARY SYSTEM : V1.0", font=("Consolas", 12), 
        text_color=ACCENT
    ).pack(pady=(60, 0), anchor="w")
    
    ctk.CTkLabel(
        content_frame, text="MEET THE DEVELOPERS", font=(FONT_FAMILY, 56, "bold"), 
        text_color=TEXT_MAIN
    ).pack(anchor="w")
    
    ctk.CTkLabel(
        content_frame, text="De La Salle Araneta University Library System Engineering Team.", 
        font=(FONT_FAMILY, 16), text_color=TEXT_SUB
    ).pack(pady=(5, 60), anchor="w")

    # Developer Horizontal Panels
    cards_container = ctk.CTkFrame(content_frame, fg_color=PAGE_BG, corner_radius=0)
    cards_container.pack(fill="x")

    for idx, dev in enumerate(DEVELOPERS):
        # Horizontal sleek panel
        panel = ctk.CTkFrame(cards_container, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color=BORDER)
        panel.pack(fill="x", pady=15, ipady=20)

        # Content container inside panel
        inner = ctk.CTkFrame(panel, fg_color=CARD_BG, corner_radius=0)
        inner.pack(fill="both", expand=True, padx=40)

        # Avatar on left
        photo = get_avatar(img_dir, dev["file"], size=160)
        app.img_refs.append(photo)
    
        pic_lbl = ctk.CTkLabel(inner, image=photo, text="", fg_color=CARD_BG)
        pic_lbl.pack(side="left", pady=10, padx=(0, 40))

        # Text Info on right
        info_frame = ctk.CTkFrame(inner, fg_color=CARD_BG, corner_radius=0)
        info_frame.pack(side="left", fill="y", expand=True, pady=30)
        
        ctk.CTkLabel(info_frame, text=f"0{idx+1}.", font=("Consolas", 14), text_color=ACCENT).pack(anchor="w")
        name_lbl = ctk.CTkLabel(info_frame, text=dev["name"].upper(), font=(FONT_FAMILY, 32, "bold"), text_color=TEXT_MAIN)
        name_lbl.pack(anchor="w", pady=(5, 0))
        
        # Secret Demo Menu trigger (3 clicks)
        if "Manuel" in dev["name"]:
            name_lbl.configure(cursor="hand2")
            name_lbl._click_count = 0
            def on_dev_click(event, lbl=name_lbl):
                lbl._click_count += 1
                if lbl._click_count >= 3:
                    lbl._click_count = 0
                    if open_demo_menu:
                        open_demo_menu(app)
            name_lbl.bind("<Button-1>", on_dev_click)

        ctk.CTkLabel(info_frame, text=dev["role"], font=(FONT_FAMILY, 16), text_color=TEXT_SUB).pack(anchor="w")

        # Badge
        badge = ctk.CTkFrame(info_frame, fg_color=ACCENT_SOFT, corner_radius=6, border_width=1, border_color=ACCENT)
        badge.pack(anchor="w", pady=(20, 0))
        ctk.CTkLabel(badge, text=dev["tag"].upper(), font=("Consolas", 12, "bold"), text_color=ACCENT).pack(padx=12, pady=4)

    # Blueprints Quote
    motto_outer = ctk.CTkFrame(content_frame, fg_color=BRAND, corner_radius=12, border_width=0)
    motto_outer.pack(fill="x", pady=80)

    quote_text = ("\"Technology is best when it brings people together.\n"
                  "We defined the space for knowledge to flow freely.\"")
    
    ctk.CTkLabel(
        motto_outer, text=quote_text, font=(FONT_FAMILY, 22, "italic"), 
        text_color="#D1FAE5", justify="center"
    ).pack(pady=(50, 20))
    
    ctk.CTkLabel(
        motto_outer, text="— THE ENGINEERING TEAM", font=("Consolas", 12), 
        text_color=ACCENT
    ).pack(pady=(0, 50))

    # Acknowledgment Section
    ctk.CTkLabel(
        content_frame, text="// ACKNOWLEDGMENTS", font=("Consolas", 12), 
        text_color=ACCENT
    ).pack(pady=(20, 5), anchor="w")
    
    ctk.CTkLabel(
        content_frame, text="Special Thanks", font=(FONT_FAMILY, 28, "bold"), 
        text_color=TEXT_MAIN
    ).pack(anchor="w", pady=(0, 30))

    ack_grid = ctk.CTkFrame(content_frame, fg_color=PAGE_BG, corner_radius=0)
    ack_grid.pack(fill="x", pady=(0, 80))

    thanks = [
        ("Doc. Marilyn Rubirca", "Guidance and project mentorship"),
        ("Mikkie Malonzo", "UI Feedback & Image assistance"),
        ("Jose Luis Gabo", "Project Assets Support"),
        ("Justin Miguel Encarnado", "Project Assets Support"),
        ("Claude & Gemini", "AI-assisted logic guidance"),
    ]

    for name, desc in thanks:
        row = ctk.CTkFrame(ack_grid, fg_color=PAGE_BG, corner_radius=0)
        row.pack(pady=8, fill="x")
        
        # Dotted line connector
        ctk.CTkLabel(row, text=name.upper(), font=(FONT_FAMILY, 14, "bold"), text_color=TEXT_MAIN, anchor="w", width=250).pack(side="left")
        
        # Draw a custom canvas for a dotted line leader
        dash_canvas = tk.Canvas(row, height=20, bg=PAGE_BG, bd=0, highlightthickness=0)
        dash_canvas.pack(side="left", fill="x", expand=True, padx=15)
        dash_canvas.create_line(0, 10, 2000, 10, fill=BORDER, dash=(2, 4))
        
        ctk.CTkLabel(row, text=desc, font=(FONT_FAMILY, 14), text_color=TEXT_SUB, anchor="e").pack(side="right")

    ctk.CTkLabel(
        content_frame, text="© 2026 DE LA SALLE ARANETA UNIVERSITY LIBRARY SYSTEM", 
        font=("Consolas", 10), text_color=TEXT_MUTE
    ).pack(pady=(0, 80))

    def _update_scroll(event=None):
        app.update_idletasks()
        h = content_frame.winfo_reqheight() + 100
        main_canvas.configure(scrollregion=(0, 0, SCREEN_W, h))

    content_frame.bind("<Configure>", _update_scroll)

    app.grab_set()
    return app

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    try:
        app = open_screen(root)
        root.mainloop()
    except Exception as e:
        import traceback
        with open("crash.txt", "w") as f:
            traceback.print_exc(file=f)
        raise
