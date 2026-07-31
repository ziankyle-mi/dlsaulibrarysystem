import customtkinter as ctk
# ===================== IMPORTS =====================
import os
import sqlite3
import hashlib
import secrets
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox
from utils import sweetalert
messagebox = sweetalert  # SweetAlert2-styled popups (see sweetalert.py)
from utils import theme  # Imports your theme.py file
from utils.db_manager import load_user_accounts, delete_user_account as delete_user_account_db, user_exists_by_id_or_email
from utils import ui_helpers

# ===================== PASSWORD HASHING =====================
# Same PBKDF2 approach as login.py so newly created accounts can sign in.

def hash_password(raw_password, salt=None):
    """Return (salt, hash) using salted PBKDF2-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return salt, digest


def split_full_name(full_name):
    """Split 'First Last' into (first, last) for login_system regulars table."""
    parts = (full_name or "").strip().split(None, 1)
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def normalize_status(status):
    """Normalize incoming status values so login checks and toggles agree."""
    if status is None:
        return "Active"
    status_text = str(status).strip().lower()
    if status_text in {"suspended", "disabled", "inactive", "deactivated", "banned", "blocked"}:
        return "Suspended"
    return "Active"

# ===================== DATABASE SETUP =====================
# Get the exact folder where usermanagement.py is located
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Lock the database folder exactly next to usermanagement.py
DB_DIR = os.path.join(BASE_DIR, "database")
DB_NAME = os.path.join(DB_DIR, "regularlogindatabase.db")
LOGIN_DB = os.path.join(DB_DIR, "login_system.db")
EXCEL_FILE = os.path.join(DB_DIR, "regularlogindatabase.xlsx")
ADMIN_EXCEL_FILE = os.path.join(DB_DIR, "adminlogindatabase.xlsx")

def setup_database():
    """Initializes the SQLite database and imports data from Excel if it's empty."""
    # Ensure the database directory exists just in case
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Create the users table to match the GUI format
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            username TEXT,
            student_id TEXT,
            email TEXT,
            program TEXT,
            role TEXT,
            status TEXT,
            password_hash TEXT,
            password_salt TEXT
        )
    ''')
    # Migrate older databases that predate the password columns
    cursor.execute("PRAGMA table_info(users)")
    user_columns = {row[1] for row in cursor.fetchall()}
    if "password_hash" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    if "password_salt" not in user_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")
    
    # Create a request queue for forgot-password approvals.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_reset_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT,
            role TEXT,
            status TEXT,
            password_hash TEXT,
            password_salt TEXT,
            requested_at TEXT,
            decided_at TEXT,
            decision_by TEXT,
            decision_note TEXT
        )
    ''')

    # Check if users table is empty.
    cursor.execute('SELECT COUNT(*) FROM users')
    if cursor.fetchone()[0] == 0:
        if os.path.exists(EXCEL_FILE):
            try:
                # Read the excel file from the database folder (only ever needed
                # on this first-run/empty-table path, so import it lazily here rather
                # than paying pandas' import cost on every ordinary launch)
                import pandas as pd
                df = pd.read_excel(EXCEL_FILE)
                
                imported_count = 0
                for index, row in df.iterrows():
                    # Safely grab column data (handles missing columns gracefully)
                    first_name = str(row.get('First Name', '')).strip()
                    last_name = str(row.get('Last Name', '')).strip()
                    name = f"{first_name} {last_name}".strip()
                    
                    # Skip empty rows
                    if name == "nan" or name == "":
                        continue
                        
                    email = str(row.get('Email', '')).strip()
                    username = email.split('@')[0] if email and '@' in email else f"user{index}"
                    student_id = str(row.get('Student ID', '')).strip()
                    program = str(row.get('Major', '')).strip()
                    role = "Student"
                    status = "Active"
                    
                    cursor.execute('''
                        INSERT INTO users (name, username, student_id, email, program, role, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (name, username, student_id, email, program, role, status))
                    
                    imported_count += 1
                    
                messagebox.showinfo("Setup Complete", f"Successfully imported {imported_count} students from Excel into the database.")
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to read the Excel file.\n\nError: {e}")
        else:
            # If the file isn't found, alert the user!
            current_dir = os.path.abspath(DB_DIR)
            messagebox.showwarning(
                "Missing File", 
                f"Could not find '{EXCEL_FILE}'.\n\nThe script is looking in:\n{current_dir}\n\nPlease make sure the Excel file is exactly in this folder."
            )
            
    conn.commit()
    conn.close()

# load_user_accounts is imported from db_manager

def delete_user_account(rowid):
    """Deletes a user from the SQLite database."""
    delete_user_account_db(rowid)

# user_exists_by_id_or_email is imported from db_manager


def user_exists_for_other_account(rowid, student_id, email):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """SELECT COUNT(*) FROM users
           WHERE id != ? AND (LOWER(student_id) = LOWER(?) OR LOWER(email) = LOWER(?))""",
        (rowid, student_id.strip(), email.strip())
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def add_user(full_name, student_id, email, role, password, program=""):
    """
    Insert a new user into the management database, login database, and Excel
    roster so the account persists across login screen rebuilds.
    Returns (True, message) on success or (False, error_message) on failure.
    """
    full_name = (full_name or "").strip()
    student_id = (student_id or "").strip()
    email = (email or "").strip()
    role = (role or "Student").strip()
    password = password or ""
    program = (program or "N/A").strip() or "N/A"

    if not all([full_name, student_id, email, role, password]):
        return False, "All required fields must be filled out."

    if "@" not in email:
        return False, "Please enter a valid email address."

    if len(password) < 4:
        return False, "Password must be at least 4 characters long."

    if user_exists_by_id_or_email(student_id, email):
        return False, "A user with this Student ID or Email already exists."

    username = email.split("@")[0] if "@" in email else f"user_{student_id}"
    status = "Active"
    salt, pwd_hash = hash_password(password)

    try:
        from utils.db_manager import insert_user_db
        success, error_msg = insert_user_db(full_name, username, student_id, email, program, role, status, pwd_hash, salt)
        if not success:
            return False, error_msg
    except Exception as exc:
        return False, f"Database error: {exc}"

    _sync_user_to_login_db(full_name, username, student_id, email, program, role, pwd_hash, salt)
    excel_ok = _append_user_to_excel(full_name, student_id, email, program, password, role)

    if not excel_ok:
        return True, (
            f"User '{full_name}' was added, but the roster file (Excel) could not be "
            "updated — it may be open in another program. The account works now, but "
            "will be LOST the next time the app restarts unless you close the roster "
            "file and add this user again."
        )
    return True, f"User '{full_name}' was added successfully."


def update_user_account(rowid, full_name, student_id, email, role, password, program, old_email, old_role):
    full_name = (full_name or "").strip()
    student_id = (student_id or "").strip()
    email = (email or "").strip()
    role = (role or "Student").strip()
    program = (program or "N/A").strip() or "N/A"
    password = password or ""

    if not all([full_name, student_id, email, role]):
        return False, "All required fields must be filled out."
    if "@" not in email:
        return False, "Please enter a valid email address."
    if password and len(password) < 4:
        return False, "Password must be at least 4 characters long."
    if user_exists_for_other_account(rowid, student_id, email):
        return False, "Another user already has this Student ID or Email."

    username = email.split("@")[0]
    try:
        from utils.db_manager import update_user_db
        success, error_msg, pwd_hash, salt = update_user_db(rowid, full_name, username, student_id, email, program, role, password)
        if not success:
            return False, error_msg
    except Exception as exc:
        return False, f"Database error: {exc}"

    _remove_user_from_login_db(old_email, old_role)
    _sync_user_to_login_db(full_name, username, student_id, email, program, role, pwd_hash, salt)
    removed_ok = _remove_user_from_excel(old_email, old_role)
    added_ok = _append_user_to_excel(full_name, student_id, email, program, password, role)

    if not (removed_ok and added_ok):
        return True, (
            f"User '{full_name}' was updated, but the roster file (Excel) could not be "
            "fully updated — it may be open in another program. These changes work now, "
            "but may be LOST the next time the app restarts unless you close the roster "
            "file and update this user again."
        )
    return True, f"User '{full_name}' was updated successfully."


def _sync_user_to_login_db(full_name, username, student_id, email, program, role, pwd_hash, salt):
    """Register the new account in the login table matching its role."""
    if not os.path.exists(LOGIN_DB):
        return
    first_name, last_name = split_full_name(full_name)
    table_name = "admins" if role.lower() == "admin" else "regulars"
    try:
        conn = sqlite3.connect(LOGIN_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,)
        )
        if not cursor.fetchone():
            conn.close()
            return

        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        col_lower = {c.lower(): c for c in columns}

        if table_name == "admins":
            mapping = {
                "username": username,
                "password": pwd_hash,
                "salt": salt,
                "role": role,
                "name": full_name,
                "email": email,
                "studentid": student_id,
                "student id": student_id,
                "program": program,
                "status": "Active",
            }
        else:
            mapping = {
                "first name": first_name,
                "last name": last_name,
                "email": email,
                "username": username,
                "password": pwd_hash,
                "salt": salt,
                "student id": student_id,
                "student_id": student_id,
                "major": program,
                "program": program,
                "status": "Active",
            }

        row_data = {}
        for key, value in mapping.items():
            if key in col_lower:
                row_data[col_lower[key]] = value

        if not row_data:
            conn.close()
            return

        placeholders = ", ".join("?" for _ in row_data)
        col_names = ", ".join(f'"{c}"' for c in row_data.keys())
        cursor.execute(
            f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})",
            tuple(row_data.values())
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[usermanagement] login DB sync warning: {exc}")


def _remove_user_from_login_db(email, role):
    if not os.path.exists(LOGIN_DB):
        return
    table_name = "admins" if role.lower() == "admin" else "regulars"
    try:
        conn = sqlite3.connect(LOGIN_DB)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,)
        )
        if cursor.fetchone():
            cursor.execute(
                f"DELETE FROM {table_name} WHERE LOWER(email) = LOWER(?)",
                (email,)
            )
            conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[usermanagement] login DB cleanup warning: {exc}")


def _append_user_to_excel(full_name, student_id, email, program, plain_password, role):
    """Append a new account to the workbook used by its selected login role.
    Returns True if the roster file was actually updated, False otherwise —
    callers use this to warn the admin instead of assuming silent success,
    since a failed write here means the change can be lost on next
    restart (the login screen rebuilds its database from this file)."""
    excel_file = ADMIN_EXCEL_FILE if role.lower() == "admin" else EXCEL_FILE
    if not os.path.exists(excel_file):
        print(f"[usermanagement] Excel append warning: {excel_file} does not exist")
        return False
    try:
        import pandas as pd
        df = pd.read_excel(excel_file, dtype=str).fillna("")
        first_name, last_name = split_full_name(full_name)
        if role.lower() == "admin":
            new_row = {
                "username": email.split("@")[0],
                "password": plain_password,
                "role": role,
                "name": full_name,
                "email": email,
                "studentid": student_id,
                "program": program,
                "status": "Active",
            }
        else:
            new_row = {
                "First Name": first_name,
                "Last Name": last_name,
                "Email": email,
                "Student ID": student_id,
                "Major": program,
                "password": plain_password,
                "username": email.split("@")[0],
            }
        for col in df.columns:
            if col not in new_row:
                new_row[col] = ""
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        df.to_excel(excel_file, index=False)
        return True
    except Exception as exc:
        print(f"[usermanagement] Excel append warning: {exc}")
        return False


def _remove_user_from_excel(email, role):
    """Remove the old row before an edit, including role changes.
    Returns True on a successful write, False if the roster couldn't be
    updated (missing file, locked/open elsewhere, permission error, etc.)."""
    excel_file = ADMIN_EXCEL_FILE if role.lower() == "admin" else EXCEL_FILE
    if not os.path.exists(excel_file):
        print(f"[usermanagement] Excel cleanup warning: {excel_file} does not exist")
        return False
    try:
        import pandas as pd
        df = pd.read_excel(excel_file, dtype=str).fillna("")
        email_columns = [column for column in df.columns if column.lower() == "email"]
        if not email_columns:
            return True  # nothing to remove — not a failure
        email_column = email_columns[0]
        df = df[df[email_column].str.strip().str.lower() != email.strip().lower()]
        df.to_excel(excel_file, index=False)
        return True
    except Exception as exc:
        print(f"[usermanagement] Excel cleanup warning: {exc}")
        return False


def _update_user_status_in_excel(email, role, status):
    """Update the user's status in the underlying login Excel source.
    Returns True on a confirmed write, False if the roster couldn't be
    updated — a False here means this status change is NOT guaranteed to
    survive the next app restart, since login.py rebuilds its database
    from this file."""
    excel_file = ADMIN_EXCEL_FILE if role.lower() == "admin" else EXCEL_FILE
    if not os.path.exists(excel_file):
        print(f"[usermanagement] Excel status sync warning: {excel_file} does not exist")
        return False
    try:
        import pandas as pd
        df = pd.read_excel(excel_file, dtype=str).fillna("")
        cols_map = {col.strip().lower(): col for col in df.columns}
        email_col = cols_map.get("email")
        if not email_col:
            print("[usermanagement] Excel status sync warning: no email column found")
            return False
        status_col = cols_map.get("status")
        if status_col is None:
            status_col = "status"
            df[status_col] = ""
        match = df[email_col].astype(str).str.strip().str.lower() == email.strip().lower()
        if not match.any():
            print(f"[usermanagement] Excel status sync warning: no row found for {email}")
            return False
        df.loc[match, status_col] = status
        df.to_excel(excel_file, index=False)
        return True
    except Exception as exc:
        print(f"[usermanagement] Excel status sync warning: {exc}")
        return False


def load_password_reset_requests(status_filter="Pending"):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    if status_filter == "All":
        cursor.execute(
            "SELECT id, username, email, role, status, requested_at, decided_at, decision_by FROM password_reset_requests ORDER BY requested_at DESC"
        )
    else:
        cursor.execute(
            "SELECT id, username, email, role, status, requested_at, decided_at, decision_by FROM password_reset_requests WHERE status = ? ORDER BY requested_at DESC",
            (status_filter,)
        )
    rows = cursor.fetchall()
    conn.close()
    return rows


def ensure_login_status_columns():
    if not os.path.exists(LOGIN_DB):
        return
    conn = sqlite3.connect(LOGIN_DB)
    cursor = conn.cursor()
    for table_name in ("admins", "regulars"):
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table_name,))
        if not cursor.fetchone():
            continue
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        if "status" not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN status TEXT")
        cursor.execute(f"UPDATE {table_name} SET status = ? WHERE status IS NULL OR TRIM(status) = ''", ("Active",))
    conn.commit()
    conn.close()


def _sync_password_reset_to_login_db(email, role, password_hash, password_salt, status="Active"):
    if not os.path.exists(LOGIN_DB):
        return
    try:
        ensure_login_status_columns()
        conn = sqlite3.connect(LOGIN_DB)
        cursor = conn.cursor()
        table_name = "admins" if str(role).lower() == "admin" else "regulars"
        cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,)
        )
        if cursor.fetchone():
            cursor.execute(
                f"UPDATE {table_name} SET password = ?, salt = ?, status = ? "
                f"WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)",
                (password_hash, password_salt, status, email, email)
            )
            conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[usermanagement] password reset login sync warning: {exc}")


def _sync_password_reset_to_excel(email, role, new_password, status="Active"):
    """Returns True on a confirmed write, False if the roster couldn't be
    updated — a False here means the reset password is NOT guaranteed to
    survive the next app restart, since login.py rebuilds its database
    from this file."""
    excel_file = ADMIN_EXCEL_FILE if str(role).lower() == "admin" else EXCEL_FILE
    if not os.path.exists(excel_file):
        print(f"[usermanagement] password reset excel sync warning: {excel_file} does not exist")
        return False
    try:
        import pandas as pd
        df = pd.read_excel(excel_file, dtype=str).fillna("")
        if "status" not in [col.lower() for col in df.columns]:
            df["status"] = "Active"
        found = False
        for idx, row in df.iterrows():
            if str(row.get("email", "")).strip().lower() == email.lower() or str(row.get("username", "")).strip().lower() == email.lower():
                found = True
                if "password" in df.columns:
                    df.at[idx, "password"] = new_password
                df.at[idx, "status"] = status
                break
        if not found:
            print(f"[usermanagement] password reset excel sync warning: no row found for {email}")
            return False
        df.to_excel(excel_file, index=False)
        return True
    except Exception as exc:
        print(f"[usermanagement] password reset excel sync warning: {exc}")
        return False


def approve_password_reset_request(request_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT email, role, password_hash, password_salt, password_plain FROM password_reset_requests WHERE id = ? AND status = ?",
        (request_id, "Pending")
    )
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False, "Selected request is not pending or does not exist."

    email, role, password_hash, password_salt, password_plain = row
    cursor.execute(
        "UPDATE users SET password_hash = ?, password_salt = ?, status = ? WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)",
        (password_hash, password_salt, "Active", email, email)
    )
    cursor.execute(
        "UPDATE password_reset_requests SET status = ?, decided_at = ?, decision_by = ?, decision_note = ? WHERE id = ?",
        ("Approved", datetime.now().isoformat(), "Admin", "Approved by admin", request_id)
    )
    conn.commit()
    conn.close()

    _sync_password_reset_to_login_db(email, role, password_hash, password_salt, "Active")
    excel_ok = _sync_password_reset_to_excel(email, role, password_plain, "Active")

    if not excel_ok:
        return True, (
            "Password reset approved and active now, but the roster file (Excel) "
            "could not be updated — it may be open in another program. The new "
            "password will be LOST the next time the app restarts unless the roster "
            "file is closed and this request is processed again."
        )
    return True, "Password reset request approved."


def deny_password_reset_request(request_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM password_reset_requests WHERE id = ? AND status = ?",
        (request_id, "Pending")
    )
    if not cursor.fetchone():
        conn.close()
        return False, "Selected request is not pending or does not exist."
    cursor.execute(
        "UPDATE password_reset_requests SET status = ?, decided_at = ?, decision_by = ?, decision_note = ? WHERE id = ?",
        ("Denied", datetime.now().isoformat(), "Admin", "Denied by admin", request_id)
    )
    conn.commit()
    conn.close()
    return True, "Password reset request denied."


def toggle_user_status(rowid, new_status):
    """Updates a user's status in the SQLite database and the login database.
    Returns (success, message) — success reflects whether the change was
    applied at all; message flags it if the Excel roster sync failed, since
    that means the status change may be LOST on the next app restart."""
    normalized_status = normalize_status(new_status)
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT email, role FROM users WHERE id = ?", (rowid,))
    user_row = cursor.fetchone()
    cursor.execute("UPDATE users SET status = ? WHERE id = ?", (normalized_status, rowid))
    conn.commit()
    conn.close()

    if not user_row:
        return False, "Could not find that user to update."

    email, role = user_row
    table_name = "admins" if str(role).lower() == "admin" else "regulars"
    if not os.path.exists(LOGIN_DB):
        return True, (
            f"Status updated to {normalized_status}, but the login database was not "
            "found, so this change is not synced to the login screen."
        )

    try:
        login_conn = sqlite3.connect(LOGIN_DB)
        login_cursor = login_conn.cursor()
        login_cursor.execute(
            f"SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,)
        )
        if login_cursor.fetchone():
            login_cursor.execute(
                f"UPDATE {table_name} SET status = ? WHERE LOWER(email) = LOWER(?) OR LOWER(username) = LOWER(?)",
                (normalized_status, email, email)
            )
            login_conn.commit()
        login_conn.close()
    except Exception as exc:
        print(f"[usermanagement] status sync warning: {exc}")

    # Persist suspension state in the Excel source used by the login screen.
    excel_ok = _update_user_status_in_excel(email, role, normalized_status)

    if not excel_ok:
        return True, (
            f"Status updated to {normalized_status}, but the roster file (Excel) "
            "could not be updated — it may be open in another program. This change "
            "will be LOST the next time the app restarts unless you close the "
            "roster file and toggle the status again."
        )
    return True, f"Status updated to {normalized_status}."

# ===================== WINDOW SETUP =====================
import customtkinter as ctk


PAGE_BG = "#F8FAFC"
CARD_BG = "#FFFFFF"
BORDER = "#E2E8F0"
TEXT_MAIN = "#111827"
TEXT_SUB = "#6B7280"
HOVER_TINT = "#F3F7F6"

def open_screen(parent):

    global SCREEN_H, SCREEN_W, new_window, user_tree
    global search_var, role_var, status_var
    
    new_window = ctk.CTkToplevel(parent)
    new_window.attributes("-fullscreen", True)
    new_window.title("User Management")
    new_window.configure(fg_color=PAGE_BG)
    new_window.bind("<Escape>", lambda event: theme.exit_program(new_window))

    new_window.update()
    SCREEN_W = new_window.winfo_screenwidth()
    SCREEN_H = new_window.winfo_screenheight()

    # ===================== STYLE SETUP =====================
    theme.setup_modern_treeview_style()

    # ===================== RUN DATABASE SETUP =====================
    import threading
    threading.Thread(target=setup_database, daemon=True).start()

    # ===================== CANVAS SETUP =====================
    canvas = tk.Canvas(new_window, width=SCREEN_W, height=SCREEN_H, bd=0, highlightthickness=0, bg=PAGE_BG)
    canvas.pack(fill="both", expand=True)

    theme.build_header(new_window, canvas)

    # ===================== MAIN CONTENT =====================
    header_h = getattr(theme, "HEADER_HEIGHT", 80)
    
    content_frame = ctk.CTkFrame(new_window, fg_color=PAGE_BG, corner_radius=0)
    content_frame.pack(fill="both", expand=True)
    canvas.create_window(SCREEN_W // 2, (SCREEN_H + header_h) // 2, window=content_frame, width=SCREEN_W - 80, height=SCREEN_H - header_h - 40)

    content_card = ctk.CTkFrame(content_frame, fg_color=CARD_BG, corner_radius=15, border_width=1, border_color="#E2E8F0")
    content_card.pack(fill="both", expand=True, padx=20, pady=20)

    # Page Title
    title_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    title_frame.pack(fill="x", padx=24, pady=(24, 8))

    ctk.CTkLabel(title_frame, text="User Management", font=("Segoe UI", 24, "bold"), text_color=theme.PRIMARY).pack(side="left")
    ctk.CTkLabel(title_frame, text="Manage student accounts, filters, and status updates.", font=("Segoe UI", 12), text_color=TEXT_SUB).pack(side="left", padx=(12, 0), pady=(4, 0))

    # ===================== TOP BAR (FILTERS) =====================
    top_bar = ctk.CTkFrame(content_card, fg_color="transparent")
    top_bar.pack(fill="x", padx=24, pady=(10, 14))

    search_var = tk.StringVar()
    role_var = tk.StringVar(value="All")
    status_var = tk.StringVar(value="All")

    search_entry = ctk.CTkEntry(top_bar, textvariable=search_var, width=300, font=("Segoe UI", 13), fg_color=PAGE_BG, border_color="#E2E8F0", placeholder_text="Search accounts...", text_color=TEXT_MAIN)
    search_entry.pack(side="left", padx=(0, 8))

    role_combo = ctk.CTkOptionMenu(top_bar, variable=role_var, values=["All", "Admin", "Student", "Professor"], width=150, fg_color=PAGE_BG, text_color=TEXT_MAIN, button_color=theme.PRIMARY, button_hover_color="#1B5349")
    role_combo.pack(side="left", padx=(0, 8))

    status_combo = ctk.CTkOptionMenu(top_bar, variable=status_var, values=["All", "Active", "Suspended"], width=150, fg_color=PAGE_BG, text_color=TEXT_MAIN, button_color=theme.PRIMARY, button_hover_color="#1B5349")
    status_combo.pack(side="left", padx=(0, 8))

    # We must define open_password_reset_requests_window before calling it, or use lambda
    request_button = ctk.CTkButton(top_bar, text="Manage Reset Requests", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY, hover_color="#1B5349", command=lambda: open_password_reset_requests_window())
    request_button.pack(side="right", padx=(12, 0))
    
    add_button = ctk.CTkButton(top_bar, text="+ Add User", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY, hover_color="#1B5349", command=lambda: open_add_user_form())
    add_button.pack(side="right")

    # ===================== BOTTOM BAR (ACTIONS) =====================
    button_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    button_frame.pack(side="bottom", fill="x", padx=24, pady=(0, 24))

    ctk.CTkButton(button_frame, text="Edit Selected", font=("Segoe UI", 12, "bold"), height=36, fg_color=theme.PRIMARY, text_color="white", hover_color="#1B5349", command=lambda: open_edit_user_form()).pack(side="left", padx=(0, 8))
    ctk.CTkButton(button_frame, text="Delete Selected", font=("Segoe UI", 12, "bold"), height=36, fg_color="#E74C3C", text_color="white", hover_color="#C0392B", command=lambda: delete_selected_user_gui()).pack(side="left", padx=8)
    ctk.CTkButton(button_frame, text="Toggle Status", font=("Segoe UI", 12, "bold"), height=36, fg_color=theme.PRIMARY, text_color="white", hover_color="#1B5349", command=lambda: toggle_selected_status_gui()).pack(side="left", padx=8)
    ctk.CTkButton(button_frame, text="Refresh", font=("Segoe UI", 12, "bold"), height=36, fg_color="#9CA3AF", text_color="white", hover_color="#6B7280", command=lambda: refresh_users()).pack(side="left", padx=8)

    # ===================== TABLE (TREEVIEW)
    table_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    table_frame.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 16))

    columns = ("rowid", "name", "username", "student_id", "email", "program", "role", "status")
    headings = ("ID", "Name", "Username", "Student ID", "Email", "Program / Year", "Role", "Status")

    user_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")

    for col, heading in zip(columns, headings):
        user_tree.heading(col, text=heading)
        if col == "rowid":
            user_tree.column(col, width=0, stretch=tk.NO)
        elif col == "name":
            user_tree.column(col, width=220, anchor="w")
        elif col == "email":
            user_tree.column(col, width=280, anchor="w")
        elif col == "program":
            user_tree.column(col, width=180, anchor="w")
        else:
            user_tree.column(col, width=140, anchor="w")

    user_tree.column("role", width=110)
    user_tree.column("status", width=110)

    user_tree.pack(fill="both", expand=True, side="left")

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=user_tree.yview)
    user_tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")

    # ===================== LOGIC FUNCTIONS =====================
    def open_add_user_form():
        form = ui_helpers.create_modal_window(new_window, "Add User", 460, 640, CARD_BG)
        container = ctk.CTkFrame(form, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(container, text="Add New User", font=("Segoe UI", 20, "bold"), text_color=theme.PRIMARY).pack(anchor="w", pady=(0, 16))

        fields = {}
        def add_field(label_text, show=None):
            ctk.CTkLabel(container, text=label_text, font=("Segoe UI", 11, "bold"), text_color=TEXT_SUB).pack(anchor="w", pady=(8, 2))
            entry = ctk.CTkEntry(container, font=("Segoe UI", 12), fg_color=PAGE_BG, border_color="#E2E8F0", show=show if show else "", text_color=TEXT_MAIN)
            entry.pack(fill="x", pady=(0, 2))
            fields[label_text] = entry
            return entry

        add_field("Full Name *")
        add_field("Student / User ID *")
        add_field("Email *")
        add_field("Program / Year").insert(0, "N/A")

        ctk.CTkLabel(container, text="Role *", font=("Segoe UI", 11, "bold"), text_color=TEXT_SUB).pack(anchor="w", pady=(8, 2))
        role_combo_form = ctk.CTkOptionMenu(container, values=["Student", "Professor", "Admin"], font=("Segoe UI", 12), fg_color=PAGE_BG, text_color=TEXT_MAIN, button_color=theme.PRIMARY)
        role_combo_form.set("Student")
        role_combo_form.pack(fill="x", pady=(0, 2))
        fields["Role *"] = role_combo_form

        add_field("Password *", show="*")

        def submit_add_user():
            full_name = fields["Full Name *"].get().strip()
            student_id = fields["Student / User ID *"].get().strip()
            email = fields["Email *"].get().strip()
            program = fields["Program / Year"].get().strip()
            role = role_combo_form.get().strip()
            password = fields["Password *"].get()

            if not messagebox.askyesno("Confirm New User", f"Add {role} account for {full_name or 'this user'}?"): return
            success, message = add_user(full_name, student_id, email, role, password, program)
            if success:
                messagebox.showinfo("Success", message)
                form.destroy()
                refresh_users()
            else:
                messagebox.showerror("Could Not Add User", message)

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(20, 0))
        ctk.CTkButton(btn_row, text="Confirm Add User", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY, text_color="white", hover_color="#1B5349", command=submit_add_user).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancel", font=("Segoe UI", 12, "bold"), fg_color="#9CA3AF", text_color="white", hover_color="#6B7280", command=form.destroy).pack(side="left")


    def open_edit_user_form():
        item = user_tree.focus()
        if not item:
            messagebox.showwarning("Select User", "Please select a user to edit.")
            return

        values = user_tree.item(item, "values")
        rowid, old_email, old_role = values[0], values[4], values[6]
        
        form = ui_helpers.create_modal_window(new_window, "Edit User", 460, 640, CARD_BG)
        container = ctk.CTkFrame(form, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=28, pady=24)
        
        ctk.CTkLabel(container, text="Edit User", font=("Segoe UI", 20, "bold"), text_color=theme.PRIMARY).pack(anchor="w", pady=(0, 16))

        fields = {}
        def add_edit_field(label_text, value="", show=None):
            ctk.CTkLabel(container, text=label_text, font=("Segoe UI", 11, "bold"), text_color=TEXT_SUB).pack(anchor="w", pady=(8, 2))
            entry = ctk.CTkEntry(container, font=("Segoe UI", 12), fg_color=PAGE_BG, border_color="#E2E8F0", show=show if show else "", text_color=TEXT_MAIN)
            entry.insert(0, value)
            entry.pack(fill="x", pady=(0, 2))
            fields[label_text] = entry

        add_edit_field("Full Name *", values[1])
        add_edit_field("Student / User ID *", values[3])
        add_edit_field("Email *", values[4])
        add_edit_field("Program / Year", values[5])

        ctk.CTkLabel(container, text="Role *", font=("Segoe UI", 11, "bold"), text_color=TEXT_SUB).pack(anchor="w", pady=(8, 2))
        role_combo_form = ctk.CTkOptionMenu(container, values=["Student", "Professor", "Admin"], font=("Segoe UI", 12), fg_color=PAGE_BG, text_color=TEXT_MAIN, button_color=theme.PRIMARY)
        role_combo_form.set(values[6] or "Student")
        role_combo_form.pack(fill="x", pady=(0, 2))
        fields["Role *"] = role_combo_form
        
        add_edit_field("New Password", show="*")

        def submit_edit_user():
            full_name = fields["Full Name *"].get().strip()
            student_id = fields["Student / User ID *"].get().strip()
            email = fields["Email *"].get().strip()
            program = fields["Program / Year"].get().strip()
            role = role_combo_form.get().strip()
            password = fields["New Password"].get()
            if not messagebox.askyesno("Confirm Changes", f"Save changes for {full_name or 'this user'}?"): return
            success, message = update_user_account(rowid, full_name, student_id, email, role, password, program, old_email, old_role)
            if success:
                messagebox.showinfo("Success", message)
                form.destroy()
                refresh_users()
            else:
                messagebox.showerror("Could Not Update User", message)

        btn_row = ctk.CTkFrame(container, fg_color="transparent")
        btn_row.pack(fill="x", pady=(20, 0))
        ctk.CTkButton(btn_row, text="Save Changes", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY, text_color="white", hover_color="#1B5349", command=submit_edit_user).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_row, text="Cancel", font=("Segoe UI", 12, "bold"), fg_color="#9CA3AF", text_color="white", hover_color="#6B7280", command=form.destroy).pack(side="left")


    def refresh_users(*args):
        selected_item = user_tree.focus() or (user_tree.selection()[0] if user_tree.selection() else None)
        selected_id = str(user_tree.item(selected_item, "values")[0]) if selected_item and user_tree.exists(selected_item) and user_tree.item(selected_item, "values") else None

        for item in user_tree.get_children():
            user_tree.delete(item)
        rows = load_user_accounts(search_var.get().strip(), role_var.get(), status_var.get())
        for row in rows:
            formatted_row = list(row)
            formatted_row[6] = formatted_row[6].capitalize() if formatted_row[6] else ""
            formatted_row[7] = formatted_row[7].capitalize() if formatted_row[7] else ""
            item_id = str(row[0])
            user_tree.insert("", "end", iid=item_id, values=formatted_row)

        if selected_id and user_tree.exists(selected_id):
            user_tree.selection_set(selected_id)
            user_tree.focus(selected_id)
            user_tree.see(selected_id)


    def delete_selected_user_gui():
        item = user_tree.focus()
        if not item:
            messagebox.showwarning("Select User", "Please select a user to delete.")
            return
        values = user_tree.item(item, "values")
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete user '{values[2]}'?"):
            delete_user_account(values[0]) 
            refresh_users()
            messagebox.showinfo("Success", "User deleted successfully.")


    def open_password_reset_requests_window():
        request_window = ui_helpers.create_modal_window(new_window, "Password Reset Requests", 940, 560, CARD_BG)
        container = ctk.CTkFrame(request_window, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=24, pady=24)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", side="top", pady=(0, 16))
        ctk.CTkLabel(header, text="Password Reset Requests", font=("Segoe UI", 20, "bold"), text_color=theme.PRIMARY).pack(side="left")

        status_var_req = tk.StringVar(value="Pending")
        status_combo_req = ctk.CTkOptionMenu(header, variable=status_var_req, values=["Pending", "Approved", "Denied", "All"], fg_color=PAGE_BG, text_color=TEXT_MAIN, button_color=theme.PRIMARY, width=120)
        status_combo_req.pack(side="right")

        action_frame = ctk.CTkFrame(container, fg_color="transparent")
        action_frame.pack(side="bottom", fill="x", pady=(16, 0))
        
        ctk.CTkButton(action_frame, text="Approve Request", font=("Segoe UI", 12, "bold"), fg_color=theme.PRIMARY, hover_color="#1B5349", height=38, command=lambda: approve_selected_request(req_tree)).pack(side="left", padx=(0, 10))
        ctk.CTkButton(action_frame, text="Deny Request", font=("Segoe UI", 12, "bold"), fg_color="#E74C3C", hover_color="#C0392B", height=38, command=lambda: deny_selected_request(req_tree)).pack(side="left", padx=10)
        ctk.CTkButton(action_frame, text="Refresh", font=("Segoe UI", 12, "bold"), fg_color="#9CA3AF", hover_color="#6B7280", height=38, command=lambda: load_requests(req_tree)).pack(side="left", padx=10)
        ctk.CTkButton(action_frame, text="Cancel", font=("Segoe UI", 12, "bold"), fg_color="#6B7280", hover_color="#4B5563", height=38, command=request_window.destroy).pack(side="right")

        body_frame = ctk.CTkFrame(container, fg_color="transparent")
        body_frame.pack(fill="both", expand=True)

        req_columns = ("id", "username", "email", "role", "status", "requested_at", "decided_at", "decision_by")
        req_headings = ("ID", "Username", "Email", "Role", "Status", "Requested At", "Decided At", "Decision By")

        req_tree = ttk.Treeview(body_frame, columns=req_columns, show="headings", selectmode="browse")
        for col, heading in zip(req_columns, req_headings):
            req_tree.heading(col, text=heading)
            req_tree.column(col, width=110 if col == "email" else 100, anchor="w")
        req_tree.column("email", width=220)
        req_tree.column("requested_at", width=180)
        req_tree.column("decided_at", width=180)
        req_tree.pack(fill="both", expand=True, side="left")

        scrollbar = ttk.Scrollbar(body_frame, orient="vertical", command=req_tree.yview)
        req_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        def load_requests(tree, *args):
            for item in tree.get_children():
                tree.delete(item)
            rows = load_password_reset_requests(status_var_req.get())
            for row in rows:
                tree.insert("", "end", iid=str(row[0]), values=row)

        def approve_selected_request(tree):
            selected = tree.focus()
            if not selected:
                messagebox.showwarning("Select Request", "Please select a request to approve.")
                return
            if not messagebox.askyesno("Confirm", "Approve this password reset request?"): return
            success, message = approve_password_reset_request(int(selected))
            if success:
                messagebox.showinfo("Approved", message)
                load_requests(tree)
            else:
                messagebox.showerror("Error", message)

        def deny_selected_request(tree):
            selected = tree.focus()
            if not selected:
                messagebox.showwarning("Select Request", "Please select a request to deny.")
                return
            if not messagebox.askyesno("Confirm", "Deny this password reset request?"): return
            success, message = deny_password_reset_request(int(selected))
            if success:
                messagebox.showinfo("Denied", message)
                load_requests(tree)
            else:
                messagebox.showerror("Error", message)

        # CTkOptionMenu command
        status_combo_req.configure(command=lambda _: load_requests(req_tree))
        load_requests(req_tree)


    def toggle_selected_status_gui():
        item = user_tree.focus()
        if not item:
            messagebox.showwarning("Select User", "Please select a user to toggle status.")
            return

        values = user_tree.item(item, "values")
        rowid = values[0]
        current_status = normalize_status(values[7])
        new_status = "Suspended" if current_status == "Active" else "Active"

        success, message = toggle_user_status(rowid, new_status)
        if success and "LOST" in message:
            messagebox.showwarning("Status Updated — Action Needed", message)
        elif not success:
            messagebox.showerror("Could Not Update Status", message)
        refresh_users()

    search_var.trace_add("write", refresh_users)
    role_combo.configure(command=lambda _: refresh_users())
    status_combo.configure(command=lambda _: refresh_users())

    refresh_users()
    new_window.grab_set()
    return new_window

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    open_screen(root)
    root.mainloop()
