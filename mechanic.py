import sqlite3
import os
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

mechanic_bp = Blueprint("mechanic", __name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

# Mechanic work status flow
WORK_STATUS_FLOW = {
    "":                 "In Progress",
    "Accepted":         "In Progress",
    "In Progress":      "Ready for Billing",
    "Ready for Billing": None,   # terminal state for mechanic
}

WORK_STATUS_LABEL = {
    "":                 "Start Work",
    "Accepted":         "Start Work",
    "In Progress":      "Mark Ready for Billing",
    "Ready for Billing": None,
}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def mechanic_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("mechanic_id"):
            flash("Please login as a mechanic to continue.", "warning")
            return redirect(url_for("mechanic.mechanic_login"))
        return f(*args, **kwargs)
    return decorated


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@mechanic_bp.route("/login", methods=["GET", "POST"])
def mechanic_login():
    if session.get("mechanic_id"):
        return redirect(url_for("mechanic.mechanic_dashboard"))
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        if not phone:
            flash("Phone number is required.", "error")
            return render_template("mechanic_login.html")
        conn = get_db()
        mech = conn.execute(
            "SELECT * FROM mechanics WHERE phone=? AND status='Active'", (phone,)
        ).fetchone()
        conn.close()
        if mech:
            session["mechanic_id"]   = mech["id"]
            session["mechanic_name"] = mech["name"]
            flash(f"Welcome, {mech['name']}!", "success")
            return redirect(url_for("mechanic.mechanic_dashboard"))
        flash("No active mechanic found with that phone number.", "error")
    return render_template("mechanic_login.html")


@mechanic_bp.route("/logout")
def mechanic_logout():
    session.pop("mechanic_id", None)
    session.pop("mechanic_name", None)
    flash("Logged out successfully.", "info")
    return redirect(url_for("mechanic.mechanic_login"))


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@mechanic_bp.route("/dashboard")
@mechanic_required
def mechanic_dashboard():
    conn = get_db()
    mid = session["mechanic_id"]
    jobs = conn.execute("""
        SELECT b.*, c.name as customer_name, c.phone as customer_phone
        FROM bookings b
        JOIN customers c ON b.customer_id = c.id
        WHERE b.mechanic_id = ?
          AND b.status IN ('Accepted', 'In Progress', 'Payment Pending', 'Completed')
        ORDER BY b.updated_at DESC, b.created_at DESC
    """, (mid,)).fetchall()

    # Stats
    active_count    = sum(1 for j in jobs if j["status"] in ("Accepted", "In Progress"))
    billing_count   = sum(1 for j in jobs if j["work_status"] == "Ready for Billing")
    completed_count = sum(1 for j in jobs if j["status"] == "Completed")

    conn.close()
    return render_template("mechanic_dashboard.html",
                           jobs=jobs,
                           active_count=active_count,
                           billing_count=billing_count,
                           completed_count=completed_count,
                           work_status_flow=WORK_STATUS_FLOW,
                           work_status_label=WORK_STATUS_LABEL)


# ─── STATUS TOGGLE ────────────────────────────────────────────────────────────

@mechanic_bp.route("/update/<int:booking_id>", methods=["POST"])
@mechanic_required
def update_work_status(booking_id):
    conn = get_db()
    mid = session["mechanic_id"]
    booking = conn.execute(
        "SELECT * FROM bookings WHERE id=? AND mechanic_id=?", (booking_id, mid)
    ).fetchone()

    if not booking:
        conn.close()
        flash("Access denied or booking not found.", "error")
        return redirect(url_for("mechanic.mechanic_dashboard"))

    current_ws = booking["work_status"] or ""
    next_ws    = WORK_STATUS_FLOW.get(current_ws)

    if next_ws is None:
        conn.close()
        flash("This job is already marked as Ready for Billing.", "info")
        return redirect(url_for("mechanic.mechanic_dashboard"))

    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Update work_status and mirror to booking status for admin/customer visibility
    new_booking_status = booking["status"]
    if next_ws == "In Progress":
        new_booking_status = "In Progress"
    # "Ready for Billing" keeps booking status as "In Progress" so admin can add bill

    conn.execute(
        "UPDATE bookings SET work_status=?, status=?, updated_at=? WHERE id=?",
        (next_ws, new_booking_status, updated_at, booking_id)
    )

    # If ready for billing, insert a notification for admin awareness via customer channel
    if next_ws == "Ready for Billing":
        mech_name = session.get("mechanic_name", "Mechanic")
        # Notify the customer that work is complete and payment will be requested soon
        conn.execute(
            "INSERT INTO notifications (customer_id, message, is_read, created_at) VALUES (?,?,0,?)",
            (
                booking["customer_id"],
                f"Great news! {mech_name} has finished work on your vehicle ({booking['ticket_id']}). "
                f"The admin will generate your bill shortly.",
                updated_at
            )
        )

    conn.commit()
    conn.close()
    flash(f"Job status updated to '{next_ws}' for ticket {booking['ticket_id']}.", "success")
    return redirect(url_for("mechanic.mechanic_dashboard"))
