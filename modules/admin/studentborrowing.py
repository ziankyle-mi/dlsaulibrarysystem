# ===================== IMPORTS =====================
import os
import sys
import sqlite3
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox
from utils import sweetalert
messagebox = sweetalert  # SweetAlert2-styled popups (see sweetalert.py)

try:
    from utils import theme
    from utils import qr_borrow
    from utils import ui_helpers
except ImportError as e:
    root = Tk()
    root.withdraw()
    messagebox.showerror("Import Error", f"Could not find 'theme.py' in this folder!\nDetails: {e}")
    sys.exit()


PRIMARY_HOVER = "#1B5349"
DANGER_COLOR = "#D64545"
DANGER_HOVER = "#B03A2E"
SUCCESS_COLOR = "#2A9D8F"


# ===================== DATABASE CONFIGURATION =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FOLDER = os.path.join(BASE_DIR, "database")


BOOKS_DB = os.path.join(DB_FOLDER, "books_system.db")             # books + borrow_records
STUDENTS_DB = os.path.join(DB_FOLDER, "regularlogindatabase.db")  # students




from utils.db_manager import (
    ensure_borrow_records_schema,
    fetch_student_lookup,
    fetch_pending_transactions_db,
    fetch_borrow_records_raw,
    delete_borrow_record,
    delete_pending_transaction,
    mark_as_returned,
    apply_fine_and_suspend as apply_fine_and_suspend_db
)




def format_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return value or "N/A"




def fetch_pending_transactions():
    """Pull QR-borrow transactions still awaiting the librarian's scan/verify
    step (qr_borrow.py's borrow_transactions table) — a student who has
    started a borrow doesn't get a borrow_records row until the admin
    verifies the QR, so without this they'd be invisible on this screen
    even though they're actively waiting on the counter."""
    return fetch_pending_transactions_db()




def fetch_borrow_records(search_query="", status_filter="All"):
    """Reads borrow_records (books_system.db) and enriches each row with the student's program/name.
    Also merges in-flight QR transactions that haven't been verified yet, shown with a Pending status."""
    ensure_borrow_records_schema()
    student_lookup = fetch_student_lookup()


    rows = fetch_borrow_records_raw()


    today = datetime.now().date()
    results = []
    for record_id, student_id, student_name, book_title, borrow_date, return_date, status in rows:
        info = student_lookup.get(student_id, {})
        display_name = info.get("name") or student_name or "N/A"
        program = info.get("program") or "N/A"


        live_status = (status or "borrowed").strip().lower()
        if live_status == "borrowed":
            try:
                due = datetime.strptime(return_date, "%Y-%m-%d").date()
                if due < today:
                    live_status = "overdue"
            except (ValueError, TypeError):
                pass

        nice_status = "Return Requested" if live_status == "return_requested" else live_status.capitalize()
        row = (
            record_id,  # Keep record_id as first column for deletion
            student_id or "N/A",
            display_name,
            program,
            book_title,
            format_date(borrow_date),
            format_date(return_date),
            nice_status
        )


        normalized_filter = status_filter.strip().lower().replace(" ", "_")
        if status_filter != "All" and normalized_filter != live_status:
            continue


        if search_query:
            haystack = " ".join(str(v) for v in row).lower()
            if search_query.lower() not in haystack:
                continue


        results.append(row)


    # Pending QR transactions — no borrow_records row exists yet, so these
    # only ever come from borrow_transactions, not the query above.
    for transaction_id, user_id, user_name, book_title, borrow_date, due_date, txn_status in fetch_pending_transactions():
        normalized_filter = status_filter.strip().lower().replace(" ", "_")
        status_value = "pending_claim" if txn_status == qr_borrow.STATUS_PENDING_ADMIN_CLAIM else "pending"
        if status_filter != "All" and normalized_filter != status_value:
            continue


        info = student_lookup.get(user_id, {})
        display_name = info.get("name") or user_name or "N/A"
        program = info.get("program") or "N/A"
        display_status = (
            "Pending Claim" if txn_status == qr_borrow.STATUS_PENDING_ADMIN_CLAIM else "Pending"
        )


        row = (
            f"PENDING:{transaction_id}",  # No borrow_records row, but keep the transaction_id so it can still be removed
            user_id or "N/A",
            display_name,
            program,
            book_title,
            format_date(borrow_date),
            format_date(due_date),
            display_status
        )


        if search_query:
            haystack = " ".join(str(v) for v in row).lower()
            if search_query.lower() not in haystack:
                continue


        results.append(row)


    return results


