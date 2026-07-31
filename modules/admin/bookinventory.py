# ===================== IMPORTS =====================

import os
import sys
import sqlite3
import pandas as pd
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk
from utils import sweetalert as messagebox
from PIL import Image, ImageTk
from utils import bookimageapi  # Open Library book cover API integration

try:
    from utils import theme  # Injects your customized structural design system
except ImportError as e:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Import Error", f"Could not find 'theme.py' in this folder!\nDetails: {e}")
    sys.exit()


PRIMARY_HOVER = "#1B5349"
PAGE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
HOVER_TINT = "#F3F7F6"


# ===================== DATABASE CONFIGURATION =====================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FOLDER_NAME = "database" 

DB_FOLDER = os.path.join(BASE_DIR, FOLDER_NAME)
os.makedirs(DB_FOLDER, exist_ok=True) 

excel_file = os.path.join(DB_FOLDER, "booksdatabase.xlsx")
db_file = os.path.join(DB_FOLDER, "books_system.db")

SHEET_NAME = "Verified Inventory"
EXCEL_COLUMNS = ['Book Code', 'Author Name', 'Book Title', 'Category', 'Publication Year']

# ===================== DATABASE SYSTEM ENGINE =====================

def ensure_books_schema():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS books (
            book_code TEXT PRIMARY KEY,
            author_name TEXT,
            book_title TEXT,
            category TEXT,
            publication_year TEXT,
            is_borrowed INTEGER DEFAULT 0,
            total_copies INTEGER DEFAULT 1,
            available_copies INTEGER DEFAULT 1
        )
    ''')
    cursor.execute("PRAGMA table_info(books)")
    columns = {row[1] for row in cursor.fetchall()}
    if "is_borrowed" not in columns:
        cursor.execute("ALTER TABLE books ADD COLUMN is_borrowed INTEGER DEFAULT 0")
    if "total_copies" not in columns:
        cursor.execute("ALTER TABLE books ADD COLUMN total_copies INTEGER DEFAULT 1")
    if "available_copies" not in columns:
        cursor.execute("ALTER TABLE books ADD COLUMN available_copies INTEGER DEFAULT 1")

    cursor.execute("UPDATE books SET total_copies = 1 WHERE total_copies IS NULL")
    cursor.execute("UPDATE books SET available_copies = CASE WHEN is_borrowed = 1 THEN 0 ELSE 1 END WHERE available_copies IS NULL")
    conn.commit()
    conn.close()

def sync_excel_to_sqlite():
    try:
        if os.path.exists(excel_file):
            df = pd.read_excel(excel_file, sheet_name=SHEET_NAME, dtype=str)
            df = df.fillna("")
            df.columns = df.columns.str.strip()
            
            df = df[[col for col in EXCEL_COLUMNS if col in df.columns]]
            df.columns = ['book_code', 'author_name', 'book_title', 'category', 'publication_year']
            
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()

            existing_copies = {}
            try:
                cursor.execute("SELECT book_code, total_copies, available_copies FROM books")
                for code, total, available in cursor.fetchall():
                    existing_copies[code] = (total, available)
            except sqlite3.OperationalError:
                pass 

            cursor.execute("DROP TABLE IF EXISTS books")
            
            df.to_sql("books", conn, if_exists="replace", index=False, dtype={
                'book_code': 'TEXT PRIMARY KEY',
                'author_name': 'TEXT',
                'book_title': 'TEXT',
                'category': 'TEXT',
                'publication_year': 'TEXT',
                'is_borrowed': 'INTEGER'
            })
            conn.commit()
            conn.close()
            ensure_books_schema()

            if existing_copies:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                for code, (total, available) in existing_copies.items():
                    cursor.execute(
                        "UPDATE books SET total_copies = ?, available_copies = ? WHERE book_code = ?",
                        (total, available, code)
                    )
                conn.commit()
                conn.close()

            print(f"Successfully synced spreadsheet metrics from '{SHEET_NAME}'.")
        else:
            ensure_books_schema()
    except Exception as e:
        print(f"Database background sync failure initialization error: {e}")

def sync_sqlite_to_excel():
    try:
        conn = sqlite3.connect(db_file)
        df = pd.read_sql_query("SELECT book_code, author_name, book_title, category, publication_year FROM books", conn)
        conn.close()
        
        df.columns = EXCEL_COLUMNS
        
        with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name=SHEET_NAME)
    except Exception as e:
        messagebox.showerror("Sync Error", f"Could not push modifications back to Excel file source: {e}")

def initialize_database():
    ensure_books_schema()
    sync_excel_to_sqlite()

import threading
threading.Thread(target=initialize_database, daemon=True).start()

# ===================== WINDOW INITIALIZATION =====================

def open_screen(parent):
    global SCREEN_H, SCREEN_W, app, book_image_label, btn_add, btn_clear, btn_delete, btn_refresh, btn_reset, btn_update
    global entry_author, entry_category, entry_code, entry_copies, entry_search, entry_title, entry_year, filter_combobox
    global tree, current_image_request
    
    app = ctk.CTkToplevel(parent)
    app.attributes("-fullscreen", True)
    app.configure(fg_color=PAGE_BG)
    app.bind("<Escape>", lambda event: theme.exit_program(app))
    app.title("Book Inventory System")

    SCREEN_W = app.winfo_screenwidth()
    SCREEN_H = app.winfo_screenheight()

    # ===================== CANVAS FRAMEWORK =====================
    main_canvas = tk.Canvas(app, width=SCREEN_W, height=SCREEN_H, bg=PAGE_BG, bd=0, highlightthickness=0)
    main_canvas.pack(fill="both", expand=True)

    try:
        theme.build_header(app, main_canvas)
    except Exception as e:
        messagebox.showerror("Theme Error", f"Error: {e}")
        app.destroy()
        return

    # MAIN CONTENT CONTAINER
    content_frame = ctk.CTkFrame(app, fg_color=PAGE_BG, corner_radius=0)
    main_canvas.create_window(SCREEN_W // 2, (SCREEN_H + 60) // 2, window=content_frame, width=SCREEN_W - 80, height=SCREEN_H - 120)

    # ===================== CONTROLLER LOGIC =====================

    def fetch_books(search_query="", filter_column="All Columns"):
        selected_item = tree.selection()
        selected_code = tree.item(selected_item[0], 'values')[0] if selected_item else None

        for row in tree.get_children():
            tree.delete(row)
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            query_str = (
                "SELECT book_code, author_name, book_title, category, publication_year, "
                "COALESCE(is_borrowed, 0), COALESCE(total_copies, 1), COALESCE(available_copies, 1) "
                "FROM books"
            )
            params = []
            col_map = {
                "Book Code": "book_code",
                "Author Name": "author_name",
                "Book Title": "book_title",
                "Category": "category",
                "Publication Year": "publication_year"
            }
            if search_query:
                target_col = col_map.get(filter_column)
                if target_col:
                    query_str += f" WHERE {target_col} LIKE ?"
                    params.append(f"%{search_query}%")
                else:
                    query_str += " WHERE book_code LIKE ? OR author_name LIKE ? OR book_title LIKE ? OR category LIKE ? OR publication_year LIKE ?"
                    params = [f"%{search_query}%"] * 5
                
            cursor.execute(query_str, params)
            rows = cursor.fetchall()
            conn.close()
        
            for row in rows:
                total_copies = int(row[6]) if row[6] is not None else 1
                available_copies = int(row[7]) if row[7] is not None else 1
                copies_display = f"{available_copies}/{total_copies}"
                is_fully_borrowed = available_copies <= 0
                tags = ("borrowed",) if is_fully_borrowed else ()
                display_row = row[:5] + (copies_display,)
                item_id = tree.insert("", "end", values=display_row, tags=tags)
                if selected_code and row[0] == selected_code:
                    tree.selection_set(item_id)
        except Exception as e:
            print(f"Error accessing interactive table dataset: {e}")

    def on_search_refresh():
        query = entry_search.get().strip()
        crit = filter_combobox.get()
        fetch_books(query, crit)

    def set_fields_state(state="readonly"):
        text_col = TEXT_SUB if state == "readonly" else TEXT_MAIN
        for entry in [entry_code, entry_author, entry_title, entry_category, entry_year, entry_copies]:
            entry.configure(state=state, text_color=text_col)

    def unlock_for_editing():
        set_fields_state("normal")
        if tree.focus():
            entry_code.configure(state="readonly", text_color=TEXT_SUB)
        if 'btn_edit' in globals() or 'btn_edit' in locals():
            btn_edit.configure(text="LOCK DETAILS", fg_color="#6B7280", hover_color="#4B5563")

    def toggle_edit_lock():
        if not tree.focus():
            messagebox.showwarning("Select Book", "Please select a book row from the table to edit.")
            return
        curr = entry_title.cget("state")
        if curr == "readonly":
            unlock_for_editing()
            messagebox.showinfo("Details Unlocked", "Book details unlocked for editing. Make your changes and click 'SAVE'.")
        else:
            set_fields_state("readonly")
            btn_edit.configure(text="EDIT DETAILS", fg_color="#F59E0B", hover_color="#D97706")

    def on_select_row(event):
        selected = tree.focus()
        if not selected:
            return
        values = tree.item(selected, 'values')
        if values:
            book_code = values[0]
            book_author = values[1]
            book_title = values[2]
        
            set_fields_state("normal")
            entry_code.delete(0, tk.END)
            entry_code.insert(0, book_code)
        
            entry_author.delete(0, tk.END)
            entry_author.insert(0, book_author)
        
            entry_title.delete(0, tk.END)
            entry_title.insert(0, book_title)
        
            entry_category.delete(0, tk.END)
            entry_category.insert(0, values[3])
        
            entry_year.delete(0, tk.END)
            entry_year.insert(0, values[4])

            copies_display = values[5] if len(values) > 5 else "1/1"
            total_copies_str = copies_display.split("/")[-1] if "/" in str(copies_display) else "1"
            entry_copies.delete(0, tk.END)
            entry_copies.insert(0, total_copies_str)
        
            load_book_image(book_code, book_title, book_author)
            set_fields_state("readonly")
            if 'btn_edit' in globals() or 'btn_edit' in locals():
                btn_edit.configure(text="EDIT DETAILS", fg_color="#F59E0B", hover_color="#D97706")

    def load_book_image(book_code, book_title, book_author):
        bookimageapi.load_cover_into_label(
            book_image_label,
            current_image_request,
            book_code,
            book_title,
            book_author,
            thumb_size=(160, 160),
        )

    def clear_form_fields():
        global current_image_request
        current_image_request["id"] += 1
        current_image_request["book_code"] = None
        
        for item in tree.selection():
            tree.selection_remove(item)
            
        set_fields_state("normal")
        entry_code.delete(0, tk.END)
        entry_author.delete(0, tk.END)
        entry_title.delete(0, tk.END)
        entry_category.delete(0, tk.END)
        entry_year.delete(0, tk.END)
        entry_copies.delete(0, tk.END)
        entry_copies.insert(0, "1")
        book_image_label.configure(
            image="",
            text="Book Cover\n(Click a book to load)"
        )
        if 'btn_edit' in globals() or 'btn_edit' in locals():
            btn_edit.configure(text="EDIT DETAILS", fg_color="#F59E0B", hover_color="#D97706")

    def add_book_record():
        b_code = entry_code.get().strip()
        author = entry_author.get().strip()
        title = entry_title.get().strip()
        category = entry_category.get().strip()
        year = entry_year.get().strip()
        copies_text = entry_copies.get().strip()

        if not title:
            messagebox.showwarning("Incomplete Data", "Please provide at least a Book Title to add a new entry.")
            return

        if not b_code:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT book_code FROM books")
                codes = [row[0] for row in cursor.fetchall()]
                conn.close()
                max_num = 1000
                for code in codes:
                    parts = code.split('-')
                    if len(parts) >= 3 and parts[-1].isdigit():
                        num = int(parts[-1])
                        if num > max_num:
                            max_num = num
                cat_prefix = (category[:3].upper() if len(category) >= 3 else "GEN")
                b_code = f"BK-{cat_prefix}-{max_num + 1}"
            except Exception:
                b_code = "BK-GEN-1001"

        try:
            total_copies = max(1, int(copies_text)) if copies_text else 1
        except ValueError:
            messagebox.showwarning("Invalid Copies", "Total Copies must be a whole number. Defaulting to 1.")
            total_copies = 1

        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO books (book_code, author_name, book_title, category, publication_year, total_copies, available_copies)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (b_code, author, title, category, year, total_copies, total_copies))
            conn.commit()
            conn.close()

            sync_sqlite_to_excel()
            clear_form_fields()
            on_search_refresh()
            messagebox.showinfo("Success", f"Book '{b_code}' has been added to the inventory.")
        except sqlite3.IntegrityError:
            messagebox.showwarning("Duplicate Entry", f"Book Code '{b_code}' already exists.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed adding new record: {e}")

    def update_book_record():
        b_code = entry_code.get().strip()
        author = entry_author.get().strip()
        title = entry_title.get().strip()
        category = entry_category.get().strip()
        year = entry_year.get().strip()
        copies_text = entry_copies.get().strip()

        if not b_code or not title:
            messagebox.showwarning("Incomplete Data", "Please select a valid book row entry and provide a title.")
            return

        try:
            new_total = max(1, int(copies_text)) if copies_text else 1
        except ValueError:
            messagebox.showwarning("Invalid Copies", "Total Copies must be a whole number.")
            return

        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("SELECT COALESCE(total_copies, 1), COALESCE(available_copies, 1) FROM books WHERE book_code = ?", (b_code,))
            existing = cursor.fetchone()
            old_total, old_available = existing if existing else (1, 1)
            borrowed_out = max(0, old_total - old_available)
            new_available = max(0, new_total - borrowed_out)

            cursor.execute('''
                UPDATE books 
                SET author_name = ?, book_title = ?, category = ?, publication_year = ?,
                    total_copies = ?, available_copies = ?
                WHERE book_code = ?
            ''', (author, title, category, year, new_total, new_available, b_code))
            conn.commit()
            conn.close()
        
            sync_sqlite_to_excel()
            on_search_refresh()
            set_fields_state("readonly")
            if 'btn_edit' in globals() or 'btn_edit' in locals():
                btn_edit.configure(text="EDIT DETAILS", fg_color="#F59E0B", hover_color="#D97706")
            messagebox.showinfo("Success", f"Book '{b_code}' info has been updated.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed updating database: {e}")

    def delete_book_record():
        b_code = entry_code.get().strip()
        if not b_code:
            messagebox.showwarning("Selection Missing", "Please select an active row to delete first.")
            return
        
        confirm = messagebox.askyesno("Confirm Action", f"Are you sure you want to delete Book '{b_code}'?")
        if confirm:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM books WHERE book_code = ?", (b_code,))
                conn.commit()
                conn.close()
            
                sync_sqlite_to_excel()
                clear_form_fields()
                on_search_refresh()
                messagebox.showinfo("Data Purged", "The entry row track has been dropped successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed removing record: {e}")

    def clear_all_books_inventory():
        pwd = ctk.CTkInputDialog(text="Enter authorization code to clear ALL inventory:", title="Authorization Required").get_input()
        if pwd == "delasallearaneta":
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM books")
                conn.commit()
                conn.close()
                sync_sqlite_to_excel()
                clear_form_fields()
                on_search_refresh()
                messagebox.showinfo("Success", "All books have been permanently cleared from the inventory.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear inventory: {e}")
        elif pwd is not None:
            messagebox.showerror("Unauthorized", "Incorrect authorization code.")

    def reset_all_borrowed_books():
        confirm = messagebox.askyesno(
            "Reset Borrowed Books",
            "This will mark all borrowed books as available and clear all borrowing records. Continue?"
        )
        if not confirm: return
        try:
            ensure_books_schema()
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("UPDATE books SET is_borrowed = 0, available_copies = COALESCE(total_copies, 1)")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS borrow_records (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_code TEXT NOT NULL, book_title TEXT NOT NULL, student_name TEXT, student_id TEXT, student_email TEXT,
                    borrow_date DATE NOT NULL, return_date DATE NOT NULL, actual_return_date DATE, status TEXT DEFAULT 'borrowed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute("DELETE FROM borrow_records")
            conn.commit()
            conn.close()
            sync_sqlite_to_excel()
            clear_form_fields()
            on_search_refresh()
            messagebox.showinfo("Reset Complete", "All borrowed books are now available and borrowing records were cleared.")
        except Exception as e:
            messagebox.showerror("Reset Error", f"Failed to reset borrowed books: {e}")

    # ===================== UI STYLING SETUP =====================
    theme.setup_modern_treeview_style()
    
    # Custom tags for the Treeview
    tree_tags = {"borrowed": {"foreground": "#DC2626", "background": "#FEF2F2"}}

    # ===================== LEFT PANEL: SEARCH & DATATABLE VIEW =====================
    left_panel = ctk.CTkFrame(content_frame, fg_color=CARD_BG, corner_radius=15, border_width=1, border_color="#E2E8F0")
    left_panel.pack(side="left", fill="both", expand=True, padx=(10, 20), pady=10)

    # Search Bar
    search_bar_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
    search_bar_frame.pack(fill="x", side="top", pady=20, padx=20)

    label_search = ctk.CTkLabel(search_bar_frame, text="Search Inventory:", font=("Segoe UI", 14, "bold"), text_color=TEXT_MAIN)
    label_search.pack(side="left", padx=(0, 10))

    entry_search = ctk.CTkEntry(search_bar_frame, font=("Segoe UI", 14), width=250, fg_color=PAGE_BG, border_color="#E2E8F0", text_color=TEXT_MAIN)
    entry_search.pack(side="left", padx=5)
    entry_search.bind("<KeyRelease>", lambda e: on_search_refresh())

    filter_combobox = ctk.CTkOptionMenu(search_bar_frame, font=("Segoe UI", 12), values=["All Columns"] + EXCEL_COLUMNS, 
                                        fg_color=PAGE_BG, button_color=theme.PRIMARY, button_hover_color=PRIMARY_HOVER, 
                                        text_color=TEXT_MAIN)
    filter_combobox.set("All Columns")
    filter_combobox.pack(side="left", padx=10)
    # CTkOptionMenu doesn't bind ComboboxSelected, use command callback
    filter_combobox.configure(command=lambda e: on_search_refresh())

    btn_refresh = ctk.CTkButton(search_bar_frame, text="REFRESH", font=("Segoe UI", 12, "bold"), text_color="white", fg_color=theme.PRIMARY, hover_color=PRIMARY_HOVER, command=on_search_refresh, width=100)
    btn_refresh.pack(side="left", padx=5)

    # Treeview Container
    table_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    columns_def = ("book_code", "author_name", "book_title", "category", "publication_year", "copies")
    tree = ttk.Treeview(table_frame, columns=columns_def, show="headings", selectmode="browse")
    tree.tag_configure("borrowed", foreground="#DC2626", background="#FEF2F2")

    tree.heading("book_code", text="BOOK CODE")
    tree.heading("author_name", text="AUTHOR NAME")
    tree.heading("book_title", text="BOOK TITLE")
    tree.heading("category", text="CATEGORY")
    tree.heading("publication_year", text="YEAR")
    tree.heading("copies", text="COPIES")

    tree.column("book_code", width=110, anchor="center")
    tree.column("author_name", width=180, anchor="w")
    tree.column("book_title", width=250, anchor="w")
    tree.column("category", width=130, anchor="w")
    tree.column("publication_year", width=90, anchor="center")
    tree.column("copies", width=130, anchor="center")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    tree.bind("<<TreeviewSelect>>", on_select_row)

    current_image_request = {"id": 0, "book_code": None}

    # ===================== RIGHT PANEL: CONSOLE EDITOR FORM =====================
    right_panel = ctk.CTkFrame(content_frame, fg_color=CARD_BG, corner_radius=15, border_width=1, border_color="#E2E8F0", width=400)
    right_panel.pack(side="right", fill="y", padx=10, pady=10)
    right_panel.pack_propagate(False)

    panel_title = ctk.CTkLabel(right_panel, text="RECORD DATA EDITOR", font=("Segoe UI", 14, "bold"), fg_color=theme.PRIMARY, text_color="white", corner_radius=15)
    panel_title.pack(fill="x", side="top", ipady=10)

    # BOOK COVER
    image_frame = ctk.CTkFrame(right_panel, fg_color="transparent", height=120)
    image_frame.pack(fill="x", padx=15, pady=(15, 5))
    image_frame.pack_propagate(False)

    book_image_label = ctk.CTkLabel(image_frame, text="Book Cover\n(Click a book to load)", fg_color=PAGE_BG, text_color=TEXT_SUB, font=("Segoe UI", 11), corner_radius=8)
    book_image_label.pack(fill="both", expand=True)

    form_container = ctk.CTkFrame(right_panel, fg_color="transparent")
    form_container.pack(fill="both", expand=True, padx=25, pady=10)

    def append_form_element(label_text):
        lbl = ctk.CTkLabel(form_container, text=label_text, font=("Segoe UI", 11, "bold"), text_color=TEXT_SUB)
        lbl.pack(anchor="w", pady=(5, 0))
        ent = ctk.CTkEntry(form_container, font=("Segoe UI", 12), fg_color=PAGE_BG, border_color="#E2E8F0", text_color=TEXT_MAIN)
        ent.pack(fill="x", ipady=3, pady=(0, 2))
        return ent

    entry_code = append_form_element("Book Code (Reference Locked)")
    entry_author = append_form_element("Author Name (Reference Locked)")
    entry_title = append_form_element("Book Title (Reference Locked)")
    entry_category = append_form_element("Category / Genre (Reference Locked)")
    entry_year = append_form_element("Publication Year (Reference Locked)")
    entry_copies = append_form_element("Total Copies (Reference Locked)")
    entry_copies.insert(0, "1")

    # Set initial fields state to readonly
    for entry in [entry_code, entry_author, entry_title, entry_category, entry_year, entry_copies]:
        entry.configure(state="readonly", text_color=TEXT_SUB)

    # ACTION BUTTONS
    actions_frame = ctk.CTkFrame(form_container, fg_color="transparent")
    actions_frame.pack(fill="x", side="bottom", pady=(5, 0))

    row1 = ctk.CTkFrame(actions_frame, fg_color="transparent")
    row1.pack(fill="x", pady=2)
    btn_edit = ctk.CTkButton(row1, text="EDIT DETAILS", font=("Segoe UI", 11, "bold"), height=32, text_color="white", fg_color="#F59E0B", hover_color="#D97706", command=toggle_edit_lock)
    btn_edit.pack(side="left", fill="x", expand=True, padx=(0, 4))
    btn_update = ctk.CTkButton(row1, text="SAVE", font=("Segoe UI", 11, "bold"), height=32, text_color="white", fg_color=theme.PRIMARY, hover_color=PRIMARY_HOVER, command=update_book_record)
    btn_update.pack(side="right", fill="x", expand=True, padx=(4, 0))

    row2 = ctk.CTkFrame(actions_frame, fg_color="transparent")
    row2.pack(fill="x", pady=2)
    btn_add = ctk.CTkButton(row2, text="+ ADD BOOK", font=("Segoe UI", 11, "bold"), height=32, text_color="white", fg_color=theme.PRIMARY, hover_color=PRIMARY_HOVER, command=add_book_record)
    btn_add.pack(side="left", fill="x", expand=True, padx=(0, 4))
    btn_delete = ctk.CTkButton(row2, text="REMOVE", font=("Segoe UI", 11, "bold"), height=32, text_color="white", fg_color="#E74C3C", hover_color="#C0392B", command=delete_book_record)
    btn_delete.pack(side="right", fill="x", expand=True, padx=(4, 0))

    # row3 (Reset Borrowed, Clear All) removed and moved to Developer Tools (Demo Menu)

    # ===================== INIT RUN STATE =====================
    on_search_refresh()

    def auto_refresh_inventory():
        if not tree.selection():
            on_search_refresh()
        app.after(3000, auto_refresh_inventory)
    
    app.after(3000, auto_refresh_inventory)

    app.grab_set()
    return app

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    try:
        open_screen(root)
        root.mainloop()
    except Exception as e:
        import traceback
        with open("crash.txt", "w") as f:
            traceback.print_exc(file=f)
        raise
