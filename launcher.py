# ===================== LAUNCHER SCRIPT (PYINSTALLER ENTRY POINT) =====================
"""
This script acts as the main entry point for the compiled .exe file.
Because the application uses `subprocess.Popen([sys.executable, "some_file.py"])` 
to switch between screens, this launcher intercepts those calls when running as an .exe
and imports the requested module directly.
"""

import sys
import os

# -------------------------------------------------------------------------
# HIDDEN IMPORTS
# These imports ensure PyInstaller detects and bundles all required modules
# even if they are imported dynamically or inside functions in the codebase.
# -------------------------------------------------------------------------
if False:  # This block is never executed at runtime, only read by PyInstaller
    import loading
    import login
    import maindashboard
    import regulardashboard
    import aboutsection
    import analytics
    import bookinventory
    import usermanagement
    import studentborrowing
    import finemanagement
    from utils import qr_borrow
    from utils import db_manager
    from utils import theme
    from utils import sweetalert
    from utils import ui_helpers
    from utils import bookimageapi

# -------------------------------------------------------------------------
# ROUTING LOGIC
# -------------------------------------------------------------------------
def main():
    # If the app is running as a bundled .exe (PyInstaller sets sys.frozen = True)ad
    if getattr(sys, 'frozen', False):
        if len(sys.argv) > 1:
            # sys.argv[1] will look something like "c:/.../login.py"
            # because of subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "login.py")])
            target_script = sys.argv[1].lower()
            
            if "login.py" in target_script:
                import login
            elif "maindashboard.py" in target_script:
                import maindashboard
            elif "regulardashboard.py" in target_script:
                import regulardashboard
            elif "loading.py" in target_script:
                import loading
            else:
                print(f"Unknown target requested: {sys.argv[1]}")
        else:
            # If launched directly (no arguments), start at the loading screen
            import loading
            
    else:
        # If running from normal python, default to loading screen 
        # (though this file is primarily meant for the .exe build)
        if len(sys.argv) > 1:
            target_script = sys.argv[1].lower()
            if "login.py" in target_script:
                import login
            elif "maindashboard.py" in target_script:
                import maindashboard
            elif "regulardashboard.py" in target_script:
                import regulardashboard
            else:
                import loading
        else:
            import loading

if __name__ == '__main__':
    main()