# delete_borrow_record, delete_pending_transaction, and mark_as_returned are imported from db_manager.


def on_remove_student():
    """Handle remove button click - shows options to delete or mark as returned"""
    selected_item = tree.selection()
    if not selected_item:
        messagebox.showwarning("No Selection", "Please select a student record to remove.")
        return
    
    # Get the selected row
    values = tree.item(selected_item[0], 'values')
    record_id = values[0]
    student_name = values[2]
    book_title = values[4]
    
    print(f"DEBUG: record_id = {record_id}, type = {type(record_id)}")  # Debug line
    
    if not record_id or record_id == "":
        messagebox.showwarning("Cannot Remove", "This is a pending transaction. Please verify or delete it from the QR verification window.")
        return

    # Pending / unclaimed QR transactions don't have a borrow_records row yet
    # (no borrow to mark as returned), so they get their own simple
    # confirm-and-delete flow instead of the return/delete dialog below.
    if isinstance(record_id, str) and record_id.startswith("PENDING:"):
        transaction_id = record_id.split("PENDING:", 1)[1]

        confirm = messagebox.showwarning(
            "Confirm Removal",
            f"This transaction was never claimed at the counter.\n\n"
            f"Student: {student_name}\n"
            f"Book: {book_title}\n\n"
            f"Remove it from the pending list? This action CANNOT be undone.",
            icon='warning'
        )

        if confirm is True or str(confirm).lower() in ['yes', 'ok', 'true', '1']:
            if delete_pending_transaction(transaction_id):
                messagebox.showinfo("Success", "Pending transaction removed successfully.")
                refresh_table()
            else:
                messagebox.showerror("Failed", "Could not remove pending transaction. Check console for details.")
        else:
            messagebox.showinfo("Cancelled", "Removal cancelled.")
        return

    # Convert to int if needed
    try:
        record_id = int(record_id)
    except ValueError:
        messagebox.showerror("Invalid Record", "Cannot delete this record - invalid ID format.")
        return
    
    # Show menu-style dialog with fade-in
    dialog = ui_helpers.create_modal_window(new_window, "Remove Record", 460, 400, "#0c1c18")
    theme.animate_modal_open(dialog)

    # ---- Styled header bar ----
    header = ctk.CTkFrame(dialog, fg_color=theme.PRIMARY, height=50, corner_radius=0)
    header.pack(fill="x")
    header.pack_propagate(False)
    ctk.CTkLabel(header, text="  Manage Borrowing Record", font=("Segoe UI", 12, "bold"),
          text_color="white", fg_color=theme.PRIMARY).pack(fill="x", padx=12, pady=12, anchor="w")

    # ---- Body ----
    body = ctk.CTkFrame(dialog, fg_color="#0c1c18", corner_radius=0)
    body.pack(fill="both", expand=True, padx=24, pady=16)

    # Info row
    info_bg = ctk.CTkFrame(body, fg_color="#173832", corner_radius=0)
    info_bg.pack(fill="x", pady=(0, 14), ipadx=12, ipady=10)
    ctk.CTkLabel(info_bg, text=f"Student:  {student_name}", font=("Segoe UI", 10),
          text_color="#9fb8ae", fg_color="#173832").pack(fill="x", anchor="w", padx=12)
    ctk.CTkLabel(info_bg, text=f"Book:       {book_title}", font=("Segoe UI", 10),
          text_color="#d0e8e0", fg_color="#173832").pack(fill="x", anchor="w", padx=12)

    ctk.CTkLabel(body, text="What would you like to do?", font=("Segoe UI", 10, "bold"),
          text_color="#FFFFFF", fg_color="#0c1c18").pack(anchor="w", pady=(0, 10))

    selected_action = StringVar(value="return")

    RADIO_BG = "#0c1c18"
    options = [
        ("return",  "✓  Mark as Returned  (keep record for history)",  "#8fbf9f"),
        ("damaged", "⚠  Report as Damaged  (Add fine)",     "#F4A261"),
        ("lost",    "✕  Report as Lost  (Add fine)",          "#e07a5f"),
        ("delete",  "🗑  Delete Record  (remove completely)",              "#e07a5f"),
    ]
    for val, txt, col in options:
        ctk.CTkRadioButton(body, text=txt, variable=selected_action, value=val,
                    font=("Segoe UI", 12), fg_color=col, hover_color=col, border_color=col, text_color=col,
                    bg_color=RADIO_BG).pack(anchor="w", pady=6)

    # ---- Buttons ----
    btn_frame = ctk.CTkFrame(body, fg_color="#0c1c18", corner_radius=0)
    btn_frame.pack(fill="x", pady=(18, 0))

    def _close_dialog():
        """Animate dialog closed."""
        theme.animate_modal_close(dialog)

    def apply_fine_and_suspend(record_id, status_str):
        """Open a styled fine-amount dialog and then write the fine + suspend
        the borrowing student. Returns True on success, False on cancel."""

        # ---- Styled fine-input popup ----
        fine_dialog = ui_helpers.create_modal_window(dialog, "Set Fine Amount", 360, 280, "#0c1c18")
        theme.animate_modal_open(fine_dialog)

        # Header
        fhdr = ctk.CTkFrame(fine_dialog, fg_color="#D35400" if status_str == "lost" else "#E67E22", height=44, corner_radius=0)
        fhdr.pack(fill="x")
        fhdr.pack_propagate(False)
        icon = "✕ Lost Book" if status_str == "lost" else "⚠ Damaged Book"
        ctk.CTkLabel(fhdr, text=f"  Fine for {icon}", font=("Segoe UI", 11, "bold"),
              text_color="white", fg_color="#D35400" if status_str == "lost" else "#E67E22").pack(fill="x", padx=10, pady=10, anchor="w")

        fbody = ctk.CTkFrame(fine_dialog, fg_color="#0c1c18", corner_radius=0)
        fbody.pack(fill="both", expand=True, padx=20, pady=14)

        ctk.CTkLabel(fbody, text=f"Book:  {book_title}",
              font=("Segoe UI", 9), text_color="#9fb8ae", fg_color="#0c1c18").pack(anchor="w", pady=(0, 12))
        ctk.CTkLabel(fbody, text="Fine Amount (₱):",
              font=("Segoe UI", 10, "bold"), text_color="#FFFFFF", fg_color="#0c1c18").pack(anchor="w")

        amount_var = StringVar(value="0")
        spin_frame = ctk.CTkFrame(fbody, fg_color="#173832", border_width=1, border_color="#2c5a4e", corner_radius=0)
        spin_frame.pack(fill="x", pady=(4, 14))
        
        # CTk doesn't have Spinbox, using CTkEntry
        spinbox = ctk.CTkEntry(spin_frame, textvariable=amount_var,
                          font=("Segoe UI", 14, "bold"), fg_color="#173832", text_color="#FFFFFF",
                          border_width=0, width=120)
        spinbox.pack(padx=10, pady=6)

        fine_result = {"value": None}

        def _confirm_fine():
            try:
                v = int(amount_var.get())
                if v < 0:
                    raise ValueError
                fine_result["value"] = v
            except ValueError:
                messagebox.showerror("Invalid Amount", "Please enter a valid non-negative amount.")
                return
            theme.animate_modal_close(fine_dialog)

        def _cancel_fine():
            theme.animate_modal_close(fine_dialog)

        fb_row = ctk.CTkFrame(fbody, fg_color="#0c1c18", corner_radius=0)
        fb_row.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(fb_row, text="APPLY FINE", font=("Segoe UI", 12, "bold"),
               fg_color="#D35400" if status_str == "lost" else "#E67E22", text_color="white",
               hover_color="#B03A2E", cursor="hand2", command=_confirm_fine).pack(side="left", padx=(0, 8))
        ctk.CTkButton(fb_row, text="CANCEL", font=("Segoe UI", 12, "bold"),
               fg_color="#2c5a4e", text_color="#d0e8e0",
               hover_color="#173832", cursor="hand2", command=_cancel_fine).pack(side="left")

        # Wait for fine dialog to close
        dialog.wait_window(fine_dialog)

        if fine_result["value"] is None:
            return False  # user cancelled

        amount = fine_result["value"]
        return apply_fine_and_suspend_db(record_id, status_str, amount, suspend_account=False)

    def do_action():
        action = selected_action.get()

        if action == "return":
            if mark_as_returned(record_id):
                messagebox.showinfo("Success", "Record marked as returned.")
                theme.animate_modal_close(dialog)
                dialog.after(int(theme.MODAL_FADE_STEPS * theme.MODAL_FADE_DELAY_MS) + 50,
                             refresh_table)
            else:
                messagebox.showerror("Failed", "Could not mark as returned.")

        elif action in ("damaged", "lost"):
            label = "damaged" if action == "damaged" else "lost"
            result = apply_fine_and_suspend(record_id, action)
            if result:
                # result may just be True if we didn't pass the info back up, let's just use generic message
                messagebox.showinfo(
                    "Fine Applied",
                    f"Book marked as {label} and fine applied.\n"
                    "The fine will appear on the student's Fines tab."
                )
                theme.animate_modal_close(dialog)
                dialog.after(int(theme.MODAL_FADE_STEPS * theme.MODAL_FADE_DELAY_MS) + 50,
                             refresh_table)
            else:
                messagebox.showinfo("Cancelled", "Operation cancelled.")

        elif action == "delete":
            confirm = messagebox.showwarning(
                "Confirm Delete",
                f"Are you absolutely sure you want to DELETE this record?\n\n"
                f"Student: {student_name}\nBook: {book_title}\n\n"
                f"This action CANNOT be undone.",
                icon="warning"
            )
            if confirm is True or str(confirm).lower() in ["yes", "ok", "true", "1"]:
                if delete_borrow_record(record_id):
                    messagebox.showinfo("Success", "Record deleted successfully.")
                    theme.animate_modal_close(dialog)
                    dialog.after(int(theme.MODAL_FADE_STEPS * theme.MODAL_FADE_DELAY_MS) + 50,
                                 refresh_table)
                else:
                    messagebox.showerror("Failed", "Could not delete record. Check console for details.")
            else:
                messagebox.showinfo("Cancelled", "Delete operation cancelled.")

    ctk.CTkButton(btn_frame, text="CONFIRM", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY,
           text_color="white", hover_color=PRIMARY_HOVER,
           cursor="hand2", command=do_action).pack(side="left", padx=(0, 10))
    ctk.CTkButton(btn_frame, text="CANCEL", font=("Segoe UI", 12, "bold"), fg_color="#2c5a4e",
           text_color="#d0e8e0", hover_color="#173832",
           cursor="hand2", command=_close_dialog).pack(side="left")



