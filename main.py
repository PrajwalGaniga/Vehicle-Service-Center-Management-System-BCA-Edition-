import sqlite3
import os
from flask import Flask, redirect, url_for
from customer import customer_bp
from admin import admin_bp

app = Flask(__name__)
app.secret_key = "autofix_pro_secret_key_2024"

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def init_db():
    """Automatically creates database.db and all required tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT    NOT NULL,
            phone    TEXT    NOT NULL UNIQUE,
            password TEXT    NOT NULL
        )
    """)

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

    conn.commit()
    conn.close()
    print("[AutoFix Pro] Database initialized successfully.")


# Register blueprints
app.register_blueprint(customer_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")


@app.route("/")
def index():
    return redirect(url_for("customer.login"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
