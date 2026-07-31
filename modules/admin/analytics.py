# ===================== IMPORTS =====================
import os
import sys
import sqlite3
import webbrowser
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from utils import sweetalert
messagebox = sweetalert  # SweetAlert2-styled popups (see sweetalert.py)

try:
    from utils import theme  # Injects your customized structural design system
except ImportError as e:
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    messagebox.showerror("Import Error", f"Could not find 'theme.py' in this folder!\nDetails: {e}")
    sys.exit()

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.backends.backend_pdf import PdfPages
except ImportError as e:
    import customtkinter as ctk
    root = ctk.CTk()
    root.withdraw()
    messagebox.showerror(
        "Missing Library",
        "This screen needs matplotlib to draw the charts.\n\n"
        "Install it first with:\n    pip install matplotlib\n\n"
        f"Details: {e}"
    )
    sys.exit()

# theme.py only ships PRIMARY, so match the hover/accent pairing already
# used across the other screens (bookinventory.py, studentborrowing.py)
PRIMARY_HOVER = "#1B5349"
ACCENT = "#2F7D6B"
MUTED = "#8A8A8A"

# ===================== DATABASE CONFIGURATION =====================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_FOLDER = os.path.join(BASE_DIR, "database")

BOOKS_DB = os.path.join(DB_FOLDER, "books_system.db")             # books + borrow_records
STUDENTS_DB = os.path.join(DB_FOLDER, "regularlogindatabase.db")  # students

TOP_N = 10          # how many bars to show on the ranked charts
AUTO_REFRESH_MS = 10000  # redraw every 10 seconds so this screen stays live


