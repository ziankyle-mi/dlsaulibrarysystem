import os
import sys
import sqlite3
from datetime import datetime, timedelta
import customtkinter as ctk
import tkinter as tk
from utils import sweetalert as messagebox
from utils.db_manager import hash_password_db

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FOLDER = os.path.join(BASE_DIR, "database")
BOOKS_DB = os.path.join(DB_FOLDER, "books_system.db")
STUDENTS_DB = os.path.join(DB_FOLDER, "regularlogindatabase.db")
LOGIN_DB = os.path.join(DB_FOLDER, "login_system.db")

class DemoMenu(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Developer Tools [Demo Mode]")
        self.geometry("450x450")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        # Center the window
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (450 // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (450 // 2)
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

        self.configure(fg_color="#1e1e1e") # Dark theme for dev tools

        lbl = ctk.CTkLabel(self, text="Developer Tools (Demo Only)", font=("Consolas", 18, "bold"), text_color="#00FF00")
        lbl.pack(pady=(20, 10))
        
        info = ctk.CTkLabel(self, text="These actions directly mutate the database to help\nset up scenarios for demonstrations.", font=("Consolas", 11), text_color="#AAAAAA")
        info.pack(pady=(0, 20))



        # Generate Borrow Record
        btn_borrow = ctk.CTkButton(self, text="1. Generate Borrow Record (Pick Student & Book)", fg_color="#333333", hover_color="#555555", font=("Consolas", 12), command=self.open_borrow_generator)
        btn_borrow.pack(fill="x", padx=40, pady=10, ipady=5)

        # Reset Borrowed Books
        btn_reset = ctk.CTkButton(self, text="3. Reset All Borrowed Books", fg_color="#8B8000", hover_color="#B8860B", font=("Consolas", 12), command=self.reset_all_borrowed_books)
        btn_reset.pack(fill="x", padx=40, pady=10, ipady=5)

        # Clear All Books
        btn_clear = ctk.CTkButton(self, text="4. Clear ALL Books Inventory", fg_color="#8B0000", hover_color="#B22222", font=("Consolas", 12), command=self.clear_all_books_inventory)
        btn_clear.pack(fill="x", padx=40, pady=10, ipady=5)
        
        # Close
        btn_close = ctk.CTkButton(self, text="Close Dev Tools", fg_color="transparent", text_color="#AAAAAA", hover_color="#222222", font=("Consolas", 12), command=self.destroy)
        btn_close.pack(pady=(20, 0))



    def open_borrow_generator(self):
        try:
            # Fetch students
            students = []
            with sqlite3.connect(LOGIN_DB) as conn:
                cur = conn.cursor()
                cur.execute('SELECT "student id", username, email FROM regulars')
                for row in cur.fetchall():
                    # format: student_id | username | email
                    students.append(f"{row[0]} | {row[1]} | {row[2]}")
            
            if not students:
                messagebox.showerror("Error", "No students found in database.")
                return

            # Fetch books
            books = []
            with sqlite3.connect(BOOKS_DB) as conn:
                cur = conn.cursor()
                cur.execute("SELECT book_code, book_title FROM books")
                for row in cur.fetchall():
                    books.append(f"{row[0]} | {row[1]}")

            if not books:
                messagebox.showerror("Error", "No books found in inventory.")
                return

            # Open popup
            popup = ctk.CTkToplevel(self)
            popup.title("Generate Borrow Record")
            popup.geometry("400x420")
            popup.transient(self)
            popup.grab_set()

            ctk.CTkLabel(popup, text="Select Student:", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
            student_var = ctk.StringVar(value=students[0])
            student_combo = ctk.CTkComboBox(popup, values=students, variable=student_var, width=300)
            student_combo.pack(pady=5)

            ctk.CTkLabel(popup, text="Select Book:", font=("Segoe UI", 12, "bold")).pack(pady=(20, 5))
            book_var = ctk.StringVar(value=books[0])
            book_combo = ctk.CTkComboBox(popup, values=books, variable=book_var, width=300)
            book_combo.pack(pady=5)

            def submit_record(is_overdue):
                s_parts = student_var.get().split(" | ")
                if len(s_parts) != 3: return
                s_id, s_name, s_email = s_parts
                
                b_parts = book_var.get().split(" | ")
                if len(b_parts) != 2: return
                b_code, b_title = b_parts

                if is_overdue:
                    # Borrowed 30 days ago, due 15 days ago
                    borrow_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
                    return_date = (datetime.now() - timedelta(days=15)).strftime("%Y-%m-%d")
                    msg = "Overdue record"
                else:
                    # Borrowed today, due in 15 days
                    borrow_date = datetime.now().strftime("%Y-%m-%d")
                    return_date = (datetime.now() + timedelta(days=15)).strftime("%Y-%m-%d")
                    msg = "Active borrow record"

                try:
                    with sqlite3.connect(BOOKS_DB) as conn:
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO borrow_records (book_code, book_title, student_name, student_id, student_email, borrow_date, return_date, status)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 'borrowed')
                        """, (b_code, b_title, s_name, s_id, s_email, borrow_date, return_date))
                        
                        cur.execute("UPDATE books SET is_borrowed = 1, available_copies = MAX(0, available_copies - 1) WHERE book_code=?", (b_code,))
                        conn.commit()
                    messagebox.showinfo("Dev Tool", f"{msg} created for {s_name} with '{b_title}'.")
                    popup.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

            ctk.CTkButton(popup, text="Inject ACTIVE Record (Not Overdue)", fg_color="#10B981", hover_color="#059669", command=lambda: submit_record(False)).pack(pady=(30, 10))
            ctk.CTkButton(popup, text="Inject OVERDUE Record (Late)", fg_color="#E74C3C", hover_color="#C0392B", command=lambda: submit_record(True)).pack(pady=(0, 30))
            
        except Exception as e:
            messagebox.showerror("Dev Tool Error", str(e))

    def reset_all_borrowed_books(self):
        confirm = messagebox.askyesno("Dev Tool", "Reset all borrowed books to available?")
        if not confirm: return
        try:
            with sqlite3.connect(BOOKS_DB) as conn:
                cur = conn.cursor()
                cur.execute("UPDATE books SET is_borrowed = 0, available_copies = COALESCE(total_copies, 1)")
                cur.execute("DELETE FROM borrow_records")
                conn.commit()
            messagebox.showinfo("Dev Tool", "All borrowed books reset.")
        except Exception as e:
            messagebox.showerror("Dev Tool Error", str(e))

    def clear_all_books_inventory(self):
        pwd = ctk.CTkInputDialog(text="Enter dev code (delasallearaneta):", title="Dev Tool").get_input()
        if pwd == "delasallearaneta":
            try:
                with sqlite3.connect(BOOKS_DB) as conn:
                    cur = conn.cursor()
                    cur.execute("DELETE FROM books")
                    conn.commit()
                messagebox.showinfo("Dev Tool", "All books cleared.")
            except Exception as e:
                messagebox.showerror("Dev Tool Error", str(e))

def open_demo_menu(parent):
    DemoMenu(parent)
