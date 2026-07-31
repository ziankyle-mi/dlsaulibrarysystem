import os
import sqlite3
import datetime
import pandas as pd
import customtkinter as ctk
from utils import theme
# pandas and reportlab moved to lazy imports inside the two functions that
# actually use them (sync_borrow_status_to_excel, generate_fine_receipt).
# Both are heavy to import, and this whole file is re-launched as a fresh
# subprocess every time a student opens their dashboard — paying that
# import cost up front on every launch, even for the many sessions that
# never touch Excel export or PDF receipts, was a real chunk of the delay
# ("feels buggy") when switching between screens.

# ===================== TK ROOT (created early) =====================
# well before the "real" window setup section builds the actual UI. Older
# Python/Tk let that slide by silently creating a hidden default root the
# First time it was needed. Python 3.14 removed that fallback, so we create
# the real root here — immediately, before anything else touches tkinter —
# and just reuse it (and show it) down in the window-setup section below.
ctk.set_appearance_mode("Light")


# ===================== DATABASE SETUP =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_NAME = os.path.join(BASE_DIR, "database", "login_system.db")
BOOKS_DB = os.path.join(BASE_DIR, "database", "books_system.db")
PROFILE_PICS_DIR = os.path.join(BASE_DIR, "database", "profile_pictures")
RECEIPTS_DIR = os.path.join(BASE_DIR, "database", "receipts")
# login.py wipes and rebuilds login_system.db from this Excel file on
# every launch (see convert_excel_to_table in login.py), hashing whatever
# plain-text password sits in its "password" column. That makes this file
# the real source of truth for student passwords — a change written only
# to the SQLite table would be silently overwritten the next time login.py
# starts.
REGULAR_EXCEL = os.path.join(BASE_DIR, "database", "regularlogindatabase.xlsx")

PLACEHOLDER_TEXT = "Click a book below to select it"

# ===================== ULTRA-MINIMAL PROFESSIONAL PALETTE =====================
BG = theme.LIGHT_BG           # #F9F9F9
CARD_BG = theme.WHITE         # #FFFFFF
CARD_GLASS = theme.WHITE
CARD_GLASS2 = theme.WHITE
SHADOW = theme.BORDER_GRAY    # #CCCCCC
BORDER_SOFT = "#E5E7EB"       # Very subtle gray
BORDER_GLOW = theme.PRIMARY
TEXT_MAIN = "#111827"         # Near black for readability
TEXT_SUB = theme.TEXT_GRAY    # #555555
TEXT_LABEL = "#9CA3AF"        # Muted gray
BRAND = theme.PRIMARY         # #10312B
ACCENT = theme.PRIMARY        # #10312B
ACCENT_HOVER = theme.PRIMARY_HOVER
ACCENT_DIM = "#F3F4F6"        # Tailwind gray-100 for subtle highlights
DANGER = "#EF4444"            # Clean red
DANGER_DIM = "#FEE2E2"
WARNING = "#F59E0B"
SUCCESS = "#10B981"
AVAILABLE_COLOR = "#10B981"
BORROWED_COLOR = "#9CA3AF"
ROW_EVEN = theme.WHITE
ROW_ODD = "#F9FAFB"           # Barely off-white
SELECT_BG = "#F3F4F6"         # Simple gray selection
HEADER_BG = theme.WHITE       # Clean white header

FONT_FAMILY = "Segoe UI"
FINE_PER_DAY = 5

from contextlib import contextmanager

@contextmanager
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()

# ===================== DATABASE FUNCTIONS =====================
def ensure_borrow_records_schema():
    """Create borrow_records table if it doesn't exist, and migrate in the
    fine_paid flag so a fine settled on the admin side (finemanagement.py)
    is recognized here too — that's the whole sync between the two dashboards.
    """
    with get_db_connection(BOOKS_DB) as conn:
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
        if "custom_fine" not in columns:
            # custom_fine stores one-off penalties set by admin for damaged/lost books
            cursor.execute("ALTER TABLE borrow_records ADD COLUMN custom_fine INTEGER DEFAULT 0")
        conn.commit()


