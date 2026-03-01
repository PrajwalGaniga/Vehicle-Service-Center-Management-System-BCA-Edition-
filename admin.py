import sqlite3
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

admin_bp = Blueprint("admin", __name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "12345"

STATUS_FLOW = {
    "Pending":     ["Accepted", "Rejected"],
    "Accepted":    ["In Progress", "Rejected"],
    "In Progress": ["Completed"],
    "Completed":   [],
    "Rejected":    [],
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "warning")
            return redirect(url_for("admin.admin_login"))
        return f(*args, **kwargs)
    return decorated


# ─── AUTH ────────────────────────────────────────────────────────────────────

@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_admin"):
        return redirect(url_for("admin.admin_dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Welcome, Admin!", "success")
            return redirect(url_for("admin.admin_dashboard"))
        flash("Invalid admin credentials.", "error")
    return render_template("admin_login.html")


@admin_bp.route("/logout")
def admin_logout():
    session.pop("is_admin", None)
    flash("Admin logged out.", "info")
    return redirect(url_for("admin.admin_login"))


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@admin_bp.route("/dashboard")
@admin_required
def admin_dashboard():
    conn = get_db()
    total_customers  = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]
    total_bookings   = conn.execute("SELECT COUNT(*) as c FROM bookings").fetchone()["c"]
    pending_tickets  = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Pending'").fetchone()["c"]
    completed        = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Completed'").fetchone()["c"]
    total_revenue    = conn.execute("SELECT COALESCE(SUM(total_amount),0) as r FROM bills").fetchone()["r"]
    recent_bookings  = conn.execute("""
        SELECT b.*, c.name as customer_name
        FROM bookings b JOIN customers c ON b.customer_id = c.id
        ORDER BY b.created_at DESC LIMIT 5
    """).fetchall()
    conn.close()
    return render_template("admin_dashboard.html",
                           total_customers=total_customers,
                           total_bookings=total_bookings,
                           pending_tickets=pending_tickets,
                           completed=completed,
                           total_revenue=total_revenue,
                           recent_bookings=recent_bookings)


# ─── TICKET MANAGEMENT ────────────────────────────────────────────────────────

@admin_bp.route("/tickets")
@admin_required
def admin_tickets():
    status_filter = request.args.get("status", "")
    conn = get_db()
    if status_filter:
        bookings = conn.execute("""
            SELECT b.*, c.name as customer_name
            FROM bookings b JOIN customers c ON b.customer_id = c.id
            WHERE b.status = ?
            ORDER BY b.created_at DESC
        """, (status_filter,)).fetchall()
    else:
        bookings = conn.execute("""
            SELECT b.*, c.name as customer_name
            FROM bookings b JOIN customers c ON b.customer_id = c.id
            ORDER BY b.created_at DESC
        """).fetchall()
    conn.close()
    return render_template("admin_tickets.html", bookings=bookings,
                           status_filter=status_filter, status_flow=STATUS_FLOW)


@admin_bp.route("/tickets/update/<int:booking_id>", methods=["POST"])
@admin_required
def update_status(booking_id):
    new_status = request.form.get("new_status", "").strip()
    conn = get_db()
    booking = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking:
        conn.close()
        flash("Booking not found.", "error")
        return redirect(url_for("admin.admin_tickets"))
    allowed = STATUS_FLOW.get(booking["status"], [])
    if new_status not in allowed:
        conn.close()
        flash(f"Cannot transition from '{booking['status']}' to '{new_status}'.", "error")
        return redirect(url_for("admin.admin_tickets"))
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE bookings SET status=?, updated_at=? WHERE id=?",
                 (new_status, updated_at, booking_id))
    conn.commit()
    conn.close()
    flash(f"Ticket {booking['ticket_id']} status updated to '{new_status}'.", "success")
    return redirect(url_for("admin.admin_tickets"))


# ─── BILLING ─────────────────────────────────────────────────────────────────

@admin_bp.route("/bill/<int:booking_id>", methods=["GET", "POST"])
@admin_required
def add_bill(booking_id):
    conn = get_db()
    booking = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking or booking["status"] != "In Progress":
        conn.close()
        flash("Bill can only be added for 'In Progress' tickets.", "error")
        return redirect(url_for("admin.admin_tickets"))
    existing_bill = conn.execute("SELECT * FROM bills WHERE booking_id=?", (booking_id,)).fetchone()
    if request.method == "POST":
        try:
            spare_parts    = float(request.form.get("spare_parts", 0) or 0)
            labor_charge   = float(request.form.get("labor_charge", 0) or 0)
            service_charge = float(request.form.get("service_charge", 0) or 0)
            tax            = float(request.form.get("tax", 0) or 0)
            total_amount   = spare_parts + labor_charge + service_charge + (
                (spare_parts + labor_charge + service_charge) * tax / 100
            )
            if existing_bill:
                conn.execute("""
                    UPDATE bills SET spare_parts=?, labor_charge=?, service_charge=?,
                    tax=?, total_amount=? WHERE booking_id=?
                """, (spare_parts, labor_charge, service_charge, tax, total_amount, booking_id))
            else:
                conn.execute("""
                    INSERT INTO bills (booking_id, spare_parts, labor_charge, service_charge, tax, total_amount)
                    VALUES (?,?,?,?,?,?)
                """, (booking_id, spare_parts, labor_charge, service_charge, tax, total_amount))
            updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE bookings SET status='Completed', updated_at=? WHERE id=?",
                         (updated_at, booking_id))
            conn.commit()
            conn.close()
            flash(f"Bill added and ticket marked as Completed. Total: ₹{total_amount:,.2f}", "success")
            return redirect(url_for("admin.admin_tickets"))
        except ValueError:
            flash("Invalid numeric values entered.", "error")
    conn.close()
    return render_template("admin_add_bill.html", booking=booking, existing_bill=existing_bill)


# ─── CUSTOMER MANAGEMENT ─────────────────────────────────────────────────────

@admin_bp.route("/customers")
@admin_required
def admin_customers():
    conn = get_db()
    customers = conn.execute("""
        SELECT c.*, COUNT(b.id) as booking_count
        FROM customers c
        LEFT JOIN bookings b ON c.id = b.customer_id
        GROUP BY c.id
        ORDER BY c.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin_customers.html", customers=customers)


@admin_bp.route("/customers/delete/<int:customer_id>", methods=["POST"])
@admin_required
def delete_customer(customer_id):
    conn = get_db()
    conn.execute("DELETE FROM bookings WHERE customer_id=?", (customer_id,))
    conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))
    conn.commit()
    conn.close()
    flash("Customer deleted successfully.", "success")
    return redirect(url_for("admin.admin_customers"))
