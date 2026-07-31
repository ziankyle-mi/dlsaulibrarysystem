# ===================== IMPORTS =====================

import os
import sys
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from utils import sweetalert
messagebox = sweetalert  # SweetAlert2-styled popups

import customtkinter as ctk

try:
    from utils import theme
except ImportError:
    theme = None

from utils.db_manager import fetch_fines, mark_fine_paid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "database", "books_system.db") 

# ===================== COLORS =====================
PAGE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
HOVER_TINT = "#F3F7F6"
PRIMARY = getattr(theme, "PRIMARY", "#10312B")
PRIMARY_HOVER = "#1B5349"
FINE_RED = "#EF4444" 
PAID_GREEN = "#10B981" 

FINE_PER_DAY = 5

# ===================== WINDOW SETUP =====================

def open_screen(parent):
    global SCREEN_H, SCREEN_W, search_var, tree, window

    window = ctk.CTkToplevel(parent)
    window.attributes("-fullscreen", True)
    window.bind("<Escape>", lambda event: (theme.exit_program(window) if theme else (window.destroy(), window.destroy())))
    window.title("Fine Management")
    window.configure(fg_color=PAGE_BG)
    window.update()

    SCREEN_W = window.winfo_screenwidth()
    SCREEN_H = window.winfo_screenheight()

    # ===================== CANVAS SETUP =====================
    canvas = tk.Canvas(window, width=SCREEN_W, height=SCREEN_H, bd=0, highlightthickness=0, bg=PAGE_BG)
    canvas.pack(fill="both", expand=True)

    if theme:
        theme.build_header(window, canvas)

    # ===================== STYLE SETUP =====================
    theme.setup_modern_treeview_style()

    # ===================== MAIN CONTENT =====================
    header_h = getattr(theme, "HEADER_HEIGHT", 80) if theme else 60
    
    content_frame = ctk.CTkFrame(window, fg_color=PAGE_BG, corner_radius=0)
    canvas.create_window(SCREEN_W // 2, (SCREEN_H + header_h) // 2, window=content_frame, width=SCREEN_W - 80, height=SCREEN_H - header_h - 40)

    content_card = ctk.CTkFrame(content_frame, fg_color=CARD_BG, corner_radius=15, border_width=1, border_color=BORDER)
    content_card.pack(fill="both", expand=True, padx=20, pady=20)

    # ===================== TITLE =====================
    title_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    title_frame.pack(fill="x", padx=24, pady=(24, 8))

    ctk.CTkLabel(title_frame, text="Fine Management", font=("Segoe UI", 24, "bold"), text_color=PRIMARY).pack(side="left")
    ctk.CTkLabel(title_frame, text=f"Track outstanding & paid fines. Policy: ₱{FINE_PER_DAY}/day overdue.", font=("Segoe UI", 12), text_color=TEXT_SUB).pack(side="left", padx=(12, 0), pady=(4, 0))

    # ===================== SEARCH BAR =====================
    toolbar = ctk.CTkFrame(content_card, fg_color="transparent")
    toolbar.pack(fill="x", padx=24, pady=(10, 14))

    search_var = tk.StringVar()
    search_entry = ctk.CTkEntry(toolbar, textvariable=search_var, font=("Segoe UI", 13), width=300, fg_color=PAGE_BG, border_color=BORDER, placeholder_text="Search fine records...", text_color=TEXT_MAIN)
    search_entry.pack(side="left", padx=(0, 15))

    btn_refresh = ctk.CTkButton(toolbar, text="REFRESH", font=("Segoe UI", 12, "bold"), fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=lambda: refresh_table())
    btn_refresh.pack(side="left")
    
    # ===================== TABLE =====================
    table_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 16))

    columns = ("student_id", "student_name", "book_title", "due_date", "days_overdue", "fine", "status")
    headings = {
        "student_id": "STUDENT ID",
        "student_name": "STUDENT NAME",
        "book_title": "BOOK TITLE",
        "due_date": "DUE DATE",
        "days_overdue": "DAYS OVERDUE",
        "fine": "FINE (₱)",
        "status": "STATUS",
    }
    widths = {
        "student_id": 110, "student_name": 170, "book_title": 220,
        "due_date": 100, "days_overdue": 110, "fine": 90, "status": 150,
    }

    tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)

    for col in columns:
        tree.heading(col, text=headings[col])
        tree.column(col, width=widths[col], anchor="center")

    tree.tag_configure("unpaid", foreground=FINE_RED)
    tree.tag_configure("paid", foreground=PAID_GREEN)

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # ===================== BOTTOM ACTIONS =====================
    bottom_bar = ctk.CTkFrame(content_card, fg_color="transparent")
    bottom_bar.pack(fill="x", padx=24, pady=(0, 24))

    def on_mark_paid():
        selected = tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Select at least one fine record first.")
            return

        success_count = 0
        for record_id in selected:
            if record_id == "—":
                continue
            if mark_fine_paid(record_id):
                success_count += 1
                
        if success_count > 0:
            messagebox.showinfo("Payment Approved", f"Successfully approved {success_count} payment(s).")
            refresh_table()
        else:
            messagebox.showerror("Update failed", "Could not update the selected record(s).")

    mark_paid_btn = ctk.CTkButton(bottom_bar, text="APPROVE SELECTED PAYMENT(S)", font=("Segoe UI", 12, "bold"), fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=on_mark_paid)
    mark_paid_btn.pack(side="right")

    # ===================== LOAD / REFRESH =====================
    def refresh_table(*args):
        selected_values = None
        selected_item = tree.selection()
        if selected_item:
            selected_values = tree.item(selected_item[0], 'values')

        for item in tree.get_children():
            tree.delete(item)
            
        rows = fetch_fines(search_var.get().strip())

        if not rows:
            tree.insert("", "end", values=("—", "No fine records found", "—", "—", "—", "—", "—"))
            return

        for record_id, student_id, student_name, book_title, due_date, days_overdue, fine_amount, is_paid, payment_status, status_display in rows:
            pay_status = "Paid" if is_paid else ("Pending Approval" if payment_status == "pending" else "Unpaid")
            tag = "paid" if is_paid else "unpaid"
            tree.insert(
                "", "end", iid=str(record_id), tags=(tag,),
                values=(student_id, student_name, book_title, due_date,
                        days_overdue, f"{fine_amount:.2f}", f"{pay_status} | {status_display}"),
            )

        if selected_values:
            for item in tree.get_children():
                if tree.item(item, 'values') == list(selected_values):
                    tree.selection_set(item)
                    tree.see(item)
                    break

    search_var.trace_add("write", refresh_table)
    refresh_table()

    def auto_refresh_fines():
        if not tree.selection():
            refresh_table()
        window.after(6000, auto_refresh_fines)

    window.after(6000, auto_refresh_fines)

    # ===================== RUN =====================
    window.grab_set()
    return window

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    open_screen(root)
    root.mainloop()
