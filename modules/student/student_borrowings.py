import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from utils import student_db
from utils import qr_borrow
from utils import bookimageapi
from PIL import Image, ImageTk, ImageDraw
import threading
from utils import theme
try:
    from utils import sweetalert as messagebox
except ImportError:
    pass

def create_fallback_image(text, size=(200, 300)):
    w, h = size
    img = Image.new("RGBA", size, (243, 244, 246, 255)) # Light Gray
    draw = ImageDraw.Draw(img)
    letter = (text.strip() or "?")[0].upper()
    try:
        bbox = draw.textbbox((0, 0), letter)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((w - tw) / 2 - bbox[0], (h - th) / 2 - bbox[1]), letter, fill=(156, 163, 175, 255))
    except Exception:
        pass
    return ImageTk.PhotoImage(img)

PAGE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
BRAND = "#10312B"
BRAND_HOVER = "#1B5349"
DANGER = "#EF4444"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
INFO = "#3B82F6"
FONT_FAMILY = "Segoe UI"

def open_screen(parent, logged_in_email):
    app = ctk.CTkToplevel(parent)
    app.attributes("-fullscreen", True)
    app.configure(fg_color=PAGE_BG)
    app.title("My Borrowings")
    
    def safe_destroy(event=None):
        app.withdraw()
        app.destroy()
        
    app.bind("<Escape>", safe_destroy)
    
    SCREEN_W = app.winfo_screenwidth()
    
    # Header
    header_canvas = tk.Canvas(app, width=SCREEN_W, height=70, bg=BRAND, highlightthickness=0, bd=0)
    header_canvas.pack(fill="x", side="top")
    
    exit_btn = ctk.CTkButton(
        app, text="✕", font=(FONT_FAMILY, 20, "bold"), width=40, height=40,
        corner_radius=8, fg_color="transparent", bg_color=BRAND, text_color="white", hover_color="#E81123",
        command=safe_destroy
    )
    header_canvas.create_window(SCREEN_W - 30, 35, window=exit_btn, anchor="e")
    
    back_btn = ctk.CTkButton(
        app, text="RETURN TO DASHBOARD", font=(FONT_FAMILY, 10, "bold"), width=160, height=40,
        corner_radius=8, fg_color="#F3F7F6", bg_color=BRAND, text_color=BRAND, hover_color="#FFFFFF",
        command=safe_destroy
    )
    header_canvas.create_window(120, 35, window=back_btn, anchor="center")
    
    # Main Content Layout
    main_frame = ctk.CTkFrame(app, fg_color="transparent")
    main_frame.pack(fill="both", expand=True, padx=40, pady=40)
    
    left_col = ctk.CTkFrame(main_frame, fg_color="transparent")
    left_col.pack(side="left", fill="both", expand=True, padx=(0, 20))
    
    right_col = ctk.CTkFrame(main_frame, fg_color=CARD_BG, corner_radius=16, width=380)
    right_col.pack(side="right", fill="y")
    right_col.pack_propagate(False)
    
    content = left_col  # Alias for existing code
    
    ctk.CTkLabel(content, text="Your Reading Journey", font=(FONT_FAMILY, 32, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 20))
    
    # Custom Tabs
    tab_frame = ctk.CTkFrame(content, fg_color="#F1F5F9", corner_radius=20, height=50)
    tab_frame.pack(anchor="w", pady=(0, 20))
    
    current_tab = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=16)
    history_tab = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=16)
    
    def show_tab(tab_name):
        if tab_name == "current":
            history_tab.pack_forget()
            current_tab.pack(fill="both", expand=True)
            btn_current.configure(fg_color=BRAND, text_color="white")
            btn_history.configure(fg_color="transparent", text_color=TEXT_SUB)
        else:
            current_tab.pack_forget()
            history_tab.pack(fill="both", expand=True)
            btn_history.configure(fg_color=BRAND, text_color="white")
            btn_current.configure(fg_color="transparent", text_color=TEXT_SUB)
            
    btn_current = ctk.CTkButton(tab_frame, text="Current Borrowings", font=(FONT_FAMILY, 14, "bold"), fg_color=BRAND, text_color="white", corner_radius=20, height=40, command=lambda: show_tab("current"))
    btn_current.pack(side="left", padx=5, pady=5)
    
    btn_history = ctk.CTkButton(tab_frame, text="Borrowing History", font=(FONT_FAMILY, 14, "bold"), fg_color="transparent", text_color=TEXT_SUB, hover_color="#E2E8F0", corner_radius=20, height=40, command=lambda: show_tab("history"))
    btn_history.pack(side="left", padx=5, pady=5)
    
    theme.setup_modern_treeview_style()
    
    # --- Current Borrowings Tab ---
    columns = ("title", "borrow_date", "due_date", "fine")
    tree_current = ttk.Treeview(current_tab, columns=columns, show="headings", selectmode="extended")
    tree_current.heading("title", text="BOOK TITLE")
    tree_current.heading("borrow_date", text="BORROW DATE")
    tree_current.heading("due_date", text="DUE DATE")
    tree_current.heading("fine", text="ACCUMULATED FINE")
    
    tree_current.column("title", width=400, anchor="w")
    tree_current.column("borrow_date", width=150, anchor="center")
    tree_current.column("due_date", width=150, anchor="center")
    tree_current.column("fine", width=150, anchor="center")
    
    scroll_c = ttk.Scrollbar(current_tab, orient="vertical", command=tree_current.yview)
    tree_current.configure(yscrollcommand=scroll_c.set)
    scroll_c.pack(side="right", fill="y", pady=20, padx=(0,10))
    tree_current.pack(fill="both", expand=True, padx=20, pady=20)
    
    tree_current.tag_configure("danger", foreground=DANGER, font=(FONT_FAMILY, 12, "bold"))
    tree_current.tag_configure("safe", foreground=SUCCESS)
    
    current_books = student_db.get_student_current_borrowings(logged_in_email)
    for record in current_books:
        record_id, book_code, book_title, borrow_date, return_date, status, fine_paid = record
        fine = 0 if fine_paid else student_db.calculate_fine(return_date)
        fine_text = "Paid" if fine_paid else (f"₱{fine}" if fine > 0 else "None")
        tag = "danger" if fine > 0 else "safe"
        tree_current.insert("", "end", values=(book_title, borrow_date, return_date, fine_text), tags=(str(record_id), tag))
        
        
    
    # --- History Tab ---
    hist_cols = ("title", "borrow_date", "due_date", "returned_date", "status")
    tree_hist = ttk.Treeview(history_tab, columns=hist_cols, show="headings", selectmode="browse")
    tree_hist.heading("title", text="BOOK TITLE")
    tree_hist.heading("borrow_date", text="BORROW DATE")
    tree_hist.heading("due_date", text="DUE DATE")
    tree_hist.heading("returned_date", text="RETURNED DATE")
    tree_hist.heading("status", text="STATUS")
    
    tree_hist.column("title", width=350, anchor="w")
    tree_hist.column("borrow_date", width=120, anchor="center")
    tree_hist.column("due_date", width=120, anchor="center")
    tree_hist.column("returned_date", width=120, anchor="center")
    tree_hist.column("status", width=150, anchor="center")
    
    tree_hist.tag_configure("returned", foreground=SUCCESS, font=(FONT_FAMILY, 12, "bold"))
    tree_hist.tag_configure("borrowed", foreground=INFO, font=(FONT_FAMILY, 12, "bold"))
    tree_hist.tag_configure("lost", foreground=DANGER, font=(FONT_FAMILY, 12, "bold"))
    tree_hist.tag_configure("damaged", foreground=WARNING, font=(FONT_FAMILY, 12, "bold"))
    
    scroll_h = ttk.Scrollbar(history_tab, orient="vertical", command=tree_hist.yview)
    tree_hist.configure(yscrollcommand=scroll_h.set)
    scroll_h.pack(side="right", fill="y", pady=20, padx=(0,10))
    tree_hist.pack(fill="both", expand=True, padx=20, pady=20)
    
    history_records = student_db.get_student_borrow_history(logged_in_email)
    for record in history_records:
        record_id, book_code, book_title, borrow_date, return_date, actual_return_date, status = record
        returned_date = actual_return_date if status == 'returned' else "—"
        
        tag_match = status.lower()
        if "return_requested" in tag_match:
            tag_match = "borrowed"
        elif "overdue" in tag_match:
            tag_match = "lost" # use red
            
        tree_hist.insert("", "end", values=(book_title, borrow_date, return_date, returned_date, status.upper()), tags=(tag_match,))
        
    # Right Column: Book Details, Image & Return Queue
    ctk.CTkLabel(right_col, text="Selected Book", font=(FONT_FAMILY, 20, "bold"), text_color=TEXT_MAIN).pack(pady=(10, 2))
    
    img_canvas = tk.Canvas(right_col, width=120, height=180, bg=CARD_BG, highlightthickness=0)
    img_canvas.pack(pady=2)
    
    app.current_img = create_fallback_image("B")
    img_canvas.create_image(60, 90, image=app.current_img)
    
    selected_lbl = ctk.CTkLabel(right_col, text="No book selected", font=(FONT_FAMILY, 14, "bold"), text_color=BRAND, wraplength=320, justify="center")
    selected_lbl.pack(pady=(2, 0))

    status_lbl = ctk.CTkLabel(right_col, text="Select a book to view details.", font=(FONT_FAMILY, 12), text_color=TEXT_SUB, wraplength=320, justify="center")
    status_lbl.pack(pady=(0, 5))
    
    # Return Queue UI
    queue_frame = ctk.CTkFrame(right_col, fg_color="#F8FAFC", corner_radius=12)
    queue_frame.pack(fill="both", expand=True, padx=20, pady=5)
    
    ctk.CTkLabel(queue_frame, text="Return Queue", font=(FONT_FAMILY, 14, "bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=15, pady=(10, 5))
    
    queue_listbox = tk.Listbox(queue_frame, bg="#FFFFFF", fg=TEXT_MAIN, font=(FONT_FAMILY, 11), selectbackground=BRAND, selectforeground="white", borderwidth=1, relief="solid")
    queue_listbox.pack(fill="both", expand=True, padx=15, pady=(0, 10))
    
    def update_image(title, status_text=""):
        selected_lbl.configure(text=title)
        status_lbl.configure(text=status_text)
        
        img_canvas.delete("all")
        img_canvas.create_text(60, 90, text="Loading image...", fill=TEXT_SUB, font=(FONT_FAMILY, 10))
        
        app.current_fetch_id = getattr(app, "current_fetch_id", 0) + 1
        my_fetch_id = app.current_fetch_id
        
        def fetch():
            if my_fetch_id != app.current_fetch_id: return
            try:
                img = bookimageapi.fetch_book_image(title)
                if my_fetch_id != app.current_fetch_id: return
                
                if img:
                    img = img.convert("RGBA")
                    img.thumbnail((120, 180), Image.Resampling.LANCZOS)
                    mask = Image.new("L", img.size, 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=8, fill=255)
                    img.putalpha(mask)
                    photo = ImageTk.PhotoImage(img)
                    def update_success():
                        if my_fetch_id != app.current_fetch_id: return
                        app.current_img = photo
                        img_canvas.delete("all")
                        img_canvas.create_image(60, 90, image=photo)
                    app.after(0, update_success)
                else:
                    def update_fail():
                        if my_fetch_id != app.current_fetch_id: return
                        app.current_img = create_fallback_image(title)
                        img_canvas.delete("all")
                        img_canvas.create_image(60, 90, image=app.current_img)
                    app.after(0, update_fail)
            except Exception:
                def update_err():
                    if my_fetch_id != app.current_fetch_id: return
                    app.current_img = create_fallback_image(title)
                    img_canvas.delete("all")
                    img_canvas.create_image(60, 90, image=app.current_img)
                app.after(0, update_err)
                
        threading.Thread(target=fetch, daemon=True).start()

    def on_select_current(event):
        selected = tree_current.selection()
        if selected:
            item = tree_current.item(selected[-1])
            title = item["values"][0]
            update_image(title, "Status: Currently Borrowed")
            
    def on_select_history(event):
        selected = tree_hist.selection()
        if selected:
            item = tree_hist.item(selected[-1])
            title = item["values"][0]
            status = item["values"][4]
            update_image(title, f"Status: {status}")

    tree_current.bind("<<TreeviewSelect>>", on_select_current)
    tree_hist.bind("<<TreeviewSelect>>", on_select_history)

    show_tab("current")
    
    app.return_cart = []
    
    def refresh_queue_list():
        queue_listbox.delete(0, tk.END)
        for i, item in enumerate(app.return_cart):
            queue_listbox.insert(tk.END, f"{i+1}. {item['title']}")
            
    def add_to_queue():
        selected = tree_current.selection()
        if not selected:
            messagebox.showwarning("Select Book", "Please select a book from your current borrowings first.")
            return
            
        for sel in selected:
            item = tree_current.item(sel)
            record_id = item["tags"][0]
            title = item["values"][0]
            
            if any(x['record_id'] == record_id for x in app.return_cart):
                continue
                
            app.return_cart.append({"record_id": record_id, "title": title})
            
        refresh_queue_list()
        
    def remove_from_queue():
        sel_indices = list(queue_listbox.curselection())
        if not sel_indices:
            messagebox.showwarning("Select Book", "Please select a book from the Return Queue to remove.")
            return
        
        sel_indices.sort(reverse=True)
        for i in sel_indices:
            del app.return_cart[i]
        refresh_queue_list()

    def submit_returns():
        if not app.return_cart:
            messagebox.showwarning("Queue Empty", "Please add books to the Return Queue first.")
            return
            
        if not messagebox.askyesno("Confirm Return", f"Submit a return request for {len(app.return_cart)} book(s)?"):
            return
            
        student_db.ensure_books_schema()
        student_db.ensure_borrow_records_schema()
        success_count = 0
        try:
            with student_db.get_db_connection(student_db.BOOKS_DB) as conn:
                cursor = conn.cursor()
                for cart_item in app.return_cart:
                    cursor.execute("UPDATE borrow_records SET status = 'return_requested' WHERE record_id = ?", (cart_item['record_id'],))
                    success_count += 1
                conn.commit()
            student_db.sync_borrow_status_to_excel()
            messagebox.showinfo("Return Requested", f"Your return request for {success_count} book(s) is pending admin approval.")
            
            app.withdraw()
            app.destroy()
            open_screen(parent, logged_in_email)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to mark book(s) as returned: {e}")

    def download_receipt():
        selected_curr = tree_current.selection()
        selected_hist = tree_hist.selection()
        if not selected_curr and not selected_hist:
            messagebox.showwarning("Select Book", "Please select a borrowed book from the list to generate a receipt.")
            return
            
        user_info = student_db.get_current_user_info(logged_in_email)
        if selected_curr:
            item = tree_current.item(selected_curr[-1])
            book_title = item["values"][0]
            borrow_date = item["values"][1]
            due_date = item["values"][2]
            record_id = item["tags"][0] if item["tags"] else "N/A"
        else:
            item = tree_hist.item(selected_hist[-1])
            book_title = item["values"][0]
            borrow_date = item["values"][1]
            due_date = item["values"][2]
            record_id = "HIST"

        txn_dict = {
            "transaction_id": f"REC-{record_id}",
            "user_id": user_info.get("student_id", "N/A"),
            "user_name": user_info.get("name", "N/A"),
            "book_title": book_title,
            "borrow_date": borrow_date,
            "due_date": due_date,
        }
        qr_borrow.print_receipt(txn_dict, parent=app)

    btn_row_1 = ctk.CTkFrame(right_col, fg_color="transparent")
    btn_row_1.pack(fill="x", padx=20, pady=(0, 5))
    
    ctk.CTkButton(btn_row_1, text="Add to Queue", command=add_to_queue, font=(FONT_FAMILY, 12, "bold"), fg_color=BRAND, hover_color=BRAND_HOVER, height=32, corner_radius=8).pack(side="left", fill="x", expand=True, padx=(0, 5))
    ctk.CTkButton(btn_row_1, text="Remove", command=remove_from_queue, font=(FONT_FAMILY, 12, "bold"), fg_color=DANGER, hover_color="#B91C1C", height=32, corner_radius=8).pack(side="right", fill="x", expand=True, padx=(5, 0))

    actions_frame = ctk.CTkFrame(right_col, fg_color="transparent")
    actions_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 20))

    ctk.CTkButton(actions_frame, text="Download Receipt", command=download_receipt, font=(FONT_FAMILY, 13, "bold"), fg_color="#2563EB", hover_color="#1D4ED8", height=35, corner_radius=8).pack(fill="x", pady=(0, 5))
    ctk.CTkButton(actions_frame, text="Submit Returns", command=submit_returns, font=(FONT_FAMILY, 14, "bold"), fg_color=BRAND, hover_color=BRAND_HOVER, height=45, corner_radius=10).pack(fill="x")
    
    return app

if __name__ == "__main__":
    import sys
    import os
    # Add the root directory to sys.path to allow importing utils
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    
    # Initialize a dummy root window
    root = ctk.CTk()
    root.withdraw() # Hide the root window since open_screen creates a Toplevel
    # Provide a dummy logged_in_email for testing
    app = open_screen(root, "test@student.com")
    root.mainloop()

