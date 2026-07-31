"""
qr_borrow.py — QR Code borrowing transaction workflow.

Student flow:
  1. Student clicks "Borrow Book" → create transaction (status: pending)
  2. QR modal shows JSON payload for librarian scanning
  3. Student confirms scan → status becomes PENDING_ADMIN_CLAIM
  4. Digital receipt modal displayed

Admin flow:
  1. Librarian scans/enters transaction ID
  2. Validate book availability + pending status
  3. Mark transaction BORROWED, decrement copies, create borrow_records row
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOKS_DB = os.path.join(BASE_DIR, "database", "books_system.db")

# Transaction status constants
STATUS_PENDING = "pending"
STATUS_PENDING_ADMIN_CLAIM = "PENDING_ADMIN_CLAIM"
STATUS_BORROWED = "BORROWED"
STATUS_CANCELLED = "CANCELLED"
STATUS_EXPIRED = "EXPIRED"


def ensure_transactions_schema():
    """Create borrow_transactions table if it does not exist."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS borrow_transactions (
            transaction_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            user_name TEXT,
            user_email TEXT,
            book_id TEXT NOT NULL,
            book_title TEXT NOT NULL,
            borrow_date DATE NOT NULL,
            due_date DATE NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            verified_at TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def ensure_borrow_records_schema():
    """Ensure borrow_records exists (shared with other modules)."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS borrow_records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_code TEXT NOT NULL,
            book_title TEXT NOT NULL,
            student_name TEXT,
            student_id TEXT,
            student_email TEXT,
            borrow_date DATE NOT NULL,
            return_date DATE NOT NULL,
            actual_return_date DATE,
            status TEXT DEFAULT 'borrowed',
            fine_paid INTEGER DEFAULT 0,
            payment_status TEXT DEFAULT 'unrequested',
            payment_requested_at TIMESTAMP,
            transaction_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("PRAGMA table_info(borrow_records)")
    columns = {row[1] for row in cursor.fetchall()}
    if "fine_paid" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN fine_paid INTEGER DEFAULT 0")
    if "payment_status" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN payment_status TEXT DEFAULT 'unrequested'")
    if "payment_requested_at" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN payment_requested_at TIMESTAMP")
    if "transaction_id" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN transaction_id TEXT")
    conn.commit()
    conn.close()


def ensure_books_schema():
    """Ensure books table has copy-tracking columns."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
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
    """)
    cursor.execute("PRAGMA table_info(books)")
    columns = {row[1] for row in cursor.fetchall()}
    if "total_copies" not in columns:
        cursor.execute("ALTER TABLE books ADD COLUMN total_copies INTEGER DEFAULT 1")
    if "available_copies" not in columns:
        cursor.execute("ALTER TABLE books ADD COLUMN available_copies INTEGER DEFAULT 1")
    if "is_borrowed" not in columns:
        cursor.execute("ALTER TABLE books ADD COLUMN is_borrowed INTEGER DEFAULT 0")
    conn.commit()
    conn.close()


def generate_transaction_id():
    """Return a short, typeable transaction pass (Order Number)."""
    ensure_transactions_schema()
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    try:
        while True:
            # Generate something like ORD-8A3B2
            transaction_id = f"ORD-{uuid.uuid4().hex[:5].upper()}"
            cursor.execute(
                "SELECT 1 FROM borrow_transactions WHERE transaction_id = ?",
                (transaction_id,)
            )
            if cursor.fetchone() is None:
                return transaction_id
    finally:
        conn.close()


def build_qr_payload(transaction_id, user_id, book_id, status=STATUS_PENDING):
    """Build the JSON payload encoded inside the QR code."""
    return {
        "transaction_id": transaction_id,
        "user_id": user_id,
        "book_id": book_id,
        "timestamp": datetime.now().isoformat(),
        "status": status,
    }


def create_pending_transaction(user_id, user_name, user_email, book_id, book_title,
                               borrow_date, due_date):
    """
    Create a new pending borrow transaction without decrementing book copies.
    Returns (transaction_id, payload_dict) or raises ValueError on failure.
    """
    ensure_transactions_schema()
    ensure_books_schema()

    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()

    book_ids = book_id.split(",")
    book_titles = book_title.split(",") if book_title else []
    
    for i, b_id in enumerate(book_ids):
        b_id = b_id.strip()
        cursor.execute(
            "SELECT book_title, COALESCE(available_copies, 1), COALESCE(total_copies, 1) "
            "FROM books WHERE book_code = ?",
            (b_id,)
        )
        book_row = cursor.fetchone()
        if not book_row:
            conn.close()
            raise ValueError(f"A selected book ({b_id}) could not be found.")

        db_title, available_copies, total_copies = book_row
        title = book_titles[i].strip() if i < len(book_titles) else db_title
        if int(available_copies or 0) <= 0:
            conn.close()
            raise ValueError(f'All {total_copies} copies of "{title}" are currently borrowed.')

    transaction_id = generate_transaction_id()
    cursor.execute("""
        INSERT INTO borrow_transactions
            (transaction_id, user_id, user_name, user_email, book_id, book_title,
             borrow_date, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        transaction_id, user_id, user_name, user_email, book_id, book_title,
        borrow_date, due_date, STATUS_PENDING
    ))
    conn.commit()
    conn.close()

    payload = build_qr_payload(transaction_id, user_id, book_id, STATUS_PENDING)
    return transaction_id, payload


