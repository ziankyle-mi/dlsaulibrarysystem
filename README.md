# DLSAU Library System

A comprehensive library management system built with Python and CustomTkinter, designed for students and administrators.

## Features
- **Authentication**: Secure login system with role-based access for Students and Admins.
- **Student Dashboard**: Browse books, manage borrowed items, and view fines or reading history.
- **Admin Dashboard**: Manage inventory, process borrow requests, and handle fine payments.
- **Cross-Platform**: Works on Windows, macOS, and Linux with responsive and modern UI.

## Tech Stack
- **Language**: Python 3.10+
- **GUI Framework**: CustomTkinter & Tkinter (for the modern, graphical user interface)
- **Database**: SQLite 3 (lightweight, serverless relational database for storing users, books, and transactions)

## Quick Start

### Requirements
- Python 3.10+

### Windows
```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python login.py
```

### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python login.py
```

*(Note: On Linux, you may need to install tkinter via `sudo apt-get install python3-tk` before running the app.)*
