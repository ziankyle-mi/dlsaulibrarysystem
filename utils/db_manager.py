# ===================== IMPORTS =====================

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager
from utils import sweetalert as messagebox

# ===================== DATABASE CONFIGURATION =====================

@contextmanager
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FOLDER = os.path.join(BASE_DIR, "database")

BOOKS_DB = os.path.join(DB_FOLDER, "books_system.db")
STUDENTS_DB = os.path.join(DB_FOLDER, "regularlogindatabase.db")
LOGIN_DB = os.path.join(DB_FOLDER, "login_system.db")

FINE_PER_DAY = 5

def ensure_borrow_records_schema():
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("PRAGMA table_info(borrow_records)")
    columns = {row[1] for row in cursor.fetchall()}
    if "custom_fine" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN custom_fine INTEGER DEFAULT 0")
    if "fine_paid" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN fine_paid INTEGER DEFAULT 0")
    if "payment_status" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN payment_status TEXT DEFAULT 'unrequested'")
    if "payment_requested_at" not in columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN payment_requested_at TIMESTAMP")
    conn.commit()
    conn.close()

# --- finemanagement.py functions ---

def calculate_fine(return_date_str, end_date_str=None):
    try:
        due_date = datetime.strptime(return_date_str, "%Y-%m-%d").date()
        if end_date_str:
            end_date = datetime.strptime(str(end_date_str).split()[0], "%Y-%m-%d").date()
        else:
            end_date = datetime.now().date()
            
        if end_date > due_date:
            days_late = (end_date - due_date).days
            return days_late * FINE_PER_DAY, days_late
    except (ValueError, TypeError, AttributeError):
        pass
    return 0, 0

def fetch_fines(search_term=""):
    ensure_borrow_records_schema()
    if not os.path.exists(BOOKS_DB):
        return []

    query = """
        SELECT record_id, student_id, student_name, book_title, return_date,
               borrow_date, COALESCE(fine_paid, 0), COALESCE(payment_status, 'unrequested'), COALESCE(custom_fine, 0), status, actual_return_date
        FROM borrow_records
        WHERE status IN ('borrowed', 'damaged', 'lost', 'return_requested', 'returned')
    """
    params = []
    if search_term:
        query += " AND (student_id LIKE ? OR student_name LIKE ? OR book_title LIKE ?)"
        like = f"%{search_term}%"
        params = [like, like, like]

    try:
        with get_db_connection(BOOKS_DB) as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            raw_rows = cur.fetchall()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Fine lookup failed:\n{e}")
        return []

    results = []
    for record_id, student_id, student_name, book_title, return_date, borrow_date, fine_paid, payment_status, custom_fine, status, actual_return_date in raw_rows:
        end_date = actual_return_date if status == "returned" else None
        fine_amount, days_overdue = calculate_fine(return_date, end_date)
        total_fine = fine_amount + custom_fine

        if total_fine <= 0 and not fine_paid:
            continue

        if status == "damaged":
            status_display = "⚠ Damaged"
        elif status == "lost":
            status_display = "✗ Lost"
        elif days_overdue > 0:
            status_display = "Overdue"
        elif fine_paid:
            status_display = "Paid"
        else:
            status_display = "Active"

        results.append((record_id, student_id, student_name, book_title, return_date, days_overdue, total_fine, fine_paid, payment_status, status_display))

    results.sort(key=lambda r: (r[7], -r[5]))  # unpaid first, most overdue first
    return results

def mark_fine_paid(record_id):
    try:
        from datetime import datetime
        today = datetime.now().date()
        with get_db_connection(BOOKS_DB) as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE borrow_records SET fine_paid = 1, payment_status = 'paid', status = 'returned', actual_return_date = ? WHERE record_id = ?",
                (today, record_id)
            )
            
            # Increment the available copies since the book is returned
            cur.execute("SELECT book_code FROM borrow_records WHERE record_id = ?", (record_id,))
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE books SET available_copies = MIN(total_copies, available_copies + 1), is_borrowed = CASE WHEN available_copies + 1 >= total_copies THEN 0 ELSE is_borrowed END WHERE book_code = ?",
                    (row[0],)
                )
            
            conn.commit()
            return True
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not mark fine paid:\n{e}")
        return False

# --- studentborrowing.py functions ---

