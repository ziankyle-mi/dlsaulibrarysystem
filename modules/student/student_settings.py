import customtkinter as ctk
import tkinter as tk
import os
import shutil
from tkinter import filedialog
from PIL import Image, ImageTk, ImageOps, ImageDraw
from utils import student_db
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
ACCENT = "#10B981"
FONT_FAMILY = "Segoe UI"

def draw_shadow(canvas, x1, y1, x2, y2, radius=20, offset_y=10, blur=15):
    # simple faux shadow using layered rounded rectangles
    for i in range(blur):
        alpha = int(20 * (1 - (i/blur)))
        color = f"#{240-alpha:02x}{240-alpha:02x}{240-alpha:02x}"
        offset = i
        canvas.create_oval(x1-offset, y1-offset+offset_y, x1+radius*2+offset, y1+radius*2+offset_y, fill=color, outline="")
        canvas.create_oval(x2-radius*2-offset, y1-offset+offset_y, x2+offset, y1+radius*2+offset_y, fill=color, outline="")
        canvas.create_oval(x1-offset, y2-radius*2-offset+offset_y, x1+radius*2+offset, y2+offset+offset_y, fill=color, outline="")
        canvas.create_oval(x2-radius*2-offset, y2-radius*2-offset+offset_y, x2+offset, y2+offset+offset_y, fill=color, outline="")
        canvas.create_rectangle(x1+radius, y1-offset+offset_y, x2-radius, y2+offset+offset_y, fill=color, outline="")
        canvas.create_rectangle(x1-offset, y1+radius+offset_y, x2+offset, y2-radius+offset_y, fill=color, outline="")

