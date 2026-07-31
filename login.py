import os
import sys
import subprocess
import ctypes
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sqlite3
import random
import string
from tkinter import Canvas
import customtkinter as ctk
from utils import sweetalert as messagebox
from PIL import Image, ImageTk, ImageFilter

from utils import theme
from utils.db_manager import (
    verify_login,
    hash_password_db as hash_password,
    get_email_for_user,
    update_password_direct,
)

ctk.set_appearance_mode("Light")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "database", "login_system.db")
SESSION_FILE = os.path.join(BASE_DIR, "database", ".session")

PRIMARY = theme.PRIMARY
PRIMARY_HOVER = theme.PRIMARY_HOVER
WHITE = theme.WHITE
BLACK = theme.BLACK
LIGHT_BG = theme.LIGHT_BG
TEXT_GRAY = theme.TEXT_GRAY

LOGO_FONT = theme.LOGO_FONT
LABEL_FONT = ("Segoe UI", 12, "bold")
ENTRY_FONT = ("Segoe UI", 12)
BUTTON_FONT = ("Segoe UI", 16, "bold")

BACKGROUND_IMAGES = [
    os.path.join(BASE_DIR, "images", "login1pic.png"),
    os.path.join(BASE_DIR, "images", "outside.png"),
    os.path.join(BASE_DIR, "images", "outside3.png"),
    os.path.join(BASE_DIR, "images", "outside2.png"),
    os.path.join(BASE_DIR, "images", "forest.png"),
]

# --- SENDER EMAIL CONFIGURATION ---
# Replace these with a real Gmail account and App Password for testing!
SENDER_EMAIL = "aranetalibrarysystem@gmail.com"
SENDER_PASSWORD = "ezjw bfxt wajs jsmc"