def fetch_student_lookup():
    lookup = {}
    try:
        with get_db_connection(STUDENTS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT student_id, name, program FROM users")
            for student_id, name, program in cursor.fetchall():
                lookup[student_id] = {"name": name, "program": program}
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not read student roster:\n{e}")
    return lookup

def fetch_pending_transactions_db():
    from utils import qr_borrow
    qr_borrow.ensure_transactions_schema()
    try:
        with get_db_connection(BOOKS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT transaction_id, user_id, user_name, book_title, borrow_date, due_date, status
                FROM borrow_transactions
                WHERE status IN (?, ?)
                ORDER BY created_at DESC
            """, (qr_borrow.STATUS_PENDING, qr_borrow.STATUS_PENDING_ADMIN_CLAIM))
            return cursor.fetchall()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not fetch pending transactions:\n{e}")
        return []


# --- usermanagement.py functions ---

def load_user_accounts(search_text="", role_filter="All", status_filter="All"):
    try:
        with get_db_connection(STUDENTS_DB) as conn:
            cursor = conn.cursor()
            query = "SELECT id, name, username, student_id, email, program, role, status FROM users WHERE 1=1"
            params = []
            if search_text:
                query += " AND (name LIKE ? OR username LIKE ? OR student_id LIKE ? OR email LIKE ?)"
                search_pattern = f"%{search_text}%"
                params.extend([search_pattern, search_pattern, search_pattern, search_pattern])
            if role_filter != "All":
                query += " AND role = ?"
                params.append(role_filter)
            if status_filter != "All":
                query += " AND status = ?"
                params.append(status_filter)
            cursor.execute(query, params)
            return cursor.fetchall()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not load user accounts:\n{e}")
        return []

def delete_user_account(rowid):
    try:
        with get_db_connection(STUDENTS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (rowid,))
            conn.commit()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not delete user account:\n{e}")

def user_exists_by_id_or_email(student_id, email):
    try:
        with get_db_connection(STUDENTS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(student_id) = LOWER(?) OR LOWER(email) = LOWER(?)", (student_id.strip(), email.strip()))
            count = cursor.fetchone()[0]
            return count > 0
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not check if user exists:\n{e}")
        return False
    return count > 0

def insert_user_db(full_name, username, student_id, email, program, role, status, pwd_hash, salt):
    try:
        with get_db_connection(STUDENTS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (name, username, student_id, email, program, role, status, password_hash, password_salt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (full_name, username, student_id, email, program, role, status, pwd_hash, salt))
            conn.commit()
            return True, ""
    except sqlite3.IntegrityError:
        return False, "Could not save user — duplicate record detected."
    except sqlite3.Error as exc:
        return False, f"Database error: {exc}"

def hash_password_db(raw_password, salt=None):
    import secrets, hashlib
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 100_000).hex()
    return salt, digest

def update_user_db(rowid, full_name, username, student_id, email, program, role, password):
    try:
        with get_db_connection(STUDENTS_DB) as conn:
            cursor = conn.cursor()
            pwd_hash, salt = None, None
            if password:
                salt, pwd_hash = hash_password_db(password)
                cursor.execute(
                    """UPDATE users SET name=?, username=?, student_id=?, email=?, program=?, role=?,
                       password_hash=?, password_salt=? WHERE id=?""",
                    (full_name, username, student_id, email, program, role, pwd_hash, salt, rowid)
                )
            else:
                cursor.execute(
                    """UPDATE users SET name=?, username=?, student_id=?, email=?, program=?, role=?
                       WHERE id=?""",
                    (full_name, username, student_id, email, program, role, rowid)
                )
                cursor.execute("SELECT password_hash, password_salt FROM users WHERE id = ?", (rowid,))
                pwd_hash, salt = cursor.fetchone()
            conn.commit()
            return True, "", pwd_hash, salt
    except sqlite3.Error as exc:
        return False, f"Database error: {exc}", None, None

def fetch_borrow_records_raw():
    try:
        ensure_borrow_records_schema()
        with get_db_connection(BOOKS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT record_id, student_id, student_name, book_title, borrow_date, return_date, status
                FROM borrow_records
                ORDER BY borrow_date DESC
            """)
            return cursor.fetchall()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not fetch borrow records:\n{e}")
        return []

def delete_borrow_record(record_id):
    try:
        with get_db_connection(BOOKS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM borrow_records WHERE record_id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not delete record:\n{e}")
        return False

def delete_pending_transaction(transaction_id):
    try:
        with get_db_connection(BOOKS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM borrow_transactions WHERE transaction_id = ?", (transaction_id,))
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not delete pending transaction:\n{e}")
        return False

def mark_as_returned(record_id):
    if not record_id:
        return False
    try:
        today = datetime.now().date()
        with get_db_connection(BOOKS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE borrow_records SET status = 'returned', actual_return_date = ? WHERE record_id = ?",
                (today, record_id)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Could not mark returned:\n{e}")
        return False

def apply_fine_and_suspend(record_id, status_str, amount, suspend_account=True):
    try:
        with get_db_connection(BOOKS_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE borrow_records SET status = ?, custom_fine = ? WHERE record_id = ?",
                (status_str, amount, record_id)
            )
            cursor.execute(
                "SELECT book_code, student_id FROM borrow_records WHERE record_id = ?",
                (record_id,)
            )
            row = cursor.fetchone()
            if row:
                book_code, student_id = row
                cursor.execute(
                    "UPDATE books SET total_copies = MAX(0, total_copies - 1) WHERE book_code = ?",
                    (book_code,)
                )
                if student_id and suspend_account:
                    with get_db_connection(STUDENTS_DB) as u_conn:
                        u_cur = u_conn.cursor()
                        u_cur.execute(
                            "UPDATE users SET status = 'Suspended' WHERE student_id = ?",
                            (student_id,)
                        )
                        u_conn.commit()
            conn.commit()
            return True
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Error applying fine:\n{e}")
        return False

# --- login.py functions ---

def ensure_login_status_columns(connection):
    cursor = connection.cursor()
    for table_name in ("admins", "regulars"):
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = {row[1] for row in cursor.fetchall()}
            if "status" not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN status TEXT DEFAULT 'Active'")
                connection.commit()
        except sqlite3.OperationalError:
            pass

def verify_login(username):
    with get_db_connection(LOGIN_DB) as conn:
        cursor = conn.cursor()
        ensure_login_status_columns(conn)
        admin_row = None
        regular_row = None
        
        try:
            cursor.execute(
                "SELECT password, salt, status FROM admins "
                "WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
                (username, username)
            )
            admin_row = cursor.fetchone()
        except sqlite3.OperationalError:
            pass

        try:
            cursor.execute(
                "SELECT password, salt, status FROM regulars "
                "WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
                (username, username)
            )
            regular_row = cursor.fetchone()
        except sqlite3.OperationalError:
            pass

    return admin_row, regular_row

def ensure_password_reset_table(request_db):
    if not os.path.exists(os.path.dirname(request_db)):
        os.makedirs(os.path.dirname(request_db), exist_ok=True)
    with get_db_connection(request_db) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                email TEXT,
                role TEXT,
                status TEXT,
                password_hash TEXT,
                password_salt TEXT,
                password_plain TEXT,
                requested_at TEXT,
                decided_at TEXT,
                decision_by TEXT,
                decision_note TEXT
            )
        ''')
        conn.commit()

def submit_password_reset_request(identifier, new_password, db_file, request_db, hash_password_fn):
    identifier = (identifier or "").strip()
    new_password = (new_password or "").strip()

    if not identifier:
        return False, "Please enter a username or email."
    if len(new_password) < 4:
        return False, "Password must be at least 4 characters long."

    with get_db_connection(db_file) as conn:
        cursor = conn.cursor()
        ensure_login_status_columns(conn)

        matched_role = None
        matched_email = None
        matched_username = None
        for table_name in ("admins", "regulars"):
            try:
                cursor.execute(
                    f"SELECT email, username FROM {table_name} WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
                    (identifier, identifier)
                )
                row = cursor.fetchone()
            except sqlite3.OperationalError:
                row = None

            if row:
                matched_email, matched_username = row
                matched_role = "Admin" if table_name == "admins" else "Student"
                break

    if not matched_email:
        return False, "No account matched that username or email."

    ensure_password_reset_table(request_db)
    with get_db_connection(request_db) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM password_reset_requests WHERE (LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)) AND status = ?",
            (matched_email, matched_username, "Pending")
        )
        if cursor.fetchone():
            return False, "A pending password reset request already exists for this account."

        salt, pwd_hash = hash_password_fn(new_password)
        requested_at = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO password_reset_requests (username, email, role, status, password_hash, password_salt, password_plain, requested_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (matched_username, matched_email, matched_role, "Pending", pwd_hash, salt, new_password, requested_at)
        )
    return True, "Password reset request submitted. An administrator must approve it before your password changes."

def get_email_for_user(identifier, db_file):
    """
    Looks up a user by username or email in login_system.db (both admins and regulars).
    Returns (email, role) if found, else (None, None).
    """
    identifier = (identifier or "").strip()
    if not identifier:
        return None, None

    with get_db_connection(db_file) as conn:
        cursor = conn.cursor()
        ensure_login_status_columns(conn)

        for table_name in ("admins", "regulars"):
            try:
                cursor.execute(
                    f"SELECT email FROM {table_name} WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
                    (identifier, identifier)
                )
                row = cursor.fetchone()
                if row:
                    role = "Admin" if table_name == "admins" else "Student"
                    return row[0], role
            except sqlite3.OperationalError:
                pass

    return None, None

def update_password_direct(identifier, new_password, db_file, hash_password_fn):
    """
    Directly updates the password for a user in login_system.db.
    """
    identifier = (identifier or "").strip()
    new_password = (new_password or "").strip()

    if not identifier or not new_password:
        return False, "Invalid inputs."

    salt, pwd_hash = hash_password_fn(new_password)

    with get_db_connection(db_file) as conn:
        cursor = conn.cursor()
        
        # Try admins first
        cursor.execute(
            "UPDATE admins SET password = ?, salt = ? WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (pwd_hash, salt, identifier, identifier)
        )
        if cursor.rowcount > 0:
            conn.commit()
            return True, "Password successfully updated!"

        # Try regulars next
        cursor.execute(
            "UPDATE regulars SET password = ?, salt = ? WHERE LOWER(username) = LOWER(?) OR LOWER(email) = LOWER(?)",
            (pwd_hash, salt, identifier, identifier)
        )
        if cursor.rowcount > 0:
            conn.commit()
            return True, "Password successfully updated!"

    return False, "Could not find user to update."

