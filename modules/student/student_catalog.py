import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import datetime
import tkcalendar
from utils import student_db
from utils import bookimageapi
from utils import qr_borrow
from PIL import Image, ImageTk, ImageDraw
from utils import theme
try:
    from utils import sweetalert as messagebox
except ImportError:
    pass

PAGE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
BRAND = "#10312B"
BRAND_HOVER = "#1B5349"
AVAILABLE_COLOR = "#10B981"
BORROWED_COLOR = "#9CA3AF"
DANGER = "#EF4444"
FONT_FAMILY = "Segoe UI"

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

def open_screen(parent, logged_in_email):
    app = ctk.CTkToplevel(parent)
    app.borrow_cart = []
    app.attributes("-fullscreen", True)
    app.configure(fg_color=PAGE_BG)
    app.title("Library Catalog")
    
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
    
    # Layout Main Frame
    main_frame = ctk.CTkFrame(app, fg_color="transparent")
    main_frame.pack(fill="both", expand=True, padx=40, pady=40)
    
    left_col = ctk.CTkFrame(main_frame, fg_color="transparent")
    left_col.pack(side="left", fill="both", expand=True, padx=(0, 20))
    
    right_col = ctk.CTkFrame(main_frame, fg_color=CARD_BG, corner_radius=16, width=380)
    right_col.pack(side="right", fill="y")
    right_col.pack_propagate(False)
    
    # Left Column: Header & Search
    title_frame = ctk.CTkFrame(left_col, fg_color="transparent")
    title_frame.pack(fill="x", pady=(0, 15))
    ctk.CTkLabel(title_frame, text="Explore the Library", font=(FONT_FAMILY, 32, "bold"), text_color=TEXT_MAIN).pack(side="left")
    
    search_frame = ctk.CTkFrame(left_col, fg_color="#F1F5F9", corner_radius=20, height=50, border_width=1, border_color="#E5E7EB")
    search_frame.pack(fill="x", pady=(0, 20))
    search_frame.pack_propagate(False)
    
    search_icon = ctk.CTkLabel(search_frame, text="🔍", font=(FONT_FAMILY, 16), text_color=TEXT_SUB)
    search_icon.pack(side="left", padx=(20, 5))
    
    search_entry = ctk.CTkEntry(search_frame, font=(FONT_FAMILY, 14), placeholder_text="Search by title, author, or category...", border_width=0, fg_color="transparent", text_color=TEXT_MAIN)
    search_entry.pack(side="left", fill="both", expand=True)
    
    # Table Frame
    table_container = ctk.CTkFrame(left_col, fg_color=CARD_BG, corner_radius=16)
    table_container.pack(fill="both", expand=True)
    
    columns = ("code", "author", "title", "category", "year", "copies")
    tree = ttk.Treeview(table_container, columns=columns, show="headings", selectmode="extended")
    
    def sort_column(tv, col, reverse):
        # Extract data to sort
        l = [(tv.set(k, col), k) for k in tv.get_children('')]
        # Sort numerically if possible (e.g. for Year)
        try:
            l.sort(key=lambda t: float(t[0] if '/' not in t[0] else t[0].split('/')[0].strip()), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)
            
        for index, (val, k) in enumerate(l):
            tv.move(k, '', index)
            
        # Update command to reverse sort on next click
        tv.heading(col, command=lambda c=col, r=not reverse: sort_column(tv, c, r))
    
    tree.heading("code", text="CODE ↕", command=lambda: sort_column(tree, "code", False))
    tree.heading("author", text="AUTHOR ↕", command=lambda: sort_column(tree, "author", False))
    tree.heading("title", text="TITLE ↕", command=lambda: sort_column(tree, "title", False))
    tree.heading("category", text="CATEGORY ↕", command=lambda: sort_column(tree, "category", False))
    tree.heading("year", text="YEAR ↕", command=lambda: sort_column(tree, "year", False))
    tree.heading("copies", text="COPIES ↕", command=lambda: sort_column(tree, "copies", False))
    
    tree.column("code", width=100)
    tree.column("author", width=200)
    tree.column("title", width=350)
    tree.column("category", width=150)
    tree.column("year", width=80, anchor="center")
    tree.column("copies", width=100, anchor="center")
    
    theme.setup_modern_treeview_style()
    
    # Treeview scrollbar
    scrollbar = ttk.Scrollbar(table_container, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y", pady=10, padx=(0,10))
    tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10)
    
    all_books = student_db.get_all_books()
    
    tree.tag_configure("unavailable", foreground=DANGER)
    
    app.grid_frame = ctk.CTkScrollableFrame(table_container, fg_color="transparent")
    
    # Store currently selected book tuple: (code, author, title, category, year, copies_str)
    app.selected_book_data = None
    
    app.current_view_mode = "list"
    app.current_matched = all_books.copy()
    app.grid_render_id = 0
    
    # -------------------------------------------------------------------------
    # POPULATE LIST VIEW (Plain Text Table)
    # -------------------------------------------------------------------------
    # This function clears the old table and inserts the new matching books.
    def populate_list(books_list):
        # Step 1: Clear existing data in the table
        for item in tree.get_children():
            tree.delete(item)
            
        # Step 2: Loop through the given books and add them to the table
        for row in books_list:
            code, author, title, category, year, is_borrowed, total_copies, available_copies = row
            total_copies = int(total_copies) if total_copies is not None else 1
            available_copies = int(available_copies) if available_copies is not None else 1
            copies_display = f"{available_copies} / {total_copies}"
            
            # Tag unavailable books so we can color them differently if needed
            tag = "unavailable" if available_copies <= 0 else ""
            tree.insert("", "end", values=(code, author, title, category, year, copies_display), tags=(tag,))
            
        def submit_image_tasks():
            for i, row_data in enumerate(books_list):
                if app.grid_render_id != current_render_id: break
                
                # We need to capture the exact widgets and data for this iteration
                code, author, title = row_data[0], row_data[1], row_data[2]
                
                # Find the label. Since widgets were created sequentially, we could pass the label directly,
                # but we can also just fetch it from the grid frame if we structured it right. 
                # Wait, it's better to just build a list of tasks while creating the UI widgets.
                pass
                
    def populate_grid(books_list):
        app.grid_render_id += 1
        current_render_id = app.grid_render_id
        
        for widget in app.grid_frame.winfo_children():
            widget.destroy()
            
        # Setup Thread Pool (Max 4 background workers)
        # We use a ThreadPoolExecutor so that if there are 60 books, it doesn't crash 
        # the computer by opening 60 network connections at the exact same time.
        if not hasattr(app, 'image_pool'):
            import concurrent.futures
            app.image_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)
            
        cols = 3
        # Limit max items to prevent UI lockup (rendering more than 60 widgets is slow)
        display_list = books_list[:60]
        
        def process_image(code_str, title_str, author_str, lbl, rid):
            # Abort if the user started a new search before this image finished!
            if app.grid_render_id != rid: return
            try:
                # 1. Fetch image from Google Books API
                img = bookimageapi.fetch_book_image(title_str, author_str, code_str)
                if app.grid_render_id != rid: return
                if img:
                    # 2. Resize and apply rounded corners
                    img = img.convert("RGBA")
                    img.thumbnail((80, 120), Image.Resampling.LANCZOS)
                    mask = Image.new("L", img.size, 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=8, fill=255)
                    img.putalpha(mask)
                    photo = ImageTk.PhotoImage(img)
                    
                    # 3. Schedule the image update on the main UI thread safely
                    if app.grid_render_id == rid:
                        app.after(0, lambda: _set_image(lbl, photo))
                else:
                    # Fallback if no image is found on Google Books
                    photo = create_fallback_image(title_str)
                    img_resized = ImageTk.getimage(photo).resize((80, 120), Image.Resampling.LANCZOS)
                    photo_resized = ImageTk.PhotoImage(img_resized)
                    if app.grid_render_id == rid:
                        app.after(0, lambda: _set_image(lbl, photo_resized))
            except Exception:
                pass

        image_tasks = []
        
        # Build the UI cards instantly
        for i, row_data in enumerate(display_list):
            code, author, title, category, year, is_borrowed, total_copies, available_copies = row_data
            total_copies = int(total_copies) if total_copies is not None else 1
            available_copies = int(available_copies) if available_copies is not None else 1
            copies_display = f"{available_copies} / {total_copies}"
            
            r, c = i // cols, i % cols
            card = ctk.CTkFrame(app.grid_frame, fg_color=CARD_BG, corner_radius=12, border_width=1, border_color="#E2E8F0")
            card.grid(row=r, column=c, padx=10, pady=10, sticky="nsew")
            
            img_lbl = ctk.CTkLabel(card, text="Image Loading...", text_color=TEXT_SUB, font=(FONT_FAMILY, 10))
            img_lbl.pack(pady=(10, 5))
            
            title_lbl = ctk.CTkLabel(card, text=title if len(title) <= 25 else title[:22]+"...", font=(FONT_FAMILY, 12, "bold"), text_color=TEXT_MAIN)
            title_lbl.pack(padx=5)
            
            author_lbl = ctk.CTkLabel(card, text=author, font=(FONT_FAMILY, 10), text_color=TEXT_SUB)
            author_lbl.pack(padx=5)
            
            avail_color = AVAILABLE_COLOR if available_copies > 0 else DANGER
            avail_lbl = ctk.CTkLabel(card, text=f"Copies: {copies_display}", font=(FONT_FAMILY, 10, "bold"), text_color=avail_color)
            avail_lbl.pack(pady=(5, 10))
            
            def make_selector(cd, au, ti, ca, ye, cop):
                return lambda event: select_book(cd, au, ti, ca, ye, cop)
            
            bind_func = make_selector(code, author, title, category, year, copies_display)
            card.bind("<Button-1>", bind_func)
            for child in card.winfo_children():
                child.bind("<Button-1>", bind_func)
                
            image_tasks.append((code, title, author, img_lbl))
            
        # Submit tasks to the pool immediately
        for task_data in image_tasks:
            app.image_pool.submit(process_image, task_data[0], task_data[1], task_data[2], task_data[3], current_render_id)

    # Helper function to place the final processed image into the label
    def _set_image(lbl, photo):
        if lbl.winfo_exists():
            lbl.configure(image=photo, text="")
            lbl.image = photo

    # -------------------------------------------------------------------------
    # VIEW TOGGLING AND SEARCH LOGIC
    # -------------------------------------------------------------------------
    # Checks which view mode is active ("list" or "grid") and only draws that specific one
    def render_active_view():
        if app.current_view_mode == "list":
            populate_list(app.current_matched)
        else:
            populate_grid(app.current_matched)

    # Switches between the plain table and the modern grid
    def toggle_view():
        if app.current_view_mode == "list":
            app.current_view_mode = "grid"
            tree.pack_forget() # Hide List
            scrollbar.pack_forget()
            app.grid_frame.pack(fill="both", expand=True, padx=10, pady=10) # Show Grid
            btn_toggle.configure(text="List View")
        else:
            app.current_view_mode = "list"
            app.grid_frame.pack_forget() # Hide Grid
            scrollbar.pack(side="right", fill="y", pady=10, padx=(0,10))
            tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=10) # Show List
            btn_toggle.configure(text="Grid View")
        render_active_view() # Call the renderer to physically draw the newly active view

    render_active_view()
    
    # --- DEBOUNCED SEARCH IMPLEMENTATION ---
    # When a user types fast, we DO NOT want to search on every single keystroke.
    # We wait 300 milliseconds after they stop typing before we actually filter the list.
    app.search_after_id = None
    def execute_filter():
        query = search_entry.get().lower()
        # Find books where the search query matches any column (title, author, code, etc.)
        app.current_matched = [row for row in all_books if any(query in str(field).lower() for field in row[:5])]
        render_active_view()

    def filter_tree(*args):
        # Cancel the pending search if the user hits another key before 300ms is up!
        if app.search_after_id:
            app.after_cancel(app.search_after_id)
        # Schedule the execute_filter function to run in 300ms
        app.search_after_id = app.after(300, execute_filter)
        
    search_entry.bind("<KeyRelease>", filter_tree)
    
    btn_toggle = ctk.CTkButton(search_frame, text="Grid View", font=(FONT_FAMILY, 12, "bold"), width=90, fg_color=BRAND, hover_color=BRAND_HOVER, command=toggle_view)
    btn_toggle.pack(side="right", padx=(5, 20))
    
    # Right Column: Borrowing Cart
    ctk.CTkLabel(right_col, text="Selected Book", font=(FONT_FAMILY, 20, "bold"), text_color=TEXT_MAIN).pack(pady=(30, 10))
    
    # Image Container
    img_canvas = tk.Canvas(right_col, width=200, height=300, bg=CARD_BG, highlightthickness=0)
    img_canvas.pack(pady=10)
    
    # Initial Placeholder
    app.current_img = create_fallback_image("B")
    img_canvas.create_image(100, 150, image=app.current_img)
    
    selected_lbl = ctk.CTkLabel(right_col, text="No book selected", font=(FONT_FAMILY, 14, "bold"), text_color=BRAND, wraplength=320, justify="center")
    selected_lbl.pack(pady=(10, 5))
    
    author_lbl = ctk.CTkLabel(right_col, text="Select a book from the list to view details.", font=(FONT_FAMILY, 12), text_color=TEXT_SUB, wraplength=320, justify="center")
    author_lbl.pack(pady=(0, 20))
    
    cart_frame = ctk.CTkFrame(right_col, fg_color="#F8FAFC", corner_radius=12)
    cart_frame.pack(fill="x", padx=20, pady=10, ipady=10)
    
    ctk.CTkLabel(cart_frame, text="Borrow Date", font=(FONT_FAMILY, 12, "bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=20, pady=(10, 2))
    borrow_date = tkcalendar.DateEntry(cart_frame, width=32, background=BRAND, foreground='white', borderwidth=0, font=(FONT_FAMILY, 11), mindate=datetime.date.today(), maxdate=datetime.date.today())
    borrow_date.pack(fill="x", padx=20, pady=(0, 15))
    
    ctk.CTkLabel(cart_frame, text="Return Date", font=(FONT_FAMILY, 12, "bold"), text_color=TEXT_MAIN).pack(anchor="w", padx=20, pady=(0, 2))
    return_date = tkcalendar.DateEntry(cart_frame, width=32, background=BRAND, foreground='white', borderwidth=0, font=(FONT_FAMILY, 11))
    return_date.pack(fill="x", padx=20, pady=(0, 10))
    
    def update_return_date(*args):
        try:
            b_date = borrow_date.get_date()
            # Set return date strictly to 30 days after borrow date
            r_date = b_date + datetime.timedelta(days=30)
            return_date.configure(state='normal')
            return_date.set_date(r_date)
            return_date.configure(state='disabled')
        except Exception:
            pass
            
    borrow_date.bind("<<DateEntrySelected>>", update_return_date)
    update_return_date() # Initialize it once
    
    def select_book(code, author, title, category, year, copies_str):
        app.selected_book_data = (code, author, title, category, year, copies_str)
        selected_lbl.configure(text=title)
        author_lbl.configure(text=f"By {author}")
        
        # Show loading text
        img_canvas.delete("all")
        img_canvas.create_text(100, 150, text="Loading image...", fill=TEXT_SUB, font=(FONT_FAMILY, 10))
        
        app.current_fetch_id = getattr(app, "current_fetch_id", 0) + 1
        my_fetch_id = app.current_fetch_id
        
        # Fetch Image
        def fetch():
            if my_fetch_id != app.current_fetch_id: return
            try:
                img = bookimageapi.fetch_book_image(title, author, code)
                if my_fetch_id != app.current_fetch_id: return
                
                if img:
                    img = img.convert("RGBA")
                    img.thumbnail((200, 300), Image.Resampling.LANCZOS)
                    mask = Image.new("L", img.size, 0)
                    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.size[0], img.size[1]), radius=8, fill=255)
                    img.putalpha(mask)
                    photo = ImageTk.PhotoImage(img)
                    def update_success():
                        if not img_canvas.winfo_exists(): return
                        if my_fetch_id != app.current_fetch_id: return
                        app.current_img = photo
                        img_canvas.delete("all")
                        img_canvas.create_image(100, 150, image=photo)
                    app.after(0, update_success)
                else:
                    def update_fail():
                        if not img_canvas.winfo_exists(): return
                        if my_fetch_id != app.current_fetch_id: return
                        app.current_img = create_fallback_image(title)
                        img_canvas.delete("all")
                        img_canvas.create_image(100, 150, image=app.current_img)
                    app.after(0, update_fail)
            except Exception:
                def update_err():
                    if not img_canvas.winfo_exists(): return
                    if my_fetch_id != app.current_fetch_id: return
                    app.current_img = create_fallback_image(title)
                    img_canvas.delete("all")
                    img_canvas.create_image(100, 150, image=app.current_img)
                app.after(0, update_err)
        
        import threading
        threading.Thread(target=fetch, daemon=True).start()

    def on_select(event):
        selected = tree.selection()
        if selected:
            item = tree.item(selected[-1])
            code, author, title, category, year, copies_str = item["values"]
            select_book(code, author, title, category, year, copies_str)
            
    tree.bind("<<TreeviewSelect>>", on_select)
    
    def add_to_cart():
        if not app.selected_book_data:
            messagebox.showwarning("Select Book", "Please select a book from the catalog first.")
            return
            
        if len(app.borrow_cart) >= 5:
            messagebox.showwarning("Cart Full", "You can only borrow a maximum of 5 books at a time.")
            return
            
        code, author, title, category, year, copies_str = app.selected_book_data
        
        try:
            available, total = map(int, copies_str.split('/'))
        except:
            available = 0
            
        if available <= 0:
            messagebox.showinfo("Not Available", f"No copies of '{title}' are available.")
            return
            
        if any(b['code'] == code for b in app.borrow_cart):
            messagebox.showwarning("Already in Cart", f"'{title}' is already in your cart.")
            return
            
        app.borrow_cart.append({"code": code, "title": title})
        messagebox.showinfo("Added", f"'{title}' added to cart.")
        cart_btn.configure(text=f"View Cart ({len(app.borrow_cart)}/5)")

    def open_cart_modal():
        if not app.borrow_cart:
            messagebox.showinfo("Empty Cart", "Your borrow cart is empty.")
            return
            
        b_date = borrow_date.get_date()
        r_date = return_date.get_date()
        
        today = datetime.date.today()
        if b_date < today:
            messagebox.showwarning("Invalid Borrow Date", "You cannot select a borrow date in the past.")
            return
            
        if r_date < b_date:
            messagebox.showwarning("Invalid Dates", "Return Date cannot be earlier than Borrow Date.")
            return
        if r_date > b_date + datetime.timedelta(days=30):
            messagebox.showwarning("Invalid Return Date", "The return date must be within 30 days of the borrow date.")
            return

        confirm_win = ctk.CTkToplevel(app)
        confirm_win.title("Cart Checkout")
        confirm_win.attributes("-topmost", True)
        cw = 500
        ch = 380 + (len(app.borrow_cart) * 35)
        cx = (app.winfo_screenwidth() // 2) - (cw // 2)
        cy = (app.winfo_screenheight() // 2) - (ch // 2)
        confirm_win.geometry(f"{cw}x{ch}+{cx}+{cy}")
        confirm_win.grab_set()

        ctk.CTkLabel(confirm_win, text="Confirm Bulk Borrow Request", font=(FONT_FAMILY, 22, "bold"), text_color=BRAND).pack(pady=(20, 10))
        
        details_frame = ctk.CTkFrame(confirm_win, fg_color="#F8FAFC", corner_radius=10)
        details_frame.pack(fill="both", expand=False, padx=30, pady=10)
        
        ctk.CTkLabel(details_frame, text="Books to Borrow:", font=(FONT_FAMILY, 12, "bold"), text_color="#111827").pack(anchor="w", padx=20, pady=(10, 0))
        for b in app.borrow_cart:
            ctk.CTkLabel(details_frame, text=f"• {b['title']}", font=(FONT_FAMILY, 14), text_color=BRAND, wraplength=400).pack(anchor="w", padx=30)
            
        ctk.CTkLabel(details_frame, text="Dates:", font=(FONT_FAMILY, 12, "bold"), text_color="#111827").pack(anchor="w", padx=20, pady=(15, 0))
        ctk.CTkLabel(details_frame, text=f"{b_date.strftime('%b %d, %Y')} to {r_date.strftime('%b %d, %Y')}", font=(FONT_FAMILY, 14), text_color="#E74C3C").pack(anchor="w", padx=30)

        def execute_bulk_borrow():
            confirm_win.destroy()
            try:
                user_info = student_db.get_current_user_info(logged_in_email)
                joined_codes = ",".join([str(b['code']) for b in app.borrow_cart])
                joined_titles = ",".join([b['title'] for b in app.borrow_cart])
                
                transaction_id, payload = qr_borrow.create_pending_transaction(
                    user_id=user_info.get("student_id", "N/A"),
                    user_name=user_info.get("name", ""),
                    user_email=logged_in_email,
                    book_id=joined_codes,
                    book_title=joined_titles,
                    borrow_date=b_date.strftime("%Y-%m-%d"),
                    due_date=r_date.strftime("%Y-%m-%d"),
                )
                qr_borrow.mark_pending_admin_claim(transaction_id)
                
                app.borrow_cart.clear()
                cart_btn.configure(text="View Cart (0/5)")
                
                ticket_win = ctk.CTkToplevel(app)
                ticket_win.title("Borrow Ticket")
                tw, th = 600, 420
                tx = (app.winfo_screenwidth() // 2) - (tw // 2)
                ty = (app.winfo_screenheight() // 2) - (th // 2)
                ticket_win.geometry(f"{tw}x{th}+{tx}+{ty}")
                ticket_win.attributes("-topmost", True)
                ticket_win.grab_set()
                
                ctk.CTkLabel(ticket_win, text="Borrow Request Successful!", font=(FONT_FAMILY, 20, "bold"), text_color=AVAILABLE_COLOR).pack(pady=(30,10))
                ctk.CTkLabel(ticket_win, text="Please present this order number to the librarian:", font=(FONT_FAMILY, 14), text_color=TEXT_SUB).pack()
                
                ticket_frame = ctk.CTkFrame(ticket_win, fg_color="#F1F5F9", corner_radius=10)
                ticket_frame.pack(pady=15, padx=20, fill="x")
                ctk.CTkLabel(ticket_frame, text=transaction_id, font=("Consolas", 36, "bold"), text_color=BRAND).pack(pady=15)
                
                def print_ticket():
                    txn_dict = {
                        "transaction_id": transaction_id,
                        "user_id": user_info.get("student_id", "N/A"),
                        "user_name": user_info.get("name", "N/A"),
                        "book_title": joined_titles,
                        "borrow_date": b_date.strftime("%Y-%m-%d"),
                        "due_date": r_date.strftime("%Y-%m-%d"),
                    }
                    qr_borrow.print_receipt(txn_dict, parent=ticket_win)
                    
                btn_frame = ctk.CTkFrame(ticket_win, fg_color="transparent")
                btn_frame.pack(fill="x", pady=10, padx=20)
                ctk.CTkButton(btn_frame, text="Print Ticket", command=print_ticket, font=(FONT_FAMILY, 14, "bold"), fg_color=BRAND, hover_color=BRAND_HOVER, height=40).pack(side="left", expand=True, padx=5)
                ctk.CTkButton(btn_frame, text="Close", command=ticket_win.destroy, font=(FONT_FAMILY, 14, "bold"), fg_color="transparent", text_color=TEXT_SUB, hover_color="#E2E8F0", border_width=1, border_color="#D1D5DB", height=40).pack(side="left", expand=True, padx=5)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to process bulk borrow: {e}")

        btn_frame = ctk.CTkFrame(confirm_win, fg_color="transparent")
        btn_frame.pack(fill="x", pady=20, padx=30)
        ctk.CTkButton(btn_frame, text="Checkout", font=(FONT_FAMILY, 14, "bold"), fg_color=BRAND, text_color="white", height=45, command=execute_bulk_borrow).pack(side="left", expand=True, padx=10)
        ctk.CTkButton(btn_frame, text="Cancel", font=(FONT_FAMILY, 14, "bold"), fg_color="#9CA3AF", text_color="white", height=45, command=confirm_win.destroy).pack(side="right", expand=True, padx=10)

    cart_row = ctk.CTkFrame(right_col, fg_color="transparent")
    cart_row.pack(side="bottom", fill="x", padx=20, pady=20)
    
    ctk.CTkButton(cart_row, text="Add to Cart", command=add_to_cart, font=(FONT_FAMILY, 14, "bold"), fg_color=AVAILABLE_COLOR, hover_color="#059669", height=45, corner_radius=12).pack(side="left", expand=True, fill="x", padx=(0, 5))
    cart_btn = ctk.CTkButton(cart_row, text="View Cart (0/5)", command=open_cart_modal, font=(FONT_FAMILY, 14, "bold"), fg_color=BRAND, hover_color=BRAND_HOVER, height=45, corner_radius=12)
    cart_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))
    
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