def ensure_schema():
    """Make sure the tables this screen reads from exist, even on a fresh install."""
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Bring older databases up to date with the columns added for
    # multi-copy inventory tracking and the fine-paid sync flag.
    cursor.execute("PRAGMA table_info(books)")
    book_columns = {row[1] for row in cursor.fetchall()}
    if "total_copies" not in book_columns:
        cursor.execute("ALTER TABLE books ADD COLUMN total_copies INTEGER DEFAULT 1")
    if "available_copies" not in book_columns:
        cursor.execute("ALTER TABLE books ADD COLUMN available_copies INTEGER DEFAULT 1")

    cursor.execute("PRAGMA table_info(borrow_records)")
    borrow_columns = {row[1] for row in cursor.fetchall()}
    if "fine_paid" not in borrow_columns:
        cursor.execute("ALTER TABLE borrow_records ADD COLUMN fine_paid INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


def fetch_student_lookup():
    """Pulls the student roster into a dict keyed by student_id (same approach as studentborrowing.py)."""
    lookup = {}
    try:
        conn = sqlite3.connect(STUDENTS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT student_id, name, program FROM users")
        for student_id, name, program in cursor.fetchall():
            lookup[student_id] = {"name": name, "program": program}
        conn.close()
    except Exception as e:
        print(f"Could not read student roster: {e}")
    return lookup


# ===================== ANALYTICS QUERIES =====================

def get_summary_stats():
    """Headline numbers shown in the stat cards at the top of the screen."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM books")
    total_books = cursor.fetchone()[0] or 0

    # Sum of copies actually out on loan across every title, not just titles
    # that are fully depleted — a book with 2 of 5 copies out still counts.
    cursor.execute("SELECT COALESCE(SUM(COALESCE(total_copies, 1) - COALESCE(available_copies, 1)), 0) FROM books")
    currently_borrowed = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COUNT(*) FROM borrow_records")
    total_transactions = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COUNT(DISTINCT student_id) FROM borrow_records
        WHERE student_id IS NOT NULL AND student_id != ''
    """)
    total_borrowers = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT b.category, COUNT(*) as cnt
        FROM borrow_records br
        JOIN books b ON br.book_code = b.book_code
        WHERE b.category IS NOT NULL AND b.category != ''
        GROUP BY b.category
        ORDER BY cnt DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    top_genre = row[0] if row else "N/A"

    conn.close()
    return {
        "total_books": total_books,
        "currently_borrowed": currently_borrowed,
        "total_transactions": total_transactions,
        "total_borrowers": total_borrowers,
        "top_genre": top_genre,
    }


def get_top_books(limit=TOP_N):
    """Most borrowed book titles, ranked by number of borrow transactions."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT book_title, COUNT(*) as cnt
        FROM borrow_records
        WHERE book_title IS NOT NULL AND book_title != ''
        GROUP BY book_title
        ORDER BY cnt DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_top_genres(limit=TOP_N):
    """Most borrowed categories/genres, joining borrow_records to books for the category."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT b.category, COUNT(*) as cnt
        FROM borrow_records br
        JOIN books b ON br.book_code = b.book_code
        WHERE b.category IS NOT NULL AND b.category != ''
        GROUP BY b.category
        ORDER BY cnt DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_top_borrowers(limit=TOP_N):
    """Students with the most borrow transactions, enriched with their name from the student roster."""
    lookup = fetch_student_lookup()

    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT student_id, student_name, COUNT(*) as cnt
        FROM borrow_records
        GROUP BY student_id
        ORDER BY cnt DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()

    results = []
    for student_id, student_name, cnt in rows:
        info = lookup.get(student_id, {})
        display_name = info.get("name") or student_name or (student_id or "Unknown")
        results.append((display_name, cnt))
    return results


def get_status_breakdown():
    """Borrowed / Overdue / Returned counts, using the same live-status logic as studentborrowing.py."""
    conn = sqlite3.connect(BOOKS_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT return_date, status FROM borrow_records")
    rows = cursor.fetchall()
    conn.close()

    today = datetime.now().date()
    counts = {"Borrowed": 0, "Overdue": 0, "Returned": 0}

    for return_date, status in rows:
        live_status = (status or "borrowed").strip().lower()
        if live_status == "borrowed":
            try:
                due = datetime.strptime(return_date, "%Y-%m-%d").date()
                if due < today:
                    live_status = "overdue"
            except (ValueError, TypeError):
                pass
        key = live_status.capitalize()
        counts[key] = counts.get(key, 0) + 1

    return counts


ensure_schema()

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
ACCENT = "#2F7D6B"

# ===================== WINDOW SETUP =====================
def open_screen(parent):
    global SCREEN_H, SCREEN_W, app, btn_print, btn_refresh, card_value_labels, last_updated_label, notebook, style, top_bar
    app = ctk.CTkToplevel(parent)
    app.attributes("-fullscreen", True)
    app.title("Analytics & Reports")
    app.configure(fg_color=PAGE_BG)
    app.bind("<Escape>", lambda event: theme.exit_program(app))

    app.update()
    SCREEN_W = app.winfo_screenwidth()
    SCREEN_H = app.winfo_screenheight()

    # ===================== CANVAS SETUP =====================
    main_canvas = Canvas(app, width=SCREEN_W, height=SCREEN_H, bd=0, highlightthickness=0, bg=PAGE_BG)
    main_canvas.pack(fill="both", expand=True)

    try:
        theme.build_header(app, main_canvas)
    except Exception as e:
        messagebox.showerror("Theme Render Error", f"Error: {e}")
        app.destroy()
        return

    # ===================== MAIN CONTENT =====================
    header_h = getattr(theme, "HEADER_HEIGHT", 80)
    
    content_frame = Frame(app, bg=PAGE_BG)
    main_canvas.create_window(SCREEN_W // 2, (SCREEN_H + header_h) // 2, window=content_frame, width=SCREEN_W - 80, height=SCREEN_H - header_h - 40)

    content_card = ctk.CTkFrame(content_frame, fg_color=CARD_BG, corner_radius=15, border_width=1, border_color=BORDER)
    content_card.pack(fill="both", expand=True, padx=20, pady=20)

    # ===================== TITLE & TOOLBAR =====================
    top_bar = ctk.CTkFrame(content_card, fg_color="transparent")
    top_bar.pack(fill="x", padx=24, pady=(24, 16))

    title_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
    title_frame.pack(side="left")
    
    ctk.CTkLabel(title_frame, text="Analytics & Reports", font=("Segoe UI", 24, "bold"), text_color=PRIMARY).pack(side="left")
    ctk.CTkLabel(title_frame, text="Live system usage statistics and book borrowing trends.", font=("Segoe UI", 12), text_color=TEXT_SUB).pack(side="left", padx=(12, 0), pady=(4, 0))

    btn_refresh = ctk.CTkButton(top_bar, text="REFRESH DATA", font=("Segoe UI", 12, "bold"), fg_color=PRIMARY, hover_color=PRIMARY_HOVER, command=lambda: refresh_all())
    btn_refresh.pack(side="right")

    btn_print = ctk.CTkButton(top_bar, text="PRINT REPORT", font=("Segoe UI", 12, "bold"), fg_color=HOVER_TINT, hover_color="#E2E8F0", text_color=PRIMARY, command=lambda: print_analytics_report())
    btn_print.pack(side="right", padx=(0, 10))

    last_updated_label = ctk.CTkLabel(top_bar, text="", font=("Segoe UI", 11, "italic"), text_color=TEXT_SUB)
    last_updated_label.pack(side="right", padx=(0, 15))

    # ===================== SUMMARY STAT CARDS =====================
    cards_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    cards_frame.pack(fill="x", padx=24, pady=(0, 15))

    card_value_labels = {}

    def build_stat_card(parent, key, title, big=True):
        card = ctk.CTkFrame(parent, fg_color=PAGE_BG, corner_radius=10, border_width=1, border_color=BORDER)
        card.pack(side="left", fill="both", expand=True, padx=8)

        value_lbl = ctk.CTkLabel(card, text="--", font=("Segoe UI", 28 if big else 18, "bold"), text_color=PRIMARY, wraplength=180, justify="center")
        value_lbl.pack(pady=(15, 0), padx=10)

        title_lbl = ctk.CTkLabel(card, text=title.upper(), font=("Segoe UI", 11, "bold"), text_color=TEXT_SUB)
        title_lbl.pack(pady=(2, 15))

        card_value_labels[key] = value_lbl

    build_stat_card(cards_frame, "total_books", "Total Books")
    build_stat_card(cards_frame, "currently_borrowed", "Currently Borrowed")
    build_stat_card(cards_frame, "total_transactions", "Borrow Transactions")
    build_stat_card(cards_frame, "total_borrowers", "Active Borrowers")
    build_stat_card(cards_frame, "top_genre", "Top Genre", big=False)

    # ===================== CHART TABS =====================
    notebook_frame = ctk.CTkFrame(content_card, fg_color="transparent")
    notebook_frame.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
        
    style.configure("TNotebook", background=CARD_BG, borderwidth=0)
    style.configure("TNotebook.Tab", font=("Segoe UI", 11, "bold"), padding=(18, 10), background=PAGE_BG, foreground=TEXT_SUB, borderwidth=0)
    style.map("TNotebook.Tab", background=[("selected", PRIMARY)], foreground=[("selected", "white")])

    notebook = ttk.Notebook(notebook_frame)
    notebook.pack(fill="both", expand=True)

    def make_chart_tab(label):
        tab = Frame(notebook, bg=CARD_BG)
        notebook.add(tab, text=label)

        fig = Figure(figsize=(9, 5), dpi=100)
        fig.patch.set_facecolor(CARD_BG)
        ax = fig.add_subplot(111)

        canvas_widget = FigureCanvasTkAgg(fig, master=tab)
        canvas_widget.get_tk_widget().configure(bg=CARD_BG)
        canvas_widget.get_tk_widget().pack(fill="both", expand=True, padx=15, pady=15)

        return fig, ax, canvas_widget

    fig_books, ax_books, canvas_books = make_chart_tab("Top Borrowed Books")
    fig_genres, ax_genres, canvas_genres = make_chart_tab("Most Borrowed Genres")
    fig_students, ax_students, canvas_students = make_chart_tab("Top Borrowers")
    fig_status, ax_status, canvas_status = make_chart_tab("Borrowing Status")

    # ===================== CHART DRAWING HELPERS =====================
    def shade_palette(n, base=PRIMARY, accent=ACCENT):
        def hex_to_rgb(h):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
        def rgb_to_hex(rgb):
            return "#%02x%02x%02x" % rgb
        c1, c2 = hex_to_rgb(base), hex_to_rgb(accent)
        colors = []
        for i in range(n):
            t = i / max(n - 1, 1)
            rgb = tuple(int(c1[j] + (c2[j] - c1[j]) * t) for j in range(3))
            colors.append(rgb_to_hex(rgb))
        return colors

    def draw_empty_state(ax, message="No borrowing data yet.\nBorrow a few books to populate this chart."):
        ax.clear()
        ax.axis("off")
        ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=12, color=TEXT_SUB)

    def draw_top_books():
        ax_books.clear()
        rows = get_top_books()
        if not rows:
            draw_empty_state(ax_books)
        else:
            rows = rows[::-1] 
            titles = [t if len(t) <= 28 else t[:25] + "..." for t, _ in rows]
            counts = [c for _, c in rows]
            colors = shade_palette(len(rows))[::-1]

            ax_books.barh(titles, counts, color=colors)
            ax_books.set_xlabel("Times Borrowed", fontsize=10, color=TEXT_SUB)
            ax_books.set_title("Top Borrowed Books", fontsize=14, fontweight="bold", color=PRIMARY)
            ax_books.tick_params(axis="y", labelsize=10, colors=TEXT_MAIN)
            ax_books.tick_params(axis="x", colors=TEXT_SUB)
            ax_books.xaxis.get_major_locator().set_params(integer=True)
            for spine in ("top", "right"):
                ax_books.spines[spine].set_visible(False)
            for spine in ("left", "bottom"):
                ax_books.spines[spine].set_color(BORDER)
            fig_books.tight_layout()
        canvas_books.draw()

    def draw_top_genres():
        ax_genres.clear()
        rows = get_top_genres()
        if not rows:
            draw_empty_state(ax_genres)
        else:
            labels = [g for g, _ in rows]
            counts = [c for _, c in rows]
            colors = shade_palette(len(rows))

            ax_genres.pie(
                counts, labels=labels, autopct="%1.0f%%", colors=colors,
                startangle=90, textprops={"fontsize": 10, "color": TEXT_MAIN}
            )
            ax_genres.set_title("Most Borrowed Genres", fontsize=14, fontweight="bold", color=PRIMARY)
            ax_genres.axis("equal")
        canvas_genres.draw()

    def draw_top_borrowers():
        ax_students.clear()
        rows = get_top_borrowers()
        if not rows:
            draw_empty_state(ax_students)
        else:
            rows = rows[::-1]
            names = [n if len(n) <= 22 else n[:19] + "..." for n, _ in rows]
            counts = [c for _, c in rows]
            colors = shade_palette(len(rows))[::-1]

            ax_students.barh(names, counts, color=colors)
            ax_students.set_xlabel("Books Borrowed", fontsize=10, color=TEXT_SUB)
            ax_students.set_title("Top Borrowers", fontsize=14, fontweight="bold", color=PRIMARY)
            ax_students.tick_params(axis="y", labelsize=10, colors=TEXT_MAIN)
            ax_students.tick_params(axis="x", colors=TEXT_SUB)
            ax_students.xaxis.get_major_locator().set_params(integer=True)
            for spine in ("top", "right"):
                ax_students.spines[spine].set_visible(False)
            for spine in ("left", "bottom"):
                ax_students.spines[spine].set_color(BORDER)
            fig_students.tight_layout()
        canvas_students.draw()

    def draw_status_breakdown():
        ax_status.clear()
        counts = {k: v for k, v in get_status_breakdown().items() if v > 0}
        if not counts:
            draw_empty_state(ax_status)
        else:
            status_colors = {"Borrowed": PRIMARY, "Overdue": "#EF4444", "Returned": "#10B981"}
            labels = list(counts.keys())
            values = list(counts.values())
            colors = [status_colors.get(l, TEXT_SUB) for l in labels]

            ax_status.pie(values, labels=labels, autopct="%1.0f%%", colors=colors,
                           startangle=90, textprops={"fontsize": 10, "color": TEXT_MAIN})
            ax_status.set_title("Borrowing Status Overview", fontsize=14, fontweight="bold", color=PRIMARY)
            ax_status.axis("equal")
        canvas_status.draw()

    def refresh_all():
        ensure_schema()
        stats = get_summary_stats()
        card_value_labels["total_books"].configure(text=str(stats["total_books"]))
        card_value_labels["currently_borrowed"].configure(text=str(stats["currently_borrowed"]))
        card_value_labels["total_transactions"].configure(text=str(stats["total_transactions"]))
        card_value_labels["total_borrowers"].configure(text=str(stats["total_borrowers"]))
        card_value_labels["top_genre"].configure(text=stats["top_genre"] or "N/A")

        draw_top_books()
        draw_top_genres()
        draw_top_borrowers()
        draw_status_breakdown()

        last_updated_label.configure(text=f"Last updated: {datetime.now().strftime('%I:%M:%S %p')}")

    def print_analytics_report():
        try:
            refresh_all()
            filename = f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            default_dir = os.path.join(BASE_DIR, "database", "reports")
            os.makedirs(default_dir, exist_ok=True)
            report_path = filedialog.asksaveasfilename(
                parent=app,
                title="Save Analytics Report",
                initialdir=default_dir,
                initialfile=filename,
                defaultextension=".pdf",
                filetypes=[("PDF report", "*.pdf"), ("All files", "*.*")],
            )
            if not report_path:
                return
            stats = get_summary_stats()

            summary = Figure(figsize=(11.69, 8.27), dpi=120)
            summary.patch.set_facecolor("white")
            summary.text(0.08, 0.88, "DLSAU LIBRARY", fontsize=25, fontweight="bold", color=PRIMARY)
            summary.text(0.08, 0.82, "Analytics & Reports", fontsize=18, color=ACCENT)
            summary.text(0.08, 0.76, f"Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
                         fontsize=10, color=TEXT_SUB)

            summary_stats = [
                ("Total Books", stats["total_books"]),
                ("Currently Borrowed", stats["currently_borrowed"]),
                ("Borrow Transactions", stats["total_transactions"]),
                ("Active Borrowers", stats["total_borrowers"]),
                ("Top Genre", stats["top_genre"] or "N/A"),
            ]
            for index, (label, value) in enumerate(summary_stats):
                x = 0.08 + (index % 3) * 0.29
                y = 0.58 if index < 3 else 0.38
                summary.text(x, y, str(value), fontsize=24, fontweight="bold", color=PRIMARY)
                summary.text(x, y - 0.06, label.upper(), fontsize=9, color=TEXT_SUB)
            summary.text(0.08, 0.16, "This report is generated from the live library database.",
                         fontsize=10, color=TEXT_SUB)

            with PdfPages(report_path) as pdf:
                pdf.savefig(summary, bbox_inches="tight")
                for figure in (fig_books, fig_genres, fig_students, fig_status):
                    pdf.savefig(figure, bbox_inches="tight")
            summary.clear()

            webbrowser.open(report_path)
            messagebox.showinfo(
                "Report Exported",
                f"The analytics report was saved here:\n\n{report_path}\n\n"
                "It has been opened so you can review or print it."
            )
        except Exception as exc:
            messagebox.showerror("Print Failed", f"Could not create the analytics report:\n{exc}")

    # ===================== INIT + AUTO REFRESH =====================
    refresh_all()

    def auto_refresh():
        refresh_all()
        app.after(AUTO_REFRESH_MS, auto_refresh)

    app.after(AUTO_REFRESH_MS, auto_refresh)
    app.grab_set()
    return app

if __name__ == "__main__":
    root = ctk.CTk()
    root.withdraw()
    open_screen(root)
    root.mainloop()