def open_screen(parent, logged_in_email):
    app = ctk.CTkToplevel(parent)
    app.attributes("-fullscreen", True)
    app.configure(fg_color=PAGE_BG)
    app.title("Account Settings")
    
    def safe_destroy(event=None):
        app.withdraw()
        app.destroy()
        
    app.bind("<Escape>", safe_destroy)
    
    SCREEN_W = app.winfo_screenwidth()
    SCREEN_H = app.winfo_screenheight()
    
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
    
    # Main Content Center
    content = ctk.CTkFrame(app, fg_color="transparent")
    content.place(relx=0.5, rely=0.5, anchor="center")
    
    user_info = student_db.get_current_user_info(logged_in_email)
    
    card = ctk.CTkFrame(content, fg_color=CARD_BG, corner_radius=24, width=450, height=640)
    card.pack()
    card.pack_propagate(False)
    
    # Avatar
    avatar_canvas = tk.Canvas(card, width=160, height=160, bg=CARD_BG, highlightthickness=0)
    avatar_canvas.pack(pady=(40, 20))
    
    app.avatar_photo = None
    
    def make_circular_image(path, size=140):
        img = Image.open(path).convert("RGBA")
        img = ImageOps.fit(img, (size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)
        
        ring = Image.new("RGBA", (size, size), (0,0,0,0))
        ImageDraw.Draw(ring).ellipse((2, 2, size-2, size-2), outline=(16, 49, 43, 255), width=4)
        out = Image.alpha_composite(img, ring)
        return ImageTk.PhotoImage(out)

    def render_avatar():
        avatar_canvas.delete("all")
        pic_path = user_info.get('profile_picture')
        loaded = False
        sz = 140
        if pic_path and os.path.exists(pic_path):
            try:
                photo = make_circular_image(pic_path, sz)
                app.avatar_photo = photo
                avatar_canvas.create_image(80, 80, image=photo)
                loaded = True
            except Exception:
                pass
        if not loaded:
            initials = "".join([p[0].upper() for p in user_info['name'].split()[:2]]) if user_info['name'] != "User" else "U"
            avatar_canvas.create_oval(10, 10, sz+10, sz+10, fill=BRAND, outline="")
            avatar_canvas.create_text(80, 80, text=initials, fill="white", font=(FONT_FAMILY, 40, "bold"))
            
    render_avatar()
    
    ctk.CTkLabel(card, text=user_info['name'], font=(FONT_FAMILY, 28, "bold"), text_color=TEXT_MAIN).pack()
    ctk.CTkLabel(card, text=f"Student ID: {user_info.get('student_id', 'N/A')}", font=(FONT_FAMILY, 14), text_color=TEXT_SUB).pack(pady=(5, 0))
    ctk.CTkLabel(card, text=f"Program: {user_info.get('course', 'N/A')}", font=(FONT_FAMILY, 14), text_color=TEXT_SUB).pack(pady=(2, 30))
    
    def change_profile_picture():
        file_path = filedialog.askopenfilename(
            title="Select Profile Picture",
            filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")]
        )
        if not file_path:
            return
        try:
            os.makedirs(student_db.PROFILE_PICS_DIR, exist_ok=True)
            ext = os.path.splitext(file_path)[1]
            safe_name = logged_in_email.replace('@', '_at_').replace('.', '_')
            dest_path = os.path.join(student_db.PROFILE_PICS_DIR, f"{safe_name}{ext}")
            shutil.copy(file_path, dest_path)
            student_db.set_profile_picture_path(logged_in_email, dest_path)
            user_info['profile_picture'] = dest_path
            render_avatar()
            messagebox.showinfo("Success", "Profile picture updated successfully!")
        except Exception as e:
            messagebox.showerror("Upload Error", f"Could not set profile picture: {e}")
            
    def change_password():
        modal = ctk.CTkToplevel(app)
        modal.title("Change Password")
        modal.configure(fg_color=CARD_BG)
        modal.transient(app)
        modal.grab_set()
        
        # Center modal
        modal.update_idletasks()
        w = 400
        h = 420
        x = (SCREEN_W // 2) - (w // 2)
        y = (SCREEN_H // 2) - (h // 2)
        modal.geometry(f"{w}x{h}+{x}+{y}")
        
        ctk.CTkLabel(modal, text="Secure Your Account", font=(FONT_FAMILY, 22, "bold"), text_color=BRAND).pack(pady=(30, 20))
        
        current_entry = ctk.CTkEntry(modal, font=(FONT_FAMILY, 14), show="*", placeholder_text="Current Password", width=320, height=45, corner_radius=10, border_width=1, border_color="#D1D5DB", text_color="#111827")
        current_entry.pack(pady=10)
        new_entry = ctk.CTkEntry(modal, font=(FONT_FAMILY, 14), show="*", placeholder_text="New Password", width=320, height=45, corner_radius=10, border_width=1, border_color="#D1D5DB", text_color="#111827")
        new_entry.pack(pady=10)
        confirm_entry = ctk.CTkEntry(modal, font=(FONT_FAMILY, 14), show="*", placeholder_text="Confirm New Password", width=320, height=45, corner_radius=10, border_width=1, border_color="#D1D5DB", text_color="#111827")
        confirm_entry.pack(pady=10)
        
        def submit():
            current = current_entry.get()
            new_pw = new_entry.get()
            confirm_pw = confirm_entry.get()
            if not current or not new_pw or not confirm_pw:
                messagebox.showwarning("Missing Information", "Please fill in all fields.")
                return
            if not student_db.verify_current_password(logged_in_email, current):
                messagebox.showerror("Error", "Incorrect current password.")
                return
            if new_pw != confirm_pw:
                messagebox.showerror("Error", "Passwords do not match.")
                return
            if len(new_pw) < 6:
                messagebox.showwarning("Too Short", "Password must be at least 6 characters.")
                return
            if student_db.update_password(logged_in_email, new_pw):
                messagebox.showinfo("Success", "Password changed successfully!")
                modal.destroy()
            else:
                messagebox.showerror("Error", "Failed to update password.")
                
        ctk.CTkButton(modal, text="Update Password", command=submit, fg_color=BRAND, hover_color=BRAND_HOVER, font=(FONT_FAMILY, 14, "bold"), width=320, height=45, corner_radius=10).pack(pady=(30, 10))
        ctk.CTkButton(modal, text="Cancel", command=modal.destroy, fg_color="transparent", text_color=TEXT_SUB, hover_color="#F3F4F6", width=320, height=40).pack()
    
    def remove_profile_picture():
        if not user_info.get('profile_picture'):
            messagebox.showinfo("Info", "No profile picture is currently set.")
            return
        if messagebox.askyesno("Remove Profile Picture", "Are you sure you want to remove your profile picture?"):
            try:
                old_path = user_info.get('profile_picture')
                student_db.set_profile_picture_path(logged_in_email, None)
                user_info['profile_picture'] = None
                if old_path and os.path.exists(old_path):
                    try:
                        os.remove(old_path)
                    except Exception:
                        pass
                render_avatar()
                messagebox.showinfo("Success", "Profile picture removed successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Could not remove profile picture: {e}")

    ctk.CTkButton(card, text="Update Profile Picture", command=change_profile_picture, font=(FONT_FAMILY, 14, "bold"), fg_color=BRAND, hover_color=BRAND_HOVER, width=320, height=45, corner_radius=12).pack(pady=(10, 5))
    ctk.CTkButton(card, text="Remove Profile Picture", command=remove_profile_picture, font=(FONT_FAMILY, 14, "bold"), fg_color="#DC2626", hover_color="#B91C1C", text_color="white", width=320, height=45, corner_radius=12).pack(pady=5)
    ctk.CTkButton(card, text="Change Password", command=change_password, font=(FONT_FAMILY, 14, "bold"), fg_color="#F1F5F9", text_color=BRAND, hover_color="#E2E8F0", width=320, height=45, corner_radius=12).pack(pady=5)
    

    
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