def mark_pending_admin_claim(transaction_id):
    """Update transaction status after the student confirms the QR scan."""
    ensure_transactions_schema()
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT status FROM borrow_transactions WHERE transaction_id = ?",
        (transaction_id,)
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError("Transaction not found.")
    if row[0] not in (STATUS_PENDING, STATUS_PENDING_ADMIN_CLAIM):
        conn.close()
        raise ValueError(f"Transaction cannot be updated (current status: {row[0]}).")

    cursor.execute(
        "UPDATE borrow_transactions SET status = ? WHERE transaction_id = ?",
        (STATUS_PENDING_ADMIN_CLAIM, transaction_id)
    )
    conn.commit()
    conn.close()
    return STATUS_PENDING_ADMIN_CLAIM


def get_transaction(transaction_id):
    """Fetch a single transaction row as a dict."""
    ensure_transactions_schema()
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT transaction_id, user_id, user_name, user_email, book_id, book_title,
               borrow_date, due_date, status, created_at, verified_at
        FROM borrow_transactions WHERE transaction_id = ?
    """, (transaction_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    keys = [
        "transaction_id", "user_id", "user_name", "user_email", "book_id", "book_title",
        "borrow_date", "due_date", "status", "created_at", "verified_at"
    ]
    return dict(zip(keys, row))


def parse_qr_input(raw_text):
    """
    Parse scanned QR content — accepts plain transaction ID or JSON payload.
    Returns transaction_id string.
    """
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("No QR data provided.")

    if text.startswith("{"):
        try:
            data = json.loads(text)
            txn_id = data.get("transaction_id")
            if not txn_id:
                raise ValueError("QR JSON is missing transaction_id.")
            return txn_id
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid QR JSON: {exc}") from exc

    return text


def verify_and_complete_borrow(raw_qr_input):
    """
    Admin verification: validate pending transaction, mark BORROWED,
    decrement available copies, and insert borrow_records row.
    Returns the completed transaction dict.
    """
    ensure_transactions_schema()
    ensure_books_schema()
    ensure_borrow_records_schema()

    transaction_id = parse_qr_input(raw_qr_input)
    txn = get_transaction(transaction_id)
    if not txn:
        raise ValueError("Transaction ID not found.")

    if txn["status"] == STATUS_BORROWED:
        raise ValueError("This transaction has already been verified and completed.")
    if txn["status"] not in (STATUS_PENDING, STATUS_PENDING_ADMIN_CLAIM):
        raise ValueError(f"Transaction status '{txn['status']}' is not eligible for verification.")

    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()

    book_ids = txn["book_id"].split(",")
    book_titles = txn["book_title"].split(",")

    for i, b_id in enumerate(book_ids):
        b_id = b_id.strip()
        b_title_fallback = book_titles[i].strip() if i < len(book_titles) else b_id

        cursor.execute(
            "SELECT COALESCE(available_copies, 1), COALESCE(total_copies, 1), book_title "
            "FROM books WHERE book_code = ?",
            (b_id,)
        )
        book_row = cursor.fetchone()
        if not book_row:
            conn.close()
            raise ValueError(f"Book '{b_title_fallback}' no longer exists in inventory.")

        available_copies, total_copies, db_book_title = book_row
        if int(available_copies or 0) <= 0:
            conn.close()
            raise ValueError(
                f'No copies available for "{db_book_title}". '
                "Another student may have claimed the last copy."
            )

        new_available = int(available_copies) - 1
        cursor.execute(
            "UPDATE books SET available_copies = ?, is_borrowed = ? WHERE book_code = ?",
            (new_available, 1 if new_available <= 0 else 0, b_id)
        )

        cursor.execute("""
            INSERT INTO borrow_records
                (book_code, book_title, student_name, student_id, student_email,
                 borrow_date, return_date, status, transaction_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'borrowed', ?)
        """, (
            b_id, db_book_title, txn["user_name"], txn["user_id"],
            txn["user_email"], txn["borrow_date"], txn["due_date"], transaction_id
        ))

    verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "UPDATE borrow_transactions SET status = ?, verified_at = ? WHERE transaction_id = ?",
        (STATUS_BORROWED, verified_at, transaction_id)
    )

    conn.commit()
    conn.close()

    _sync_books_to_excel()

    txn["status"] = STATUS_BORROWED
    txn["verified_at"] = verified_at
    return txn


def _sync_books_to_excel():
    """Push updated book inventory back to booksdatabase.xlsx if present."""
    excel_path = os.path.join(BASE_DIR, "database", "booksdatabase.xlsx")
    if not os.path.exists(excel_path):
        return
    try:
        import pandas as pd
        excel_columns = ["Book Code", "Author Name", "Book Title", "Category", "Publication Year"]
        conn = sqlite3.connect(BOOKS_DB)
        df = pd.read_sql_query("SELECT * FROM books", conn)
        conn.close()
        df = df.iloc[:, : len(excel_columns)]
        df.columns = excel_columns
        with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Verified Inventory")
    except Exception as exc:
        print(f"[qr_borrow] Excel sync warning: {exc}")


def print_receipt(transaction_dict, parent=None):
    """Generate a PDF borrow receipt and open it using ReportLab."""
    was_topmost = False
    if parent is not None:
        try:
            was_topmost = bool(parent.attributes("-topmost"))
            if was_topmost:
                parent.attributes("-topmost", False)
        except Exception:
            pass

    try:
        from reportlab.lib.pagesizes import letter, inch
        from reportlab.pdfgen import canvas as pdf_canvas
        import tkinter as tk
        from tkinter import filedialog, messagebox
        import os
        import sys
        import subprocess

        txn = transaction_dict
        transaction_id = txn.get('transaction_id', 'N/A')
        
        file_kwargs = {
            "title": "Save Borrow Receipt",
            "initialfile": f"Borrow_Receipt_{transaction_id}.pdf",
            "defaultextension": ".pdf",
            "filetypes": [("PDF file", "*.pdf"), ("All files", "*.*")]
        }
        if parent:
            file_kwargs["parent"] = parent

        pdf_path = filedialog.asksaveasfilename(**file_kwargs)
        if not pdf_path:
            return

        c = pdf_canvas.Canvas(pdf_path, pagesize=letter)
        
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(letter[0] / 2.0, letter[1] - 0.8 * inch, "ALIW LIBRARY SYSTEM")
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(letter[0] / 2.0, letter[1] - 1.2 * inch, "BORROW TRANSACTION RECEIPT")
        
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(letter[0] / 2.0, letter[1] - 1.6 * inch, f"Transaction Ref: {transaction_id}")
        
        c.setLineWidth(1)
        c.line(0.8 * inch, letter[1] - 1.8 * inch, letter[0] - 0.8 * inch, letter[1] - 1.8 * inch)

        c.setFont("Helvetica", 11)
        text_obj = c.beginText(1 * inch, letter[1] - 2.2 * inch)
        text_obj.setLeading(16)
        text_obj.textLine(f"Date Issued:   {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        text_obj.textLine(f"Student Name:  {txn.get('user_name', 'N/A')}")
        text_obj.textLine(f"Student ID:    {txn.get('user_id', 'N/A')}")
        text_obj.textLine(f"Borrow Date:   {txn.get('borrow_date', 'N/A')}")
        text_obj.textLine(f"Due Date:      {txn.get('due_date', 'N/A')}")
        text_obj.textLine("")
        
        text_obj.setFont("Helvetica-Bold", 12)
        text_obj.textLine("Borrowed Book(s):")
        text_obj.setFont("Helvetica", 11)
        
        raw_titles = txn.get('book_title', 'N/A')
        for title in str(raw_titles).split(','):
            title_clean = title.strip()
            if title_clean:
                title_safe = title_clean.encode('latin-1', 'replace').decode('latin-1')
                text_obj.textLine(f"  • {title_safe}")
                
        c.drawText(text_obj)
        
        c.line(0.8 * inch, 2.5 * inch, letter[0] - 0.8 * inch, 2.5 * inch)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(letter[0] / 2.0, 2.1 * inch, "Thank you for utilizing the ALIW Library System!")
        c.drawCentredString(letter[0] / 2.0, 1.8 * inch, "Please return your borrowed items on or before the due date to avoid fines.")
        
        c.save()
        
        # Open generated PDF automatically
        try:
            if sys.platform.startswith("win"):
                os.startfile(pdf_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", pdf_path])
            else:
                subprocess.Popen(["xdg-open", pdf_path])
        except Exception:
            pass

        try:
            from utils import sweetalert
            sweetalert.showinfo("Receipt Exported", f"Borrow receipt saved successfully to:\n{pdf_path}", parent=parent)
        except Exception:
            messagebox.showinfo("Receipt Exported", f"Borrow receipt saved successfully to:\n{pdf_path}", parent=parent)

    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showerror("Print Error", f"Could not generate receipt: {e}", parent=parent)
    finally:
        if parent is not None and was_topmost:
            try:
                parent.attributes("-topmost", True)
                parent.focus_force()
            except Exception:
                pass


def format_date_display(value):
    """Format YYYY-MM-DD to MM/DD/YYYY for receipts."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%m/%d/%Y")
    except (ValueError, TypeError):
        return value or "N/A"