def get_student_current_borrowings(email):
    """Get books currently borrowed by the student"""
    ensure_borrow_records_schema()
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT record_id, book_code, book_title, borrow_date, return_date, status, COALESCE(fine_paid, 0)
            FROM borrow_records
            WHERE student_email = ? AND status IN ('borrowed', 'return_requested')
            ORDER BY return_date ASC
        """, (email,))
        rows = cursor.fetchall()
    return rows


def get_student_borrow_history(email):
    """Get complete borrow history for the student"""
    ensure_borrow_records_schema()
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT record_id, book_code, book_title, borrow_date, return_date, actual_return_date, status
            FROM borrow_records
            WHERE student_email = ? 
            ORDER BY created_at DESC
            LIMIT 20
        """, (email,))
        rows = cursor.fetchall()
    return rows


def calculate_fine(return_date_str):
    """Calculate fine for overdue book"""
    try:
        return_date = datetime.datetime.strptime(return_date_str, '%Y-%m-%d').date()
        today = datetime.date.today()
        if today > return_date:
            days_late = (today - return_date).days
            return days_late * FINE_PER_DAY
    except ValueError:
        pass
    return 0


def get_fine_payment_status(record_id):
    ensure_borrow_records_schema()
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COALESCE(payment_status, 'unrequested') FROM borrow_records WHERE record_id = ?",
            (record_id,)
        )
        row = cursor.fetchone()
    return row[0] if row else "unrequested"


def request_fine_payment(record_id):
    """Tell the admin that the fine was paid in person at the library."""
    ensure_borrow_records_schema()
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE borrow_records
               SET payment_status = 'pending', payment_requested_at = CURRENT_TIMESTAMP
               WHERE record_id = ? AND fine_paid = 0""",
            (record_id,)
        )
        changed = cursor.rowcount > 0
        conn.commit()
    return changed


def get_student_fine_records(email):
    """Return all borrow rows for the student that have fines (paid or unpaid).
    Includes overdue fines AND custom fines (damaged/lost books).
    """
    ensure_borrow_records_schema()
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT record_id, book_code, book_title, borrow_date, return_date, status,
                   COALESCE(fine_paid, 0), COALESCE(custom_fine, 0)
            FROM borrow_records
            WHERE student_email = ? 
              AND status IN ('borrowed', 'overdue', 'damaged', 'lost', 'return_requested', 'returned')
            ORDER BY return_date ASC
            """,
            (email,)
        )
        rows = cursor.fetchall()
        
    filtered_rows = []
    for row in rows:
        record_id, book_code, book_title, borrow_date, return_date, status, fine_paid, custom_fine = row
        # If it's paid, keep it
        if fine_paid:
            filtered_rows.append(row)
            continue
            
        # If it has a custom fine, keep it
        if custom_fine > 0:
            filtered_rows.append(row)
            continue
            
        # If it's not returned and has an overdue fine, keep it
        if status != 'returned':
            overdue_fine = calculate_fine(return_date)
            if overdue_fine > 0:
                filtered_rows.append(row)
                
    return filtered_rows


def get_student_total_fines(email):
    """Calculate total fines for student, including both overdue and
    custom (damaged/lost) fines, excluding anything the admin has
    already marked as paid in Fine Management."""
    borrowings = get_student_fine_records(email)
    total_fine = 0
    for record in borrowings:
        record_id, book_code, book_title, borrow_date, return_date, status, fine_paid, custom_fine = record
        if fine_paid:
            continue
        overdue_fine = calculate_fine(return_date)
        total_fine += overdue_fine + custom_fine
    return total_fine


