====================================================================
DLSAU LIBRARY SYSTEM - SETUP GUIDE
====================================================================

HOW TO RUN THIS (for your friend)
--------------------------------------------------------------------
1. Unzip this folder somewhere on your computer.
2. Make sure Python 3.10+ is installed (check with: python3 --version
   or on Windows: python --version). Get it from python.org if not.
3. Open a terminal INSIDE this folder (the one this README is in)
   and paste the block for your operating system below, then hit
   Enter. It will set everything up and launch the app.

--------------------------------------------------------------------
WINDOWS (PowerShell or CMD)
--------------------------------------------------------------------
python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt && python login.py

--------------------------------------------------------------------
macOS / LINUX (bash/zsh terminal)
--------------------------------------------------------------------
python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && python login.py

--------------------------------------------------------------------
NOTE ON TKINTER
--------------------------------------------------------------------
Tkinter (the GUI toolkit this app uses) ships built-in with Python
on Windows and macOS. On Linux it sometimes needs a separate system
package. If "python login.py" complains about "No module named
tkinter", run this first, then try again:
    sudo apt-get install python3-tk

Next time you just need to reactivate the environment and run it:
  Windows:      venv\Scripts\activate  &&  python login.py
  macOS/Linux:  source venv/bin/activate  &&  python login.py

====================================================================
WHAT WAS FIXED IN THIS PASS (UI / interface pass)
====================================================================

1. ACCIDENTAL INSTANT-QUIT ON ESCAPE (fixed app-wide)
   Every screen used to hard-kill the whole application the moment
   Escape was pressed, or the X button clicked - no confirmation, no
   way back, whatever you were doing was just gone. All screens now
   route through one shared theme.exit_program() that asks
   "Are you sure you want to exit?" before actually closing.

2. SCROLLING WAS WINDOWS-ONLY (About page)
   The About/Credits page only listened for the Windows/macOS mouse
   wheel event. On Linux the scroll wheel did nothing at all. It now
   also listens for the Linux scroll events, so scrolling works on
   all three platforms.

3. BROKEN FONT FALLBACK FOR AVATARS (About page)
   The developer avatar initials (used when a photo is missing) tried
   to load a Windows-only font file by name. On macOS/Linux this
   silently failed and fell back to a tiny, blurry placeholder font.
   It now tries several common system fonts before giving up, so the
   avatars look correct cross-platform.

4. FIXED-SIZE / NON-RESIZABLE WINDOWS
   Every screen force-launched fullscreen with hardcoded pixel
   positions computed once at startup, so if a window manager exited
   fullscreen (or the app ran on a second monitor with a different
   resolution) the whole layout could end up off-center or clipped.
   Login and the About page now support being resized/un-maximized,
   re-centering their content and background instead of staying
   frozen at launch-time dimensions.

5. DUPLICATED COLORS/FONTS ACROSS FILES
   Nearly every screen had its own hand-copied version of the brand
   colors and fonts (PRIMARY = "#10312B" etc. re-typed 8+ times).
   These are now pulled from theme.py in the screens most likely to
   drift (login.py, aboutsection.py), so a future rebrand only needs
   one edit instead of hunting through a dozen files.

6. LEFTOVER DEBUG OUTPUT
   Removed a stray "DEBUG: Input username..." print left in the
   login flow.

====================================================================
KNOWN, NOT-YET-FIXED ITEMS (flagged for later, out of scope for this
UI-focused pass - see earlier code review for the full list)
====================================================================
- Passwords are stored and checked in plain text (no hashing).
- login.py wipes and rebuilds login_system.db from the Excel files on
  every single launch, discarding any changes made directly in the DB.
- reuse.py appears to be an unused leftover screen (nothing else in
  the codebase imports or launches it) - safe to delete if unneeded.
- regulardashboard.py (~1,200 lines) and bookinventory.py (~570
  lines) mix UI drawing and database logic in the same functions;
  worth splitting into separate modules if you keep extending them.