def print_fine_payment_receipt(transaction_dict, parent=None):
    """Generate a PDF fine payment receipt and open it using ReportLab."""
    was_topmost = False
    if parent is not None:
        try:
            was_topmost = bool(parent.attributes("-topmost"))
            if was_topmost:
                parent.attributes("-topmost", False)
        except Exception:
            pass

    try:
        from reportlab.lib.pagesizes import letter, inch
        from reportlab.pdfgen import canvas as pdf_canvas
        import tkinter as tk
        from tkinter import filedialog, messagebox
        import os
        import sys
        import subprocess

        txn = transaction_dict
        transaction_id = txn.get('transaction_id', 'N/A')
        
        file_kwargs = {
            "title": "Save Fine Payment Receipt",
            "initialfile": f"Fine_Payment_{transaction_id}.pdf",
            "defaultextension": ".pdf",
            "filetypes": [("PDF file", "*.pdf"), ("All files", "*.*")]
        }
        if parent:
            file_kwargs["parent"] = parent

        pdf_path = filedialog.asksaveasfilename(**file_kwargs)
        if not pdf_path:
            return

        c = pdf_canvas.Canvas(pdf_path, pagesize=letter)
        
        c.setFont("Helvetica-Bold", 20)
        c.drawCentredString(letter[0] / 2.0, letter[1] - 0.8 * inch, "ALIW LIBRARY SYSTEM")
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(letter[0] / 2.0, letter[1] - 1.2 * inch, "FINE PAYMENT RECEIPT")
        
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(letter[0] / 2.0, letter[1] - 1.6 * inch, f"Transaction Ref: {transaction_id}")
        
        c.setLineWidth(1)
        c.line(0.8 * inch, letter[1] - 1.8 * inch, letter[0] - 0.8 * inch, letter[1] - 1.8 * inch)

        c.setFont("Helvetica", 11)
        text_obj = c.beginText(1 * inch, letter[1] - 2.2 * inch)
        text_obj.setLeading(16)
        text_obj.textLine(f"Date Issued:   {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
        text_obj.textLine(f"Student Name:  {txn.get('user_name', 'N/A')}")
        text_obj.textLine(f"Student ID:    {txn.get('user_id', 'N/A')}")
        text_obj.textLine(f"Borrow Date:   {txn.get('borrow_date', 'N/A')}")
        text_obj.textLine(f"Due Date:      {txn.get('due_date', 'N/A')}")
        text_obj.textLine(f"Fine Amount:   PHP {txn.get('fine_amount', '0.00')}")
        text_obj.textLine("")
        
        text_obj.setFont("Helvetica-Bold", 12)
        text_obj.textLine("Book Details:")
        text_obj.setFont("Helvetica", 11)
        
        raw_titles = txn.get('book_title', 'N/A')
        for title in str(raw_titles).split(','):
            title_clean = title.strip()
            if title_clean:
                title_safe = title_clean.encode('latin-1', 'replace').decode('latin-1')
                text_obj.textLine(f"  • {title_safe}")
                
        c.drawText(text_obj)
        
        c.line(0.8 * inch, 2.5 * inch, letter[0] - 0.8 * inch, 2.5 * inch)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(letter[0] / 2.0, 2.1 * inch, "Thank you for utilizing the ALIW Library System!")
        c.drawCentredString(letter[0] / 2.0, 1.8 * inch, "Please bring this receipt to the cashier for payment, then to the librarian.")
        
        c.save()
        
        # Open generated PDF automatically
        try:
            if sys.platform.startswith("win"):
                os.startfile(pdf_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", pdf_path])
            else:
                subprocess.Popen(["xdg-open", pdf_path])
        except Exception:
            pass

        try:
            from utils import sweetalert
            sweetalert.showinfo("Receipt Exported", f"Fine Payment receipt saved successfully to:\n{pdf_path}", parent=parent)
        except Exception:
            messagebox.showinfo("Receipt Exported", f"Fine Payment receipt saved successfully to:\n{pdf_path}", parent=parent)

    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showerror("Print Error", f"Could not generate receipt: {e}", parent=parent)
    finally:
        if parent is not None and was_topmost:
            try:
                parent.attributes("-topmost", True)
                parent.focus_force()
            except Exception:
                pass