def send_otp_email(recipient_email, otp_code):
    try:
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = recipient_email
        msg["Subject"] = "Your Password Reset OTP"

        body = f"Hello,\n\nYour 6-digit verification code is: {otp_code}\n\nDo not share this code with anyone."
        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        text = msg.as_string()
        server.sendmail(SENDER_EMAIL, recipient_email, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


class LoginApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.attributes("-fullscreen", True)
        # Force window to the top on launch to prevent it from loading in the background
        self.attributes("-topmost", True)
        self.focus_force()
        self.after(500, lambda: self.attributes("-topmost", False))

        self.title("ALIW Library System - Login")
        self.bind("<Escape>", lambda e: theme.exit_program(self))

        self.screen_w = self.winfo_screenwidth()
        self.screen_h = self.winfo_screenheight()

        self.card_cx = self.screen_w / 2
        self.card_cy = self.screen_h / 2

        self.bg_index = 0
        self.lockout = {"count": 0, "locked_until": None}

        self.canvas = Canvas(
            self, width=self.screen_w, height=self.screen_h, bd=0, highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        theme.enable_responsive_resize(self, self.canvas)

        # Start Splash Screen
        self.draw_splash_screen()

        # Simulate loading heavy assets/database (since we removed Excel it is much faster)
        self.after(1500, self.finish_loading)

    def draw_splash_screen(self):
        self.canvas.create_rectangle(
            0, 0, self.screen_w, self.screen_h, fill=WHITE, outline="", tags="splash"
        )

        try:
            logo = Image.open(os.path.join(BASE_DIR, "images", "dlsaulogos1.png"))
            logo = logo.resize((400, 60), Image.Resampling.LANCZOS)
            self.splash_logo = ImageTk.PhotoImage(logo)
            self.canvas.create_image(
                self.screen_w / 2,
                self.screen_h / 2 - 20,
                image=self.splash_logo,
                anchor="center",
                tags="splash",
            )
        except Exception:
            self.canvas.create_text(
                self.screen_w / 2,
                self.screen_h / 2 - 20,
                text="ALIW LIBRARY SYSTEM",
                font=("Segoe UI", 30, "bold"),
                fill=PRIMARY,
                tags="splash",
            )

        self.canvas.create_text(
            self.screen_w / 2,
            self.screen_h / 2 + 50,
            text="Loading modules...",
            font=("Segoe UI", 12),
            fill=TEXT_GRAY,
            tags="splash",
        )

    def finish_loading(self):
        self.canvas.delete("splash")
        self.attributes("-alpha", 0.0)  # For fade in
        self.draw_background()
        self.draw_header()
        self.draw_login_card()
        self.draw_exit_button()
        self.fade_in()

    def fade_in(self, alpha=0.0):
        alpha += 0.05
        if alpha < 1.0:
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self.fade_in(alpha))
        else:
            self.attributes("-alpha", 1.0)

    def draw_background(self):
        try:
            bg = Image.open(BACKGROUND_IMAGES[self.bg_index]).convert("RGBA")
            bg = bg.filter(ImageFilter.GaussianBlur(radius=6))
            bg = bg.resize((self.screen_w, self.screen_h), Image.Resampling.LANCZOS)

            # Create a true semi-transparent black overlay using PIL instead of ugly stipple
            overlay = Image.new("RGBA", bg.size, (0, 0, 0, 140))
            blended_bg = Image.alpha_composite(bg, overlay)

            self.bg_photo = ImageTk.PhotoImage(blended_bg)

            self.canvas.delete("bg")
            self.canvas.create_image(0, 0, image=self.bg_photo, anchor="nw", tags="bg")
            self.canvas.tag_lower("bg")
        except Exception:
            self.canvas.create_rectangle(
                0, 0, self.screen_w, self.screen_h, fill="#F4F6F6", tags="bg"
            )
            self.canvas.tag_lower("bg")

        self.bg_index = (self.bg_index + 1) % len(BACKGROUND_IMAGES)
        if len(BACKGROUND_IMAGES) > 1:
            self.after(10000, self.draw_background)

    def draw_header(self):
        self.canvas.create_rectangle(0, 0, self.screen_w, 80, fill=PRIMARY, outline="")
        try:
            logo = Image.open(os.path.join(BASE_DIR, "images", "dlsaulogos1.png"))
            logo = logo.resize((340, 50), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo)
            self.canvas.create_image(30, 40, image=self.logo_photo, anchor="w")
        except:
            pass

    def draw_exit_button(self):
        exit_btn = ctk.CTkButton(
            self,
            text="✕",
            font=("Segoe UI", 20, "bold"),
            width=40,
            height=40,
            corner_radius=8,
            fg_color=PRIMARY,
            text_color=WHITE,
            hover_color="#E81123",
            command=lambda: theme.exit_program(self),
        )
        self.canvas.create_window(self.screen_w - 20, 40, window=exit_btn, anchor="e")

    def draw_login_card(self):
        card_w, card_h = 420, 620
        corner_radius = 25
        shadow_pad = 20

        try:
            from PIL import ImageDraw

            img_size = (card_w + shadow_pad * 2, card_h + shadow_pad * 2)
            card_img = Image.new("RGBA", img_size, (0, 0, 0, 0))

            draw = ImageDraw.Draw(card_img)
            draw.rounded_rectangle(
                (shadow_pad, shadow_pad, shadow_pad + card_w, shadow_pad + card_h),
                radius=corner_radius,
                fill=(0, 0, 0, 50),
            )
            card_img = card_img.filter(ImageFilter.GaussianBlur(radius=12))

            draw = ImageDraw.Draw(card_img)
            draw.rounded_rectangle(
                (shadow_pad, shadow_pad, shadow_pad + card_w, shadow_pad + card_h),
                radius=corner_radius,
                fill=(255, 255, 255, 235),
            )

            self.card_photo = ImageTk.PhotoImage(card_img)
            self.canvas.create_image(
                self.card_cx, self.card_cy, image=self.card_photo, anchor="center"
            )
        except:
            self.canvas.create_rectangle(
                self.card_cx - card_w / 2,
                self.card_cy - card_h / 2,
                self.card_cx + card_w / 2,
                self.card_cy + card_h / 2,
                fill=WHITE,
                outline="",
            )

        # Profile Picture
        try:
            from PIL import ImageDraw

            profile_img = Image.open(
                os.path.join(BASE_DIR, "images", "profilepic2.png")
            ).convert("RGBA")
            profile_img = profile_img.resize((120, 120), Image.Resampling.LANCZOS)
            mask = Image.new("L", (120, 120), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, 120, 120), fill=255)
            circular_profile = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            circular_profile.paste(profile_img, (0, 0), mask=mask)
            self.profile_photo = ImageTk.PhotoImage(circular_profile)
            self.canvas.create_image(
                self.card_cx,
                self.card_cy - 200,
                image=self.profile_photo,
                anchor="center",
            )
        except:
            pass

        self.canvas.create_text(
            self.card_cx,
            self.card_cy - 110,
            text="Welcome Back",
            font=("Segoe UI", 26, "bold"),
            fill=PRIMARY,
            anchor="center",
        )
        self.canvas.create_text(
            self.card_cx,
            self.card_cy - 75,
            text="Sign in to continue",
            font=("Segoe UI", 12),
            fill="#666666",
            anchor="center",
        )

        input_w, input_h = 340, 50
        left_edge = self.card_cx - (input_w / 2)

        self.canvas.create_text(
            left_edge,
            self.card_cy - 20,
            text="Email",
            font=("Segoe UI", 11, "bold"),
            fill="#444444",
            anchor="sw",
        )
        self.entryuser = ctk.CTkEntry(
            self,
            width=input_w,
            height=input_h,
            font=("Segoe UI", 18),
            fg_color="#F8FAFA",
            text_color="#111111",
            border_color="#D1D8D8",
            border_width=1,
            corner_radius=12,
        )
        self.entryuser_win = self.canvas.create_window(
            self.card_cx, self.card_cy + 10, window=self.entryuser, anchor="center"
        )
        self.entryuser.bind("<Return>", lambda e: self.on_login())
        self.entryuser.bind("<KeyRelease>", self.check_caps_lock)

        self.canvas.create_text(
            left_edge,
            self.card_cy + 85,
            text="Password",
            font=("Segoe UI", 11, "bold"),
            fill="#444444",
            anchor="sw",
        )
        self.entrypass = ctk.CTkEntry(
            self,
            width=input_w,
            height=input_h,
            font=("Segoe UI", 18),
            fg_color="#F8FAFA",
            text_color="#111111",
            border_color="#D1D8D8",
            border_width=1,
            corner_radius=12,
            show="•",
        )
        self.entrypass_win = self.canvas.create_window(
            self.card_cx, self.card_cy + 115, window=self.entrypass, anchor="center"
        )
        self.entrypass.bind("<Return>", lambda e: self.on_login())
        self.entrypass.bind("<KeyRelease>", self.check_caps_lock)

        self.canvas.create_text(
            left_edge,
            self.card_cy + 155,
            text="⚠️ Caps Lock is ON",
            font=("Segoe UI", 10, "bold"),
            fill="red",
            anchor="sw",
            tags="caps_warning",
            state="hidden",
        )

        self.toggle_btn = ctk.CTkButton(
            self,
            text="👁",
            width=50,
            height=35,
            fg_color="#F8FAFA",
            text_color="#444444",
            hover_color="#E8EBEB",
            font=("Segoe UI", 18),
            corner_radius=8,
            command=self.toggle_password,
        )
        self.canvas.create_window(
            self.card_cx + (input_w / 2) - 35,
            self.card_cy + 115,
            window=self.toggle_btn,
            anchor="center",
        )

        login_btn = ctk.CTkButton(
            self,
            text="SIGN IN",
            font=("Segoe UI", 15, "bold"),
            width=input_w,
            height=55,
            fg_color=PRIMARY,
            text_color=WHITE,
            hover_color=PRIMARY_HOVER,
            corner_radius=12,
            command=self.on_login,
        )
        self.canvas.create_window(
            self.card_cx, self.card_cy + 205, window=login_btn, anchor="center"
        )

        forgot_text_id = self.canvas.create_text(
            self.card_cx,
            self.card_cy + 250,
            text="Forgot your password?",
            font=("Segoe UI", 11, "bold", "underline"),
            fill=PRIMARY,
            anchor="center",
        )
        self.canvas.tag_bind(
            forgot_text_id, "<Button-1>", lambda e: self.open_forgot_password_dialog()
        )
        self.canvas.tag_bind(
            forgot_text_id,
            "<Enter>",
            lambda e: self.canvas.itemconfigure(forgot_text_id, fill=PRIMARY_HOVER),
        )
        self.canvas.tag_bind(
            forgot_text_id,
            "<Leave>",
            lambda e: self.canvas.itemconfigure(forgot_text_id, fill=PRIMARY),
        )

        self.entryuser.focus_set()

        # Help text positioned at the bottom left of the screen, away from the login card
        help_text_id = self.canvas.create_text(
            20,
            self.screen_h - 20,
            text="Don't have an account? Help",
            font=("Segoe UI", 10, "underline"),
            fill="#FFFFFF",
            anchor="sw",
        )
        self.canvas.tag_bind(
            help_text_id,
            "<Button-1>",
            lambda e: messagebox.showinfo(
                "Account Registration",
                "Please proceed to the librarian's desk and submit your Student ID to register for a new account.",
            ),
        )
        self.canvas.tag_bind(
            help_text_id,
            "<Enter>",
            lambda e: self.canvas.itemconfigure(help_text_id, fill="#DDDDDD"),
        )
        self.canvas.tag_bind(
            help_text_id,
            "<Leave>",
            lambda e: self.canvas.itemconfigure(help_text_id, fill="#FFFFFF"),
        )

    def toggle_password(self):
        if self.entrypass.cget("show") == "•":
            self.entrypass.configure(show="")
            self.toggle_btn.configure(text="🙈")
        else:
            self.entrypass.configure(show="•")
            self.toggle_btn.configure(text="👁")

    def check_caps_lock(self, event=None):
        self.entryuser.configure(border_color="#D1D8D8", border_width=1)
        self.entrypass.configure(border_color="#D1D8D8", border_width=1)
        if ctypes.windll.user32.GetKeyState(0x14) & 1:
            self.canvas.itemconfigure("caps_warning", state="normal")
        else:
            self.canvas.itemconfigure("caps_warning", state="hidden")

    def shake_canvas_window(self, window_id, count=0):
        if count < 8:
            offset = 8 if count % 2 == 0 else -8
            self.canvas.move(window_id, offset, 0)
            self.after(30, lambda: self.shake_canvas_window(window_id, count + 1))

    def verify_password(self, raw_password, salt, expected_hash):
        import secrets

        if not salt or not expected_hash:
            return False
        _, digest = hash_password(raw_password, salt)
        return secrets.compare_digest(digest, expected_hash)

    def on_login(self):
        username = self.entryuser.get().strip()
        password = self.entrypass.get().strip()

        if not username or not password:
            messagebox.showwarning("Error", "Please fill out all fields.")
            return

        import time

        if self.lockout["locked_until"]:
            remaining = int(self.lockout["locked_until"] - time.time())
            if remaining > 0:
                messagebox.showerror(
                    "Locked Out",
                    f"Too many failed attempts. Try again in {remaining} seconds.",
                )
                return
            else:
                self.lockout["locked_until"] = None
                self.lockout["count"] = 0

        try:
            admin_row, regular_row = verify_login(username)
            is_valid = False
            user_role = ""

            if admin_row:
                if admin_row[2] == "Suspended":
                    messagebox.showwarning(
                        "Account Suspended", "Your account has been suspended."
                    )
                    return
                if self.verify_password(password, admin_row[1], admin_row[0]):
                    is_valid = True
                    user_role = "admin"
            elif regular_row:
                if regular_row[2] == "Suspended":
                    messagebox.showwarning(
                        "Account Suspended", "Your account has been suspended."
                    )
                    return
                if self.verify_password(password, regular_row[1], regular_row[0]):
                    is_valid = True
                    user_role = "regular"

            if is_valid:
                # ---------------------------------------------------------
                # SUCCESSFUL LOGIN HANDLING
                # ---------------------------------------------------------
                # If the password matched, reset the lockout counter
                self.lockout["count"] = 0
                self.lockout["locked_until"] = None

                try:
                    # Save the logged-in email to a session file so the dashboard knows who is logged in
                    with open(SESSION_FILE, "w", encoding="utf-8") as f:
                        f.write(username)
                except Exception:
                    pass

                # Function to actually launch the new screen based on their role
                def launch_dashboard():
                    self.destroy()  # Close the login screen
                    if user_role == "admin":
                        # Open the Librarian (Admin) Dashboard
                        subprocess.Popen(
                            [sys.executable, os.path.join(BASE_DIR, "maindashboard.py")]
                        )
                    else:
                        # Open the Student Dashboard
                        subprocess.Popen(
                            [
                                sys.executable,
                                os.path.join(BASE_DIR, "regulardashboard.py"),
                            ]
                        )

                # Perform a smooth fade-out animation before launching the dashboard
                theme.fade_out(self, launch_dashboard)
            else:
                # ---------------------------------------------------------
                # FAILED LOGIN HANDLING
                # ---------------------------------------------------------
                # If the password was wrong, increase the strike count
                self.lockout["count"] += 1
                if self.lockout["count"] >= 5:
                    # Lock them out for 30 seconds if they fail 5 times
                    self.lockout["locked_until"] = time.time() + 30
                    self.lockout["count"] = 0

                # Make the input boxes red and physically shake the screen to show an error
                self.entryuser.configure(border_color="red", border_width=2)
                self.entrypass.configure(border_color="red", border_width=2)
                self.shake_canvas_window(self.entryuser_win)
                self.shake_canvas_window(self.entrypass_win)

        except Exception as e:
            # Show a popup error if the database crashed or something unexpected happened
            messagebox.showerror("Error", f"An error occurred: {e}")

    def open_forgot_password_dialog(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Forgot Password")
        popup.geometry("500x380")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()

        x = self.winfo_rootx() + (self.winfo_width() - 500) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 380) // 2
        popup.geometry(f"+{max(0, x)}+{max(0, y)}")

        frame = ctk.CTkFrame(popup, fg_color=WHITE, corner_radius=15)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        title_label = ctk.CTkLabel(
            frame,
            text="Reset Password",
            font=("Segoe UI", 22, "bold"),
            text_color=PRIMARY,
        )
        title_label.pack(anchor="w", pady=(10, 5), padx=20)

        desc_label = ctk.CTkLabel(
            frame,
            text="Enter your Username or Email. A verification code will be sent to your registered email address.",
            font=("Segoe UI", 12),
            text_color=TEXT_GRAY,
            justify="left",
            wraplength=400,
        )
        desc_label.pack(anchor="w", pady=(0, 20), padx=20)

        # State Variables
        self.reset_step = 1
        self.generated_otp = None
        self.reset_identifier = None

        input_entry = ctk.CTkEntry(
            frame,
            placeholder_text="Username or Email",
            font=ENTRY_FONT,
            width=400,
            height=40,
        )
        input_entry.pack(pady=(0, 15))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=30, pady=(10, 0))

        def handle_next():
            if self.reset_step == 1:
                ident = input_entry.get().strip()
                if not ident:
                    messagebox.showwarning(
                        "Error", "Please enter your username or email."
                    )
                    return

                # Fetch email from DB
                email, role = get_email_for_user(ident, DB_FILE)
                if not email:
                    messagebox.showerror("Error", "Account not found.")
                    return

                # Generate OTP
                self.generated_otp = "".join(random.choices(string.digits, k=6))
                self.reset_identifier = ident

                print(
                    f"[DEBUG] Generated OTP for {email}: {self.generated_otp}"
                )  # For testing if email fails

                action_btn.configure(state="disabled", text="Sending...")
                popup.update()

                # Send email
                success = send_otp_email(email, self.generated_otp)

                if success or "YOUR_SENDER" in SENDER_EMAIL:
                    # If using placeholder, let them proceed using the printed debug OTP for testing
                    desc_label.configure(
                        text=f"A 6-digit code has been sent to {email[:3]}***@{email.split('@')[-1]}. "
                    )
                    input_entry.delete(0, "end")
                    input_entry.configure(placeholder_text="Enter 6-digit OTP", show="")
                    action_btn.configure(text="Verify Code", state="normal")
                    self.reset_step = 2
                else:
                    messagebox.showerror(
                        "Error",
                        "Failed to send OTP email. Please check internet connection or server settings.",
                    )
                    action_btn.configure(state="normal", text="Send Code")

            elif self.reset_step == 2:
                entered_otp = input_entry.get().strip()
                if entered_otp != self.generated_otp:
                    messagebox.showerror("Error", "Invalid verification code.")
                    return

                desc_label.configure(
                    text="Code verified! Please enter your new password below."
                )
                input_entry.delete(0, "end")
                input_entry.configure(placeholder_text="New Password", show="*")
                action_btn.configure(text="Update Password")
                self.reset_step = 3

            elif self.reset_step == 3:
                new_pass = input_entry.get().strip()
                if len(new_pass) < 4:
                    messagebox.showwarning(
                        "Error", "Password must be at least 4 characters."
                    )
                    return

                success, msg = update_password_direct(
                    self.reset_identifier, new_pass, DB_FILE, hash_password
                )
                if success:
                    messagebox.showinfo(
                        "Success", "Your password has been successfully reset!"
                    )
                    popup.destroy()
                else:
                    messagebox.showerror("Error", msg)

        action_btn = ctk.CTkButton(
            btn_frame,
            text="Send Code",
            font=BUTTON_FONT,
            fg_color=PRIMARY,
            hover_color=PRIMARY_HOVER,
            command=handle_next,
        )
        action_btn.pack(side="left", padx=5)

        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            font=BUTTON_FONT,
            fg_color=LIGHT_BG,
            text_color=TEXT_GRAY,
            hover_color="#E8EFEA",
            command=popup.destroy,
        )
        cancel_btn.pack(side="right", padx=5)


app = LoginApp()
app.mainloop()
