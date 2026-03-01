import sqlite3
import os
import hashlib
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify

customer_bp = Blueprint("customer", __name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "customer_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("customer.login"))
        return f(*args, **kwargs)
    return decorated


def generate_ticket_id():
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) as cnt FROM bookings").fetchone()
    conn.close()
    return f"TICK{1001 + row['cnt']}"


def add_notification(conn, customer_id, message):
    """Insert a notification row for a customer."""
    conn.execute(
        "INSERT INTO notifications (customer_id, message, is_read, created_at) VALUES (?,?,0,?)",
        (customer_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )


# ─── AUTH ────────────────────────────────────────────────────────────────────

@customer_bp.route("/login", methods=["GET", "POST"])
def login():
    if "customer_id" in session:
        return redirect(url_for("customer.dashboard"))
    if request.method == "POST":
        phone    = request.form.get("phone", "").strip()
        password = request.form.get("password", "").strip()
        if not phone or not password:
            flash("All fields are required.", "error")
            return render_template("login.html")
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM customers WHERE phone = ? AND password = ?",
            (phone, hash_password(password))
        ).fetchone()
        conn.close()
        if user:
            session["customer_id"]    = user["id"]
            session["customer_name"]  = user["name"]
            session["customer_phone"] = user["phone"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("customer.dashboard"))
        flash("Invalid phone number or password.", "error")
    return render_template("login.html")


@customer_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name     = request.form.get("name", "").strip()
        phone    = request.form.get("phone", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        if not name or not phone or not email or not password:
            flash("All fields are required.", "error")
            return render_template("login.html")
        if not phone.isdigit() or len(phone) != 10:
            flash("Phone number must be exactly 10 digits.", "error")
            return render_template("login.html")
        if "@" not in email or "." not in email:
            flash("Please enter a valid email address.", "error")
            return render_template("login.html")
        try:
            conn = get_db()
            conn.execute(
                "INSERT INTO customers (name, phone, email, password) VALUES (?, ?, ?, ?)",
                (name, phone, email, hash_password(password))
            )
            conn.commit()
            conn.close()
            flash("Account created successfully! Please login.", "success")
            return redirect(url_for("customer.login"))
        except sqlite3.IntegrityError:
            flash("Phone number already registered. Please login.", "error")
    return render_template("login.html")


@customer_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("customer.login"))


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@customer_bp.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    cid = session["customer_id"]
    total  = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE customer_id=?", (cid,)).fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE customer_id=? AND status NOT IN ('Completed','Rejected')",
        (cid,)
    ).fetchone()["c"]
    payment_pending_count = conn.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE customer_id=? AND status='Payment Pending'",
        (cid,)
    ).fetchone()["c"]
    recent = conn.execute(
        "SELECT * FROM bookings WHERE customer_id=? ORDER BY created_at DESC LIMIT 3",
        (cid,)
    ).fetchall()
    # Unread notifications
    notifications = conn.execute(
        "SELECT * FROM notifications WHERE customer_id=? AND is_read=0 ORDER BY created_at DESC",
        (cid,)
    ).fetchall()
    conn.close()
    return render_template("customer_dashboard.html",
                           total=total, active=active, recent=recent,
                           payment_pending_count=payment_pending_count,
                           notifications=notifications)


# ─── MARK NOTIFICATIONS READ ─────────────────────────────────────────────────

@customer_bp.route("/notifications/read", methods=["POST"])
@login_required
def mark_notifications_read():
    conn = get_db()
    conn.execute(
        "UPDATE notifications SET is_read=1 WHERE customer_id=?",
        (session["customer_id"],)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})


# ─── BOOK SERVICE ─────────────────────────────────────────────────────────────

@customer_bp.route("/book", methods=["GET", "POST"])
@login_required
def book_service():
    if request.method == "POST":
        fields = ["vehicle_name","vehicle_type","vehicle_number","model",
                  "body_type","model_year","problem","preferred_date","contact_number"]
        data = {f: request.form.get(f, "").strip() for f in fields}
        if any(v == "" for v in data.values()):
            flash("All fields are required.", "error")
            return render_template("book_service.html", phone=session.get("customer_phone",""))
        if not data["contact_number"].isdigit() or len(data["contact_number"]) != 10:
            flash("Contact number must be exactly 10 digits.", "error")
            return render_template("book_service.html", phone=session.get("customer_phone",""))
        ticket_id  = generate_ticket_id()
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db()
        conn.execute("""
            INSERT INTO bookings
              (ticket_id, customer_id, vehicle_name, vehicle_type, vehicle_number,
               model, body_type, model_year, problem, status, preferred_date, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,'Pending',?,?)
        """, (ticket_id, session["customer_id"], data["vehicle_name"], data["vehicle_type"],
              data["vehicle_number"], data["model"], data["body_type"], data["model_year"],
              data["problem"], data["preferred_date"], created_at))
        conn.commit()
        conn.close()
        flash(f"Service booked! Your Ticket ID is {ticket_id}.", "success")
        return redirect(url_for("customer.view_bookings"))
    return render_template("book_service.html", phone=session.get("customer_phone", ""))


# ─── VIEW BOOKINGS ────────────────────────────────────────────────────────────

@customer_bp.route("/bookings")
@login_required
def view_bookings():
    conn = get_db()
    bookings = conn.execute("""
        SELECT b.*, m.name as mechanic_name
        FROM bookings b
        LEFT JOIN mechanics m ON b.mechanic_id = m.id
        WHERE b.customer_id=?
        ORDER BY b.created_at DESC
    """, (session["customer_id"],)).fetchall()
    conn.close()
    return render_template("view_bookings.html", bookings=bookings)


# ─── PAY NOW ──────────────────────────────────────────────────────────────────

@customer_bp.route("/pay/<int:booking_id>", methods=["GET", "POST"])
@login_required
def pay_now(booking_id):
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=? AND customer_id=?",
        (booking_id, session["customer_id"])
    ).fetchone()
    if not booking or booking["status"] != "Payment Pending":
        conn.close()
        flash("Payment is not due for this booking.", "warning")
        return redirect(url_for("customer.view_bookings"))
    bill = conn.execute("SELECT * FROM bills WHERE booking_id=?", (booking_id,)).fetchone()

    if request.method == "POST":
        method = request.form.get("payment_method", "").strip()
        if method not in ("Online", "Cash"):
            flash("Please select a valid payment method.", "error")
            conn.close()
            return render_template("pay_now.html", booking=booking, bill=bill)
        updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE bookings SET payment_method=?, updated_at=? WHERE id=?",
            (method, updated_at, booking_id)
        )
        # Notify customer confirmation
        add_notification(conn, session["customer_id"],
                         f"Payment method '{method}' selected for {booking['ticket_id']}. "
                         f"Awaiting admin verification.")
        conn.commit()
        conn.close()
        flash(f"Payment method '{method}' submitted for {booking['ticket_id']}. "
              f"Admin will verify and complete your service.", "success")
        return redirect(url_for("customer.view_bookings"))

    conn.close()
    return render_template("pay_now.html", booking=booking, bill=bill)


# ─── BILL DETAIL ─────────────────────────────────────────────────────────────

@customer_bp.route("/bill/<int:booking_id>")
@login_required
def bill_detail(booking_id):
    conn = get_db()
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=? AND customer_id=?",
        (booking_id, session["customer_id"])
    ).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("customer.view_bookings"))
    bill = conn.execute("SELECT * FROM bills WHERE booking_id=?", (booking_id,)).fetchone()
    conn.close()
    return render_template("bill_detail.html", booking=booking, bill=bill)