def open_qr_verification_modal():
    """
    Admin / librarian interface: scan or paste a transaction QR payload / ID,
    validate the pending borrow, and finalize the checkout.
    """
    modal = ui_helpers.create_modal_window(new_window, "Verify Borrow Ticket", 480, 420, "white")
    theme.animate_modal_open(modal)


    frame = ctk.CTkFrame(modal, fg_color="white", corner_radius=0)
    frame.pack(fill="both", expand=True, padx=24, pady=20)


    ctk.CTkLabel(frame, text="Verify Borrow Ticket", font=("Segoe UI", 16, "bold"),
          text_color=theme.PRIMARY, fg_color="white").pack(anchor="w", pady=(0, 8))
    ctk.CTkLabel(
        frame,
        text="Enter the Transaction ID displayed on the student's checkout ticket.",
        font=("Segoe UI", 10), text_color="#666666", fg_color="white", wraplength=420, justify="left"
    ).pack(anchor="w", pady=(0, 10))


    input_frame = ctk.CTkFrame(frame, fg_color="white", corner_radius=0)
    input_frame.pack(fill="x", pady=(0, 10))
    qr_entry = ctk.CTkEntry(input_frame, font=("Segoe UI", 11), fg_color="#F5F5F5", border_width=1,
                     border_color="#CCCCCC", text_color="#111827")
    qr_entry.pack(fill="x", ipady=6, side="left", expand=True)
    qr_entry.focus_set()


    preview_var = StringVar(value="Scan or enter a transaction to preview details.")
    preview_label = ctk.CTkLabel(frame, textvariable=preview_var, font=("Segoe UI", 9), text_color="#555555",
                          fg_color="#F8FAFB", wraplength=420, justify="left")
    preview_label.pack(fill="x", pady=(0, 12), ipadx=10, ipady=10)


    def preview_transaction():
        raw = qr_entry.get().strip()
        if not raw:
            preview_var.set("Scan or enter a transaction to preview details.")
            return
        try:
            txn_id = qr_borrow.parse_qr_input(raw)
            txn = qr_borrow.get_transaction(txn_id)
            if not txn:
                preview_var.set(f"Transaction '{txn_id}' not found.")
                return
            
            # Format titles
            titles = txn.get('book_title', 'N/A')
            book_list = [t.strip() for t in titles.split(',')]
            books_display = ", ".join(book_list)
            
            preview_var.set(
                f"Student: {txn.get('user_name', 'N/A')} ({txn.get('user_id', 'N/A')})\n"
                f"Books: {books_display}\n"
                f"Due: {qr_borrow.format_date_display(txn.get('due_date'))}\n"
                f"Status: {txn.get('status', 'N/A')}"
            )
        except Exception as exc:
            preview_var.set(f"Invalid input: {exc}")


    qr_entry.bind("<KeyRelease>", lambda e: preview_transaction())


    def do_verify():
        raw = qr_entry.get().strip()
        if not raw:
            messagebox.showwarning("Input Required", "Please scan or enter a transaction ID / QR payload.")
            return
        try:
            txn = qr_borrow.verify_and_complete_borrow(raw)
            titles = txn.get('book_title', 'N/A')
            book_list = [t.strip() for t in titles.split(',')]
            books_display = "\n- " + "\n- ".join(book_list)
            
            should_print = messagebox.askyesno(
                "Verification Successful",
                f"Borrow confirmed!\n\n"
                f"Student: {txn.get('user_name', 'N/A')}\n"
                f"Books: {books_display}\n\n"
                f"Transaction: {txn.get('transaction_id', 'N/A')}\n\n"
                f"Would you like to print/save the receipt now?"
            )
            if should_print:
                qr_borrow.print_receipt(txn, parent=modal)
            modal.destroy()
            refresh_table()
        except ValueError as exc:
            messagebox.showerror("Verification Failed", str(exc))
        except Exception as exc:
            messagebox.showerror("Verification Error", f"Could not verify transaction: {exc}")


    btn_row = ctk.CTkFrame(frame, fg_color="white", corner_radius=0)
    btn_row.pack(fill="x", pady=(4, 0))


    ctk.CTkButton(btn_row, text="VERIFY & CHECK OUT", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY, text_color="white",
           hover_color=PRIMARY_HOVER, cursor="hand2", command=do_verify).pack(side="left", padx=(0, 8))


    ctk.CTkButton(btn_row, text="Cancel", font=("Segoe UI", 12, "bold"), fg_color="#888888", text_color="white",
           hover_color="#666666", cursor="hand2", command=modal.destroy).pack(side="left")




