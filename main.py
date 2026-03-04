import sqlite3
import os
import sys
import subprocess
import threading
import time
from flask import Flask, redirect, url_for
from customer import customer_bp
from admin import admin_bp
from mechanic import mechanic_bp

app = Flask(__name__)
app.secret_key = "motoserv_centre_secret_key_2026"

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def init_db():
    """Zero-setup: Creates DB + tables on first run. Safe migrations for existing DBs."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ── CUSTOMERS ─────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            phone    TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL
        )
    """)
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN email TEXT DEFAULT ''")
        print("[MotoServ Centre] Migration: added 'email' to customers.")
    except Exception:
        pass

    # ── MECHANICS ─────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mechanics (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            name              TEXT    NOT NULL,
            phone             TEXT    NOT NULL UNIQUE,
            experience_years  INTEGER NOT NULL DEFAULT 0,
            specialization    TEXT    NOT NULL DEFAULT 'General',
            status            TEXT    NOT NULL DEFAULT 'Active'
        )
    """)

    # ── BOOKINGS ──────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id      TEXT    NOT NULL UNIQUE,
            customer_id    INTEGER NOT NULL,
            vehicle_name   TEXT    NOT NULL,
            vehicle_type   TEXT    NOT NULL,
            vehicle_number TEXT    NOT NULL,
            model          TEXT    NOT NULL,
            body_type      TEXT    NOT NULL,
            model_year     TEXT    NOT NULL,
            problem        TEXT    NOT NULL,
            status         TEXT    NOT NULL DEFAULT 'Pending',
            preferred_date TEXT    NOT NULL,
            created_at     TEXT    NOT NULL,
            updated_at     TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)
    # Safe migrations for bookings
    for col, definition in [
        ("payment_method", "TEXT DEFAULT ''"),
        ("mechanic_id",    "INTEGER REFERENCES mechanics(id)"),
        ("work_status",    "TEXT DEFAULT ''"),
    ]:
        try:
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col} {definition}")
            print(f"[MotoServ Centre] Migration: added '{col}' to bookings.")
        except Exception:
            pass

    # ── BILLS ─────────────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bills (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id     INTEGER NOT NULL UNIQUE,
            spare_parts    REAL    NOT NULL DEFAULT 0,
            labor_charge   REAL    NOT NULL DEFAULT 0,
            service_charge REAL    NOT NULL DEFAULT 0,
            tax            REAL    NOT NULL DEFAULT 0,
            total_amount   REAL    NOT NULL DEFAULT 0,
            FOREIGN KEY (booking_id) REFERENCES bookings(id)
        )
    """)

    # ── NOTIFICATIONS ─────────────────────────────────────────────────────────
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            message     TEXT    NOT NULL,
            is_read     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # ── SEED MECHANICS (only if table is empty) ───────────────────────────────
    count = cursor.execute("SELECT COUNT(*) FROM mechanics").fetchone()[0]
    if count == 0:
        cursor.executemany(
            "INSERT INTO mechanics (name, phone, experience_years, specialization, status) VALUES (?,?,?,?,?)",
            [
                ("Rajesh Kumar",   "9876543210", 8, "Engine & Transmission", "Active"),
                ("Suresh Sharma",  "9123456789", 5, "Electrical & AC",       "Active"),
                ("Priya Patel",    "9988776655", 6, "Body & Paint",          "Active"),
            ]
        )
        print("[MotoServ Centre] Seeded 3 mechanics: Rajesh Kumar, Suresh Sharma, Priya Patel.")

    # Enable WAL mode for concurrent read/write without locking
    conn.execute("PRAGMA journal_mode=WAL")
    conn.commit()
    conn.close()
    print("[MotoServ Centre] Database initialized successfully.")
    print("[MotoServ Centre] Admin credentials → Username: Admin | Password: 12345")
    print("[MotoServ Centre] Mechanic login    → Use mechanic phone number (e.g. 9876543210)")


def start_ngrok(port=5000):
    """Start Ngrok tunnel and print the public URL."""
    ngrok_exe = os.path.join(os.path.dirname(__file__), "ngrok.exe")
    if not os.path.exists(ngrok_exe):
        print("[MotoServ Centre] ngrok.exe not found in project folder. Skipping Ngrok tunnel.")
        return

    def run_ngrok():
        try:
            # Start ngrok process
            proc = subprocess.Popen(
                [ngrok_exe, "http", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            time.sleep(2)  # Wait for ngrok to start
            # Query the local ngrok API to get the public URL
            import urllib.request
            import json
            try:
                with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels") as resp:
                    data = json.loads(resp.read().decode())
                    tunnels = data.get("tunnels", [])
                    for t in tunnels:
                        if t.get("proto") == "https":
                            url = t["public_url"]
                            print(f"\n{'='*60}")
                            print(f"  🌐  MotoServ Centre — Public URL (Ngrok):")
                            print(f"      {url}")
                            print(f"{'='*60}\n")
                            return
                    print("[MotoServ Centre] Ngrok is running. Visit http://127.0.0.1:4040 for URL.")
            except Exception:
                print("[MotoServ Centre] Ngrok started. Visit http://127.0.0.1:4040 to get the public URL.")
        except Exception as e:
            print(f"[MotoServ Centre] Could not start Ngrok: {e}")

    t = threading.Thread(target=run_ngrok, daemon=True)
    t.start()


# Register blueprints
app.register_blueprint(customer_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")
app.register_blueprint(mechanic_bp, url_prefix="/mechanic")


@app.route("/")
def index():
    return redirect(url_for("customer.login"))


if __name__ == "__main__":
    PORT = 5000
    init_db()
    # Start Ngrok tunnel in background (if ngrok.exe present)
    start_ngrok(PORT)
    print(f"\n[MotoServ Centre] Running on http://127.0.0.1:{PORT}")
    print("[MotoServ Centre] Press Ctrl+C to stop.\n")
    app.run(debug=True, port=PORT, use_reloader=False)
