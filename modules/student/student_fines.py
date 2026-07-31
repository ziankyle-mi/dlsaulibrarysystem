import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from utils import student_db
from PIL import Image, ImageTk, ImageDraw

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
DANGER = "#EF4444"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
FONT_FAMILY = "Segoe UI"


def create_gradient_bg(width, height, color1, color2):
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)
    # create a smooth horizontal gradient
    for x in range(width):
        r1, g1, b1 = color1
        r2, g2, b2 = color2
        r = int(r1 + (r2 - r1) * (x / width))
        g = int(g1 + (g2 - g1) * (x / width))
        b = int(b1 + (b2 - b1) * (x / width))
        draw.line([(x, 0), (x, height)], fill=(r, g, b, 255))

    # Add subtle rounded corners
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, width, height), radius=24, fill=255)
    img.putalpha(mask)
    return ImageTk.PhotoImage(img)


def open_screen(parent, logged_in_email):
    app = ctk.CTkToplevel(parent)
    app.attributes("-fullscreen", True)
    app.configure(fg_color=PAGE_BG)
    app.title("Fines & Payments")

    def safe_destroy(event=None):
        app.withdraw()
        app.destroy()

    app.bind("<Escape>", safe_destroy)

    SCREEN_W = app.winfo_screenwidth()

    # Header
    header_canvas = tk.Canvas(
        app, width=SCREEN_W, height=70, bg=BRAND, highlightthickness=0, bd=0
    )
    header_canvas.pack(fill="x", side="top")

    exit_btn = ctk.CTkButton(
        app,
        text="✕",
        font=(FONT_FAMILY, 20, "bold"),
        width=40,
        height=40,
        corner_radius=8,
        fg_color="transparent",
        bg_color=BRAND,
        text_color="white",
        hover_color="#E81123",
        command=safe_destroy,
    )
    header_canvas.create_window(SCREEN_W - 30, 35, window=exit_btn, anchor="e")

    back_btn = ctk.CTkButton(
        app,
        text="RETURN TO DASHBOARD",
        font=(FONT_FAMILY, 10, "bold"),
        width=160,
        height=40,
        corner_radius=8,
        fg_color="#F3F7F6",
        bg_color=BRAND,
        text_color=BRAND,
        hover_color="#FFFFFF",
        command=safe_destroy,
    )
    header_canvas.create_window(120, 35, window=back_btn, anchor="center")

    # Main Content
    content = ctk.CTkFrame(app, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=40, pady=40)

    ctk.CTkLabel(
        content,
        text="Financial Overview",
        font=(FONT_FAMILY, 32, "bold"),
        text_color=TEXT_MAIN,
    ).pack(anchor="w", pady=(0, 20))

    # Summary Card (Wallet style)
    total_fine = student_db.get_student_total_fines(logged_in_email)

    card_w = 550
    card_h = 160
    wallet_canvas = tk.Canvas(
        content, width=card_w, height=card_h, bg=PAGE_BG, highlightthickness=0
    )
    wallet_canvas.pack(anchor="w", pady=(0, 30))

    if total_fine > 0:
        app.bg_img = create_gradient_bg(
            card_w, card_h, (239, 68, 68), (185, 28, 28)
        )  # Red Gradient
    else:
        app.bg_img = create_gradient_bg(
            card_w, card_h, (16, 185, 129), (4, 120, 87)
        )  # Green Gradient

    wallet_canvas.create_image(0, 0, image=app.bg_img, anchor="nw")

    wallet_canvas.create_text(
        40,
        50,
        text="Total Outstanding Balance",
        font=(FONT_FAMILY, 14, "bold"),
        fill="#E5E7EB",
        anchor="w",
    )
    wallet_canvas.create_text(
        40,
        100,
        text=f"₱{total_fine}",
        font=(FONT_FAMILY, 56, "bold"),
        fill="#FFFFFF",
        anchor="w",
    )

    if total_fine > 0:
        unpaid_record_ids = []
        fine_books_data = student_db.get_student_fine_records(logged_in_email)
        if fine_books_data:
            for record in fine_books_data:
                (
                    record_id,
                    book_code,
                    book_title,
                    borrow_date,
                    return_date,
                    status,
                    fine_paid,
                    custom_fine,
                ) = record
                overdue_fine = student_db.calculate_fine(return_date)
                total_book_fine = overdue_fine + custom_fine
                if not fine_paid and total_book_fine > 0:
                    payment_status = student_db.get_fine_payment_status(record_id)
                    if payment_status != "pending":
                        unpaid_record_ids.append(record_id)

        def pay_all_fines():
            if not unpaid_record_ids:
                messagebox.showinfo(
                    "No Fines", "All fines are already paid or pending approval."
                )
                return

            titles = []
            for record in fine_books_data:
                (
                    record_id,
                    book_code,
                    book_title,
                    borrow_date,
                    return_date,
                    status,
                    fine_paid,
                    custom_fine,
                ) = record
                if record_id in unpaid_record_ids:
                    titles.append(book_title)

            joined_titles = ", ".join(titles)

            pay_win = ctk.CTkToplevel(app)
            pay_win.title("Fine Payment Instructions")
            pay_win.geometry("500x350")
            pay_win.attributes("-topmost", True)
            pay_win.transient(app)

            pay_win.update_idletasks()
            x = (pay_win.winfo_screenwidth() - 500) // 2
            y = (pay_win.winfo_screenheight() - 350) // 2
            pay_win.geometry(f"+{x}+{y}")

            ctk.CTkLabel(
                pay_win,
                text="Fine Payment Window",
                font=(FONT_FAMILY, 20, "bold"),
                text_color=BRAND,
            ).pack(pady=(20, 10))

            instruction_text = (
                "1. Click the button below to generate a Payment Receipt for ALL fines.\n"
                "2. Present this receipt to the cashier to pay your fine (make sure to print or take a picture of the receipt).\n"
                "3. After paying, you must bring the book(s) (if applicable) along with the official receipt given to you by the cashier to the librarian."
            )
            ctk.CTkLabel(
                pay_win,
                text=instruction_text,
                font=(FONT_FAMILY, 14),
                text_color=TEXT_MAIN,
                justify="left",
                wraplength=450,
            ).pack(padx=20, pady=20)

            # =========================================================
            # PAYMENT LOGIC EXPLAINED:
            # 1. We generate a unique random ID (e.g., PAY-A1B2C) for the receipt.
            # 2. We loop through all unpaid fines and mark them as 'pending'.
            # 3. We print the official receipt using the qr_borrow module.
            # 4. We restart the screen so the red 'unpaid' card turns orange!
            # =========================================================
            def process_payment():
                import uuid
                from utils import qr_borrow

                user_info = student_db.get_current_user_info(logged_in_email)

                txn_dict = {
                    "transaction_id": f"PAY-{uuid.uuid4().hex[:5].upper()}",
                    "user_id": user_info.get("student_id", "N/A"),
                    "user_name": user_info.get("name", "N/A"),
                    "book_title": joined_titles,
                    "borrow_date": "Multiple",
                    "due_date": "Multiple",
                    "fine_amount": f"{total_fine:.2f}",
                }

                for rid in unpaid_record_ids:
                    student_db.request_fine_payment(rid)

                if hasattr(qr_borrow, "print_fine_payment_receipt"):
                    qr_borrow.print_fine_payment_receipt(txn_dict, parent=pay_win)
                else:
                    qr_borrow.print_receipt(txn_dict, parent=pay_win)

                pay_win.destroy()
                app.destroy()
                open_screen(parent, logged_in_email)

            ctk.CTkButton(
                pay_win,
                text="Generate Receipt",
                font=(FONT_FAMILY, 14, "bold"),
                fg_color=BRAND,
                hover_color=BRAND_HOVER,
                command=process_payment,
                height=40,
            ).pack(pady=10)

        pay_all_btn = ctk.CTkButton(
            content,
            text="Pay All Fines",
            command=pay_all_fines,
            font=(FONT_FAMILY, 14, "bold"),
            fg_color=BRAND,
            hover_color=BRAND_HOVER,
            corner_radius=12,
            height=45,
            width=200,
            bg_color="#B91C1C",
        )
        pay_all_btn.place(in_=wallet_canvas, relx=1.0, rely=0.5, x=-30, y=0, anchor="e")

    # Fines List Container (Replacing boxy Treeview with Premium Cards)
    list_container = ctk.CTkScrollableFrame(
        content, fg_color="transparent", bg_color="transparent"
    )
    list_container.pack(fill="both", expand=True, pady=(20, 0))

    fine_books = student_db.get_student_fine_records(logged_in_email)

    if not fine_books:
        empty_lbl = ctk.CTkLabel(
            list_container,
            text="🎉 No outstanding fines!",
            font=(FONT_FAMILY, 16),
            text_color=SUCCESS,
        )
        empty_lbl.pack(pady=40)
    else:
        for record in fine_books:
            (
                record_id,
                book_code,
                book_title,
                borrow_date,
                return_date,
                status,
                fine_paid,
                custom_fine,
            ) = record
            overdue_fine = student_db.calculate_fine(return_date)
            total_book_fine = overdue_fine + custom_fine

            if fine_paid:
                status_text = "Paid"
                total_book_fine = 0
                status_color = SUCCESS
            else:
                payment_status = student_db.get_fine_payment_status(record_id)
                if payment_status == "pending":
                    status_text = "Pending Approval"
                    status_color = WARNING
                else:
                    status_text = "Unpaid"
                    status_color = DANGER

            # Individual Fine Card
            card = ctk.CTkFrame(
                list_container,
                fg_color=CARD_BG,
                corner_radius=20,
                border_width=1,
                border_color="#E5E7EB",
            )
            card.pack(fill="x", pady=12, padx=10, ipady=25)

            # Left: Book Info
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=30, pady=10)

            reason_text = "Overdue Fine"
            reason_color = WARNING
            if status == "damaged":
                reason_text = "Damaged Book"
                reason_color = "#E67E22"
            elif status == "lost":
                reason_text = "Lost Book"
                reason_color = DANGER

            reason_badge = ctk.CTkFrame(
                info_frame, fg_color=reason_color, corner_radius=6
            )
            reason_badge.pack(anchor="w", pady=(0, 6))
            ctk.CTkLabel(
                reason_badge,
                text=f" {reason_text} ",
                font=(FONT_FAMILY, 10, "bold"),
                text_color="white",
            ).pack(padx=8, pady=2)

            ctk.CTkLabel(
                info_frame,
                text=book_title,
                font=(FONT_FAMILY, 20, "bold"),
                text_color=TEXT_MAIN,
                anchor="w",
            ).pack(fill="x")
            details = f"Borrowed: {borrow_date}   •   Due: {return_date}"
            ctk.CTkLabel(
                info_frame,
                text=details,
                font=(FONT_FAMILY, 14),
                text_color=TEXT_SUB,
                anchor="w",
            ).pack(fill="x", pady=(5, 0))

            # Middle: Status Badge
            badge_frame = ctk.CTkFrame(card, fg_color="transparent")
            badge_frame.pack(side="left", padx=20)

            status_badge = ctk.CTkFrame(
                badge_frame, fg_color=status_color, corner_radius=12
            )
            status_badge.pack(anchor="center")
            ctk.CTkLabel(
                status_badge,
                text=status_text.upper(),
                font=(FONT_FAMILY, 12, "bold"),
                text_color="white",
            ).pack(padx=16, pady=6)

            # Right: Fine Amount & Action
            amount_frame = ctk.CTkFrame(card, fg_color="transparent")
            amount_frame.pack(side="right", padx=20)

            ctk.CTkLabel(
                amount_frame,
                text=f"₱ {total_book_fine}",
                font=(FONT_FAMILY, 28, "bold"),
                text_color=DANGER if total_book_fine > 0 else SUCCESS,
            ).pack(side="left", padx=25)

            if total_book_fine > 0 and status_text == "Unpaid":

                def make_pay_command(
                    r_id=record_id,
                    title=book_title,
                    fine_amt=total_book_fine,
                    borrow_dt=borrow_date,
                    due_dt=return_date,
                ):
                    def cmd():
                        pay_win = ctk.CTkToplevel(app)
                        pay_win.title("Fine Payment Instructions")
                        pay_win.geometry("500x350")
                        pay_win.attributes("-topmost", True)
                        pay_win.transient(app)

                        pay_win.update_idletasks()
                        x = (pay_win.winfo_screenwidth() - 500) // 2
                        y = (pay_win.winfo_screenheight() - 350) // 2
                        pay_win.geometry(f"+{x}+{y}")

                        ctk.CTkLabel(
                            pay_win,
                            text="Fine Payment Window",
                            font=(FONT_FAMILY, 20, "bold"),
                            text_color=BRAND,
                        ).pack(pady=(20, 10))

                        instruction_text = (
                            "1. Click the button below to generate a Payment Receipt.\n"
                            "2. Present this receipt to the cashier to pay your fine (make sure to print or take a picture of the receipt).\n"
                            "3. After paying, you must bring the book (if applicable) along with the official receipt given to you by the cashier to the librarian."
                        )
                        ctk.CTkLabel(
                            pay_win,
                            text=instruction_text,
                            font=(FONT_FAMILY, 14),
                            text_color=TEXT_MAIN,
                            justify="left",
                            wraplength=450,
                        ).pack(padx=20, pady=20)

                        def process_payment():
                            import uuid
                            from utils import qr_borrow

                            user_info = student_db.get_current_user_info(
                                logged_in_email
                            )

                            txn_dict = {
                                "transaction_id": f"PAY-{uuid.uuid4().hex[:5].upper()}",
                                "user_id": user_info.get("student_id", "N/A"),
                                "user_name": user_info.get("name", "N/A"),
                                "book_title": title,
                                "borrow_date": borrow_dt,
                                "due_date": due_dt,
                                "fine_amount": f"{fine_amt:.2f}",
                            }

                            student_db.request_fine_payment(r_id)

                            if hasattr(qr_borrow, "print_fine_payment_receipt"):
                                qr_borrow.print_fine_payment_receipt(
                                    txn_dict, parent=pay_win
                                )
                            else:
                                qr_borrow.print_receipt(txn_dict, parent=pay_win)

                            pay_win.destroy()
                            app.destroy()
                            open_screen(parent, logged_in_email)

                        ctk.CTkButton(
                            pay_win,
                            text="Generate Receipt",
                            font=(FONT_FAMILY, 14, "bold"),
                            fg_color=BRAND,
                            hover_color=BRAND_HOVER,
                            command=process_payment,
                            height=40,
                        ).pack(pady=10)

                    return cmd

                pay_btn = ctk.CTkButton(
                    amount_frame,
                    text="Pay Fine",
                    font=(FONT_FAMILY, 14, "bold"),
                    fg_color=BRAND,
                    hover_color=BRAND_HOVER,
                    corner_radius=12,
                    width=140,
                    height=40,
                    command=make_pay_command(),
                )
                pay_btn.pack(side="left")

    return app


if __name__ == "__main__":
    import sys
    import os

    # Add the root directory to sys.path to allow importing utils
    sys.path.append(
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    )

    # Initialize a dummy root window
    root = ctk.CTk()
    root.withdraw()  # Hide the root window since open_screen creates a Toplevel
    # Provide a dummy logged_in_email for testing
    app = open_screen(root, "test@student.com")
    root.mainloop()