# ===================== WINDOW SETUP =====================
import customtkinter as ctk

PAGE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
HOVER_TINT = "#F3F7F6"
PRIMARY = getattr(theme, "PRIMARY", "#10312B")
PRIMARY_HOVER = "#1B5349"
DANGER_COLOR = "#D64545"
DANGER_HOVER = "#B03A2E"

# ===================== WINDOW SETUP =====================
def open_screen(parent):
    global SCREEN_H, SCREEN_W, auto_refresh_enabled, new_window, tree, entry_search, status_combobox, refresh_table

    new_window = ctk.CTkToplevel(parent)
    new_window.attributes("-fullscreen", True)
    new_window.title("Student Borrowing Management")
    new_window.configure(fg_color=PAGE_BG)
    new_window.bind("<Escape>", lambda event: new_window.destroy())

    new_window.update()
    SCREEN_W = new_window.winfo_screenwidth()
    SCREEN_H = new_window.winfo_screenheight()

    # ===================== STYLE SETUP =====================
    theme.setup_modern_treeview_style()

    # ===================== CANVAS SETUP =====================
    canvas = Canvas(new_window, width=SCREEN_W, height=SCREEN_H, bd=0, highlightthickness=0, bg=PAGE_BG)
    canvas.pack(fill="both", expand=True)

    theme.build_header(new_window, canvas)

    # ===================== MAIN CONTENT =====================
    header_h = getattr(theme, "HEADER_HEIGHT", 80)
    
    content_frame = ctk.CTkFrame(new_window, fg_color=PAGE_BG, corner_radius=0)
    canvas.create_window(SCREEN_W // 2, (SCREEN_H + header_h) // 2, window=content_frame, width=SCREEN_W - 80, height=SCREEN_H - header_h - 40)

    content_card = ctk.CTkFrame(content_frame, fg_color=CARD_BG, corner_radius=15, border_width=1, border_color=BORDER)
    content_card.pack(fill="both", expand=True, padx=20, pady=20)

    # ===================== TITLE =====================
    title_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    title_frame.pack(fill="x", padx=24, pady=(24, 8))

    ctk.CTkLabel(title_frame, text="Student Borrowing Records", font=("Segoe UI", 24, "bold"), text_color=PRIMARY).pack(side="left")
    ctk.CTkLabel(title_frame, text="Manage and verify active student book loans.", font=("Segoe UI", 12), text_color=TEXT_SUB).pack(side="left", padx=(12, 0), pady=(4, 0))

    # ===================== SEARCH / FILTER BAR =====================
    toolbar = ctk.CTkFrame(content_card, fg_color="transparent")
    toolbar.pack(fill="x", padx=24, pady=(10, 14))

    entry_search = ctk.CTkEntry(toolbar, font=("Segoe UI", 13), width=280, fg_color=PAGE_BG, border_color=BORDER, placeholder_text="Search borrowing records...", text_color=TEXT_MAIN)
    entry_search.pack(side="left", padx=(0, 15))

    status_combobox = ctk.CTkOptionMenu(toolbar, values=["All", "Borrowed", "Overdue", "Returned", "Pending", "Return Requested"],
                                        width=150, fg_color=PAGE_BG, text_color=TEXT_MAIN, button_color=PRIMARY, button_hover_color=PRIMARY_HOVER)
    status_combobox.set("All")
    status_combobox.pack(side="left", padx=(0, 15))

    btn_refresh = ctk.CTkButton(toolbar, text="REFRESH", font=("Segoe UI", 12, "bold"), fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=lambda: refresh_table())
    btn_refresh.pack(side="left", padx=(0, 10))

    btn_verify_qr = ctk.CTkButton(toolbar, text="VERIFY CODE", font=("Segoe UI", 12, "bold"), fg_color="#F59E0B", hover_color="#D97706", command=lambda: open_qr_verification_modal())
    btn_verify_qr.pack(side="left", padx=(0, 10))

    btn_remove = ctk.CTkButton(toolbar, text="EDIT/REMOVE", font=("Segoe UI", 12, "bold"), fg_color=DANGER_COLOR, hover_color=DANGER_HOVER, command=lambda: on_remove_student())
    btn_remove.pack(side="right")
    
    btn_approve_return = ctk.CTkButton(toolbar, text="APPROVE RETURN", font=("Segoe UI", 12, "bold"), fg_color="#10B981", hover_color="#059669", command=lambda: approve_return_request())
    btn_approve_return.pack(side="right", padx=(0, 10))

    # ===================== TABLE =====================
    table_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    table_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    columns_def = ("record_id", "student_id", "student_name", "program", "book_title", "borrow_date", "due_date", "status")
    tree = ttk.Treeview(table_frame, columns=columns_def, show="headings", selectmode="extended")

    headings = {
        "record_id": ("REC ID", 0, "center"),
        "student_id": ("STUDENT ID", 110, "center"),
        "student_name": ("STUDENT NAME", 200, "w"),
        "program": ("PROGRAM", 160, "w"),
        "book_title": ("BOOK TITLE", 260, "w"),
        "borrow_date": ("BORROWED ON", 120, "center"),
        "due_date": ("DUE DATE", 120, "center"),
        "status": ("STATUS", 110, "center"),
    }
    
    for col, (text, width, anchor) in headings.items():
        tree.heading(col, text=text)
        if width > 0:
            tree.column(col, width=width, anchor=anchor)
        else:
            tree.column(col, width=0, stretch=False)

    tree.tag_configure("overdue", foreground="#B03A2E", background="#FDEDEC")
    tree.tag_configure("returned", foreground="#1F8A73", background="#EAFBF4")
    tree.tag_configure("borrowed", foreground="#333333", background="#FFFFFF")
    tree.tag_configure("pending", foreground="#8A5300", background="#FFF3E0")
    tree.tag_configure("pending_claim", foreground="#92400E", background="#FEF3C7")
    tree.tag_configure("return_requested", foreground="#0F766E", background="#D1FAE5")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def refresh_table(*args):
        selected_values = None
        selected_item = tree.selection()
        if selected_item:
            selected_values = tree.item(selected_item[0], 'values')
    
        for row in tree.get_children():
            tree.delete(row)

        records = fetch_borrow_records(entry_search.get().strip(), status_combobox.get())
        if not records:
            tree.insert("", "end", values=("", "", "", "", "No borrowing records found.", "", "", ""))
            return

        for record in records:
            status_tag = record[-1].lower().replace(" ", "_")
            tree.insert("", "end", values=record, tags=(status_tag,))
    
        if selected_values:
            for item in tree.get_children():
                if tree.item(item, 'values') == list(selected_values):
                    tree.selection_set(item)
                    tree.see(item)
                    break

    entry_search.bind("<KeyRelease>", refresh_table)
    status_combobox.configure(command=refresh_table)

    def approve_return_request():
        selected_items = tree.selection()
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select at least one record to approve.")
            return

        valid_items = []
        for item in selected_items:
            values = tree.item(item, 'values')
            record_id = values[0]
            status_text = values[-1]
            if str(record_id).isdigit() and status_text.strip().lower() == "return requested":
                valid_items.append((item, record_id, values[4], values[2])) 

        if not valid_items:
            messagebox.showinfo("Invalid Selection", "None of the selected records are currently requesting a return.")
            return

        if len(valid_items) < len(selected_items):
            if not messagebox.askyesno("Partial Selection", f"Only {len(valid_items)} of {len(selected_items)} selected items are valid return requests.\nDo you want to proceed with approving only the valid ones?"):
                return
        
        if len(valid_items) == 1:
            msg = f"Approve return of '{valid_items[0][2]}' from {valid_items[0][3]}?"
        else:
            msg = f"Approve return of {len(valid_items)} books?"

        if not messagebox.askyesno("Approve Return", msg): 
            return

        try:
            conn = sqlite3.connect(BOOKS_DB)
            cursor = conn.cursor()
            today = datetime.now().date()
            success_count = 0
            
            for item, record_id, book_title, student_name in valid_items:
                cursor.execute("SELECT book_code FROM borrow_records WHERE record_id = ?", (int(record_id),))
                row = cursor.fetchone()
                if not row: continue

                book_code = row[0]
                cursor.execute("SELECT COALESCE(available_copies, 1), COALESCE(total_copies, 1) FROM books WHERE book_code = ?", (book_code,))
                book_row = cursor.fetchone()
                if book_row:
                    available_copies, total_copies = book_row
                    new_available = min(int(total_copies), int(available_copies) + 1)
                    cursor.execute("UPDATE books SET available_copies = ?, is_borrowed = 0 WHERE book_code = ?", (new_available, book_code))

                cursor.execute("UPDATE borrow_records SET status = 'returned', actual_return_date = ? WHERE record_id = ?", (today, int(record_id)))
                success_count += 1
                
            conn.commit()
            conn.close()

            messagebox.showinfo("Return Approved", f"Successfully approved {success_count} return request(s).")
            refresh_table()
        except Exception as exc:
            messagebox.showerror("Approval Failed", f"Could not approve returns: {exc}")

    refresh_table()

    auto_refresh_enabled = True 
    def auto_refresh():
        if auto_refresh_enabled and not tree.selection():
            refresh_table()
        new_window.after(6000, auto_refresh) 

    new_window.after(6000, auto_refresh) 

    new_window.grab_set()
    return new_window

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    open_screen(root)
    root.mainloop()