def ensure_profile_picture_column():
    """Migrate in a profile_picture column on regulars — stores the on-disk
    path to the student's uploaded avatar image, mirroring the other
    ensure_*_schema migrations in this file."""
    with get_db_connection(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='regulars'")
        if not cursor.fetchone():
            return
        cursor.execute("PRAGMA table_info(regulars)")
        columns = {row[1] for row in cursor.fetchall()}
        if "profile_picture" not in columns:
            cursor.execute("ALTER TABLE regulars ADD COLUMN profile_picture TEXT")
        conn.commit()


def set_profile_picture_path(email, path):
    ensure_profile_picture_column()
    with get_db_connection(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE regulars SET profile_picture = ? WHERE email = ?", (path, email))
        conn.commit()


def hash_password(raw_password, salt=None):
    """Mirrors login.py's hash_password exactly (salted PBKDF2-HMAC-SHA256,
    100,000 iterations). Has to match bit-for-bit, or a password changed
    here would verify here but fail at the actual login screen."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return salt, digest


def verify_password_hash(raw_password, salt, expected_hash):
    if not salt or not expected_hash:
        return False
    _, digest = hash_password(raw_password, salt)
    return secrets.compare_digest(digest, expected_hash)


def verify_current_password(email, entered_password):
    """Checks the typed password against the salted hash stored in
    `regulars` — the SQLite table stores a PBKDF2 hash + salt, never the
    plain password, so this has to re-hash and compare rather than
    string-match like a plain-text column would."""
    with get_db_connection(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT password, salt FROM regulars WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            row = cursor.fetchone()
        except sqlite3.OperationalError:
            row = None
    if not row:
        return False
    stored_hash, salt = row
    return verify_password_hash(entered_password, salt, stored_hash)


def update_password_in_excel(email, new_password):
    """Writes the new plain-text password into regularlogindatabase.xlsx —
    the actual source of truth, since login.py rebuilds login_system.db
    from this file (hashing the password column fresh) on every launch.
    Preserves every other sheet/column untouched."""
    if not os.path.exists(REGULAR_EXCEL):
        return False
    try:
        sheets = pd.read_excel(REGULAR_EXCEL, sheet_name=None, dtype=str)
    except Exception as e:
        from utils import sweetalert
        sweetalert.showerror("Excel Error", f"Could not read Excel file: {e}")
        return False
    if not sheets:
        return False

    first_sheet_name = list(sheets.keys())[0]
    df = sheets[first_sheet_name]

    email_col = next((c for c in df.columns if str(c).strip().lower() == "email"), None)
    password_col = next((c for c in df.columns if str(c).strip().lower() == "password"), None)
    if not email_col or not password_col:
        return False

    mask = df[email_col].astype(str).str.strip().str.lower() == email.strip().lower()
    if not mask.any():
        return False

    df.loc[mask, password_col] = new_password
    sheets[first_sheet_name] = df

    try:
        with pd.ExcelWriter(REGULAR_EXCEL, engine="openpyxl") as writer:
            for name, sheet_df in sheets.items():
                sheet_df.to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        from utils import sweetalert
        sweetalert.showerror("Excel Error", f"Could not write Excel file: {e}")
        return False
    return True


def update_password(email, new_password):
    salt, digest = hash_password(new_password)
    with get_db_connection(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(regulars)")
        columns = {row[1] for row in cursor.fetchall()}
        if "salt" not in columns:
            cursor.execute("ALTER TABLE regulars ADD COLUMN salt TEXT")
        cursor.execute(
            "UPDATE regulars SET password = ?, salt = ? WHERE LOWER(email) = LOWER(?)",
            (digest, salt, email)
        )
        conn.commit()
        
    students_db = os.path.join(BASE_DIR, "database", "regularlogindatabase.db")
    if os.path.exists(students_db):
        with get_db_connection(students_db) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET password_hash = ?, password_salt = ? WHERE LOWER(email) = LOWER(?)",
                (digest, salt, email)
            )
            conn.commit()
    return True


def get_current_user_info(email):
    ensure_profile_picture_column()
    with get_db_connection(DB_NAME) as conn:
        cursor = conn.cursor()

        # Auto-detect a likely "student ID" column since the exact name isn't known.
        cursor.execute("PRAGMA table_info(regulars)")
        columns = [row[1] for row in cursor.fetchall()]
        id_candidates = [
            "student_id", "student id", "id_number", "id number",
            "studentno", "student no", "student number", "sr_code", "sr code"
        ]
        id_column = next(
            (c for c in columns if c.lower().replace("_", " ") in id_candidates),
            None
        )

        select_cols = "[first name], [last name], major, profile_picture"
        if id_column:
            select_cols += f", [{id_column}]"

        try:
            cursor.execute(f"SELECT {select_cols} FROM regulars WHERE email = ?", (email,))
            row = cursor.fetchone()
        except sqlite3.OperationalError:
            row = None
        

    if not row:
        return {'name': 'User', 'course': 'N/A', 'email': email, 'student_id': 'N/A', 'profile_picture': None}

    info = {'name': f"{row[0]} {row[1]}", 'course': row[2], 'email': email, 'profile_picture': row[3]}
    info['student_id'] = row[4] if id_column and len(row) > 4 and row[4] else 'N/A'
    return info


def ensure_books_schema():
    """Same migration as bookinventory.py: total_copies/available_copies let
    one book_code stand for several physical copies instead of just one."""
    with get_db_connection(BOOKS_DB) as conn:
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
        if "is_borrowed" not in columns:
            cursor.execute("ALTER TABLE books ADD COLUMN is_borrowed INTEGER DEFAULT 0")
        if "total_copies" not in columns:
            cursor.execute("ALTER TABLE books ADD COLUMN total_copies INTEGER DEFAULT 1")
        if "available_copies" not in columns:
            cursor.execute("ALTER TABLE books ADD COLUMN available_copies INTEGER DEFAULT 1")
        cursor.execute("UPDATE books SET total_copies = 1 WHERE total_copies IS NULL")
        cursor.execute("""
            UPDATE books
            SET available_copies = CASE WHEN is_borrowed = 1 THEN 0 ELSE 1 END
            WHERE available_copies IS NULL
        """)
        conn.commit()


def get_all_books():
    ensure_books_schema()
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT book_code, author_name, book_title, category, publication_year,
                   COALESCE(is_borrowed, 0), COALESCE(total_copies, 1), COALESCE(available_copies, 1)
            FROM books
        """)
        rows = cursor.fetchall()
    return rows


# ===================== BOOK CART =====================
# borrow_cart maps book_code -> {title, author, avail, total}
# A student can add up to 5 books; all go into one transaction (one Order Number).
MAX_CART_SIZE = 5
borrow_cart = {}  # book_code -> dict
_cart_update_callbacks = []  # functions called whenever the cart changes


def add_to_cart(code, title, author, avail, total):
    """Add a book to the borrow cart. Returns (success, message)."""
    if code in borrow_cart:
        return False, f"'{title}' is already in your cart."
    if len(borrow_cart) >= MAX_CART_SIZE:
        return False, f"Cart is full ({MAX_CART_SIZE} books max per transaction)."
    if int(avail or 0) <= 0:
        return False, f"No copies of '{title}' are currently available."
    borrow_cart[code] = {"title": title, "author": author, "avail": avail, "total": total}
    for cb in _cart_update_callbacks:
        cb()
    return True, f"'{title}' added to cart."


def remove_from_cart(code):
    """Remove a book from the cart by its code."""
    borrow_cart.pop(code, None)
    for cb in _cart_update_callbacks:
        cb()


def clear_cart():
    """Empty the cart."""
    borrow_cart.clear()
    for cb in _cart_update_callbacks:
        cb()


def sync_borrow_status_to_excel():
    import pandas as pd
    excel_path = os.path.join(BASE_DIR, "database", "booksdatabase.xlsx")
    if not os.path.exists(excel_path):
        return
    with get_db_connection(BOOKS_DB) as conn:
        df = pd.read_sql_query("SELECT * FROM books", conn)
    if "is_borrowed" not in df.columns:
        df["is_borrowed"] = 0
    df.to_excel(excel_path, index=False, sheet_name="Verified Inventory")


def open_file_externally(path):
    """Best-effort cross-platform 'open with the OS default app'."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except (OSError, subprocess.SubprocessError):
        pass


def generate_fine_receipt(logged_in_email):
    """Build a PDF fine statement for the logged-in student covering their
    currently borrowed books, and save it to database/receipts/. Amounts
    are written as 'PHP' rather than the peso sign since ReportLab's
    built-in fonts don't include the ₱ glyph."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    fine_books = get_student_fine_records(logged_in_email)
    user_info = get_current_user_info(logged_in_email)
    if not fine_books:
        messagebox.showinfo("Nothing to Export", "You have no outstanding or paid fines to include in a receipt.")
        return

    try:
        from tkinter import filedialog
        timestamp = datetime.datetime.now()
        reference_no = timestamp.strftime("%Y%m%d%H%M%S")
        safe_name = logged_in_email.replace('@', '_at_').replace('.', '_')
        default_filename = f"receipt_{safe_name}_{reference_no}.pdf"
        
        pdf_path = filedialog.asksaveasfilename(
            title="Save Fine Receipt",
            initialfile=default_filename,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if not pdf_path:
            return

        doc = SimpleDocTemplate(
            pdf_path, pagesize=letter,
            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
            leftMargin=0.6 * inch, rightMargin=0.6 * inch
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("ReceiptTitle", parent=styles["Title"], fontSize=16, spaceAfter=2)
        sub_style = ParagraphStyle("ReceiptSub", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#6B7684"))
        section_style = ParagraphStyle("ReceiptSection", parent=styles["Heading2"], fontSize=11, spaceBefore=14, spaceAfter=6)
        note_style = ParagraphStyle("ReceiptNote", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#6B7684"), spaceBefore=12)

        elements = []
        elements.append(Paragraph("De La Salle Araneta University", sub_style))
        elements.append(Paragraph("Library Fine Statement", title_style))
        elements.append(Paragraph(
            f"Reference No. {reference_no}  |  Generated {timestamp.strftime('%B %d, %Y %I:%M %p')}",
            sub_style
        ))
        elements.append(Spacer(1, 14))

        info_table = Table([
            ["Student Name:", user_info.get('name', 'N/A'), "Student ID:", user_info.get('student_id', 'N/A')],
            ["Program:", user_info.get('course', 'N/A'), "Email:", user_info.get('email', 'N/A')],
        ], colWidths=[1.1 * inch, 2.3 * inch, 1.0 * inch, 2.1 * inch])
        info_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1B2430")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(info_table)
        elements.append(Paragraph("Currently Borrowed Books", section_style))

        table_data = [["Book Title", "Borrowed", "Due", "Status", "Fine (PHP)"]]
        total_due = 0
        for record in fine_books:
            record_id, book_code, book_title, borrow_dt, return_dt, status, fine_paid, custom_fine = record
            overdue_fine = calculate_fine(return_dt)
            fine = overdue_fine + custom_fine
            
            if fine_paid:
                status_text, fine_text = "Paid at counter", "0.00"
            elif fine > 0:
                payment_status = get_fine_payment_status(record_id)
                if payment_status == "pending":
                    status_text = "Pending Approval"
                else:
                    status_text = "Unpaid"
                fine_text = f"{fine:.2f}"
                total_due += fine
            else:
                status_text, fine_text = "No fine", "0.00"
                
            if fine > 0 or status_text == "Pending Approval":
                table_data.append([book_title, borrow_dt, return_dt, status_text, fine_text])
                
        # If no actual fines (just empty), add placeholder
        if len(table_data) == 1:
            table_data.append(["No fines found", "-", "-", "-", "0.00"])

        book_table = Table(
            table_data,
            colWidths=[2.5 * inch, 1.1 * inch, 1.1 * inch, 1.1 * inch, 0.8 * inch],
            repeatRows=1
        )
        book_table.setStyle(TableStyle([
            # Modern header
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10312B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ALIGN", (4, 0), (4, -1), "RIGHT"),
            
            # Subtle row striping without grid lines
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            
            # Clean horizontal lines instead of a boxy grid
            ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor("#10312B")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
            
            # Better padding
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        elements.append(book_table)
        elements.append(Spacer(1, 15))

        total_color = colors.HexColor("#EF4444") if total_due > 0 else colors.HexColor("#10B981")
        total_style = ParagraphStyle(
            "ReceiptTotal", parent=styles["Normal"], fontSize=14, alignment=TA_RIGHT, textColor=total_color
        )
        elements.append(Paragraph(f"<b>Total Outstanding Balance: PHP {total_due:.2f}</b>", total_style))

        elements.append(Paragraph(
            "This is a system-generated statement acting as proof of your payment request. "
            "If your payment is pending, the librarian will verify it shortly.",
            note_style
        ))

        doc.build(elements)

        should_open = messagebox.askyesno(
            "Receipt Exported",
            f"Fine statement saved to:\n{pdf_path}\n\nOpen it now?"
        )
        if should_open:
            open_file_externally(pdf_path)
    except Exception as e:
        messagebox.showerror("Export Error", f"Could not generate the fine receipt: {e}")




def generate_reading_history(email):
    """Generate a PDF of all borrowed books for a student."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    except ImportError:
        messagebox.showerror("Error", "Required PDF libraries are not installed.")
        return

    user_info = get_current_user_info(email)
    if not user_info:
        messagebox.showerror("Error", "Could not load user data.")
        return

    # Fetch ALL records
    with get_db_connection(BOOKS_DB) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT book_code, book_title, borrow_date, return_date, actual_return_date, status 
            FROM borrow_records 
            WHERE student_email = ? 
            ORDER BY borrow_date DESC
        """, (email,))
        all_records = cursor.fetchall()

    if not all_records:
        messagebox.showinfo("No History", "You haven't borrowed any books yet.")
        return

    os.makedirs(RECEIPTS_DIR, exist_ok=True)
    timestamp = datetime.datetime.now()
    safe_email = email.replace("@", "_at_").replace(".", "_")
    pdf_filename = f"Reading_History_{safe_email}_{timestamp.strftime('%Y%m%d%H%M%S')}.pdf"
    pdf_path = os.path.join(RECEIPTS_DIR, pdf_filename)

    doc = SimpleDocTemplate(
        pdf_path, pagesize=letter,
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReceiptTitle", parent=styles["Heading1"], fontSize=22, spaceAfter=8, textColor=colors.HexColor("#10312B")
    )
    sub_style = ParagraphStyle(
        "ReceiptSub", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#6B7280"), spaceAfter=15
    )
    section_style = ParagraphStyle(
        "SectionHeader", parent=styles["Heading2"], fontSize=14, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor("#111827")
    )
    
    elements = []
    
    elements.append(Paragraph("Reading History Report", title_style))
    elements.append(Paragraph(f"Generated {timestamp.strftime('%B %d, %Y %I:%M %p')}", sub_style))
    elements.append(Spacer(1, 14))

    info_table = Table([
        ["Student Name:", user_info.get('name', 'N/A'), "Student ID:", user_info.get('student_id', 'N/A')],
        ["Program:", user_info.get('course', 'N/A'), "Email:", user_info.get('email', 'N/A')],
    ], colWidths=[1.1 * inch, 2.3 * inch, 1.0 * inch, 2.1 * inch])
    info_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1B2430")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(info_table)
    
    elements.append(Paragraph("Borrowing History", section_style))

    table_data = [["Book Title", "Borrowed", "Due", "Returned", "Status"]]
    for record in all_records:
        book_code, book_title, borrow_dt, return_dt, actual_return_dt, status = record
        actual_return_dt = actual_return_dt if actual_return_dt else "-"
        # Fix encoding issues in titles
        b_title_safe = book_title.encode('latin-1', 'replace').decode('latin-1')
        table_data.append([b_title_safe, borrow_dt, return_dt, actual_return_dt, status.capitalize()])
        
    book_table = Table(
        table_data,
        colWidths=[2.5 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch],
        repeatRows=1
    )
    book_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10312B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
        ("LINEBELOW", (0, 0), (-1, 0), 2, colors.HexColor("#10312B")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elements.append(book_table)
    
    try:
        doc.build(elements)
        should_open = messagebox.askyesno(
            "Export Successful",
            f"Reading history saved to:\n{pdf_path}\n\nOpen it now?"
        )
        if should_open:
            open_file_externally(pdf_path)
    except Exception as e:
        messagebox.showerror("Export Error", f"Could not generate history: {e}")
