import sqlite3
import os
import json
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

admin_bp = Blueprint("admin", __name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

ADMIN_USERNAME = "Admin"
ADMIN_PASSWORD = "12345"

# ── Updated status flow (includes "Paid (Verifying)" → "Completed")
STATUS_FLOW = {
    "Pending":          ["Rejected"],   # Accept is done via mechanic assignment modal
    "Accepted":         ["In Progress", "Rejected"],
    "In Progress":      ["Payment Pending", "Rejected"],
    "Payment Pending":  ["Completed"],
    "Paid (Verifying)": ["Completed"],
    "Completed":        [],
    "Rejected":         [],
}

STATUS_MESSAGES = {
    "Accepted":         "Your service request ({tid}) has been accepted! We'll start working on your vehicle soon.",
    "Rejected":         "We're sorry, your service request ({tid}) has been rejected. Please contact us for more details.",
    "In Progress":      "Great news! Your vehicle ({tid}) is now being serviced by our technicians.",
    "Payment Pending":  "Your vehicle service ({tid}) is complete! Please proceed to payment via your dashboard.",
    "Paid (Verifying)": "Thank you for your payment for {tid}. Admin will verify and mark it as Completed soon.",
    "Completed":        "Your service ({tid}) is fully completed. Thank you for choosing MotoServ Centre! 🏍️",
}


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
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


def insert_notification(conn, customer_id, ticket_id, new_status):
    """Insert a notification for the customer when admin changes ticket status."""
    tmpl = STATUS_MESSAGES.get(new_status, "Your ticket ({tid}) status has been updated to: " + new_status + ".")
    message = tmpl.format(tid=ticket_id)
    conn.execute(
        "INSERT INTO notifications (customer_id, message, is_read, created_at) VALUES (?,?,0,?)",
        (customer_id, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )


def get_mechanics_with_task_count(conn):
    """Return all Active mechanics with their current active task count."""
    return conn.execute("""
        SELECT m.*,
               COUNT(b.id) as task_count
        FROM mechanics m
        LEFT JOIN bookings b ON b.mechanic_id = m.id
            AND b.status IN ('Accepted','In Progress')
        WHERE m.status = 'Active'
        GROUP BY m.id
        ORDER BY m.name
    """).fetchall()


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
            flash("Welcome, Admin! 🏍️", "success")
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

    # ── CORE KPIs
    total_customers   = conn.execute("SELECT COUNT(*) as c FROM customers").fetchone()["c"]
    total_bookings    = conn.execute("SELECT COUNT(*) as c FROM bookings").fetchone()["c"]
    total_mechanics   = conn.execute("SELECT COUNT(*) as c FROM mechanics WHERE status='Active'").fetchone()["c"]
    pending_tickets   = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Pending'").fetchone()["c"]
    accepted          = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Accepted'").fetchone()["c"]
    in_progress       = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='In Progress'").fetchone()["c"]
    payment_pending   = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Payment Pending'").fetchone()["c"]
    paid_verifying    = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Paid (Verifying)'").fetchone()["c"]
    completed         = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Completed'").fetchone()["c"]
    rejected          = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE status='Rejected'").fetchone()["c"]
    ready_for_billing = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE work_status='Ready for Billing' AND status='In Progress'").fetchone()["c"]
    total_revenue     = conn.execute("SELECT COALESCE(SUM(total_amount),0) as r FROM bills").fetchone()["r"]
    avg_bill          = conn.execute("SELECT COALESCE(AVG(total_amount),0) as a FROM bills").fetchone()["a"]

    today_str      = datetime.now().strftime("%Y-%m-%d")
    yesterday_str  = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_bookings     = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE DATE(created_at)=?", (today_str,)).fetchone()["c"]
    yesterday_bookings = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE DATE(created_at)=?", (yesterday_str,)).fetchone()["c"]

    # Weekly chart
    weekly_labels = []; weekly_counts = []; weekly_revenue = []
    for i in range(6, -1, -1):
        day = datetime.now() - timedelta(days=i)
        ds  = day.strftime("%Y-%m-%d")
        cnt = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE DATE(created_at)=?", (ds,)).fetchone()["c"]
        rev = conn.execute(
            "SELECT COALESCE(SUM(bi.total_amount),0) as r FROM bills bi JOIN bookings bk ON bi.booking_id=bk.id WHERE DATE(bk.created_at)=?",
            (ds,)
        ).fetchone()["r"]
        weekly_labels.append(day.strftime("%a"))
        weekly_counts.append(cnt)
        weekly_revenue.append(round(rev, 2))

    # Monthly trend
    monthly_labels = []; monthly_revenue = []; monthly_bookings = []
    for i in range(5, -1, -1):
        d   = datetime.now().replace(day=1) - timedelta(days=i * 30)
        ym  = d.strftime("%Y-%m")
        rev = conn.execute(
            "SELECT COALESCE(SUM(bi.total_amount),0) as r FROM bills bi JOIN bookings bk ON bi.booking_id=bk.id WHERE substr(bk.created_at,1,7)=?",
            (ym,)
        ).fetchone()["r"]
        cnt = conn.execute("SELECT COUNT(*) as c FROM bookings WHERE substr(created_at,1,7)=?", (ym,)).fetchone()["c"]
        monthly_labels.append(d.strftime("%b %Y"))
        monthly_revenue.append(round(rev, 2))
        monthly_bookings.append(cnt)

    status_labels = ["Pending","Accepted","In Progress","Payment Pending","Paid (Verifying)","Completed","Rejected"]
    status_data   = [pending_tickets, accepted, in_progress, payment_pending, paid_verifying, completed, rejected]
    vtype_rows    = conn.execute("SELECT vehicle_type, COUNT(*) as c FROM bookings GROUP BY vehicle_type ORDER BY c DESC").fetchall()
    vtype_labels  = [r["vehicle_type"] for r in vtype_rows]
    vtype_data    = [r["c"] for r in vtype_rows]

    bill_avg = conn.execute("SELECT COALESCE(AVG(spare_parts),0) as sp,COALESCE(AVG(labor_charge),0) as lc,COALESCE(AVG(service_charge),0) as sc FROM bills").fetchone()
    billing_labels = ["Spare Parts","Labor","Service"]
    billing_data   = [round(bill_avg["sp"],2), round(bill_avg["lc"],2), round(bill_avg["sc"],2)]

    top_customers = conn.execute("""
        SELECT c.name, COUNT(b.id) as bcount FROM customers c
        LEFT JOIN bookings b ON c.id=b.customer_id
        GROUP BY c.id ORDER BY bcount DESC LIMIT 5
    """).fetchall()
    recent_bookings = conn.execute("""
        SELECT b.*, c.name as customer_name, m.name as mechanic_name
        FROM bookings b
        JOIN customers c ON b.customer_id=c.id
        LEFT JOIN mechanics m ON b.mechanic_id=m.id
        ORDER BY b.created_at DESC LIMIT 8
    """).fetchall()
    conn.close()

    booking_change = round(((today_bookings - yesterday_bookings) / max(yesterday_bookings, 1)) * 100, 1)

    return render_template("admin_dashboard.html",
        total_customers=total_customers, total_bookings=total_bookings,
        total_mechanics=total_mechanics,
        pending_tickets=pending_tickets, in_progress=in_progress,
        payment_pending=payment_pending, paid_verifying=paid_verifying,
        ready_for_billing=ready_for_billing,
        completed=completed, rejected=rejected,
        total_revenue=total_revenue, avg_bill=avg_bill,
        today_bookings=today_bookings, booking_change=booking_change,
        weekly_labels=json.dumps(weekly_labels),
        weekly_counts=json.dumps(weekly_counts),
        weekly_revenue=json.dumps(weekly_revenue),
        monthly_labels=json.dumps(monthly_labels),
        monthly_revenue=json.dumps(monthly_revenue),
        monthly_bookings=json.dumps(monthly_bookings),
        status_labels=json.dumps(status_labels),
        status_data=json.dumps(status_data),
        vtype_labels=json.dumps(vtype_labels),
        vtype_data=json.dumps(vtype_data),
        billing_labels=json.dumps(billing_labels),
        billing_data=json.dumps(billing_data),
        top_customers=top_customers,
        recent_bookings=recent_bookings,
    )


# ─── TICKET MANAGEMENT ────────────────────────────────────────────────────────

@admin_bp.route("/tickets")
@admin_required
def admin_tickets():
    status_filter = request.args.get("status", "")
    conn = get_db()
    if status_filter:
        bookings = conn.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   m.name as mechanic_name
            FROM bookings b
            JOIN customers c ON b.customer_id=c.id
            LEFT JOIN mechanics m ON b.mechanic_id=m.id
            WHERE b.status=? ORDER BY b.created_at DESC
        """, (status_filter,)).fetchall()
    else:
        bookings = conn.execute("""
            SELECT b.*, c.name as customer_name, c.phone as customer_phone,
                   m.name as mechanic_name
            FROM bookings b
            JOIN customers c ON b.customer_id=c.id
            LEFT JOIN mechanics m ON b.mechanic_id=m.id
            ORDER BY b.created_at DESC
        """).fetchall()

    # Fetch mechanics with task counts for the assignment modal
    mechanics = get_mechanics_with_task_count(conn)
    conn.close()
    return render_template("admin_tickets.html", bookings=bookings,
                           status_filter=status_filter, status_flow=STATUS_FLOW,
                           mechanics=mechanics)


@admin_bp.route("/tickets/assign/<int:booking_id>", methods=["POST"])
@admin_required
def assign_mechanic(booking_id):
    """Accept a ticket and assign it to a mechanic."""
    mechanic_id = request.form.get("mechanic_id", "").strip()
    if not mechanic_id:
        flash("Please select a mechanic.", "error")
        return redirect(url_for("admin.admin_tickets"))
    conn = get_db()
    booking = conn.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
    if not booking or booking["status"] != "Pending":
        conn.close()
        flash("Ticket is not in Pending state or does not exist.", "error")
        return redirect(url_for("admin.admin_tickets"))
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "UPDATE bookings SET status='Accepted', mechanic_id=?, work_status='Accepted', updated_at=? WHERE id=?",
        (mechanic_id, updated_at, booking_id)
    )
    insert_notification(conn, booking["customer_id"], booking["ticket_id"], "Accepted")
    conn.commit()
    conn.close()
    flash(f"Ticket {booking['ticket_id']} accepted and mechanic assigned.", "success")
    return redirect(url_for("admin.admin_tickets"))


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
    insert_notification(conn, booking["customer_id"], booking["ticket_id"], new_status)
    conn.commit()
    conn.close()
    flash(f"Ticket {booking['ticket_id']} status updated to '{new_status}'.", "success")
    return redirect(url_for("admin.admin_tickets"))


# ─── BILLING ─────────────────────────────────────────────────────────────────

@admin_bp.route("/bill/<int:booking_id>", methods=["GET", "POST"])
@admin_required
def add_bill(booking_id):
    conn = get_db()
    booking = conn.execute("""
        SELECT b.*, m.name as mechanic_name
        FROM bookings b LEFT JOIN mechanics m ON b.mechanic_id=m.id
        WHERE b.id=?
    """, (booking_id,)).fetchone()
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
                    UPDATE bills SET spare_parts=?,labor_charge=?,service_charge=?,
                    tax=?,total_amount=? WHERE booking_id=?
                """, (spare_parts, labor_charge, service_charge, tax, total_amount, booking_id))
            else:
                conn.execute("""
                    INSERT INTO bills (booking_id,spare_parts,labor_charge,service_charge,tax,total_amount)
                    VALUES (?,?,?,?,?,?)
                """, (booking_id, spare_parts, labor_charge, service_charge, tax, total_amount))
            updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute("UPDATE bookings SET status='Payment Pending', updated_at=? WHERE id=?",
                         (updated_at, booking_id))
            insert_notification(conn, booking["customer_id"], booking["ticket_id"], "Payment Pending")
            conn.commit()
            conn.close()
            flash(f"Bill saved! Ticket {booking['ticket_id']} is now 'Payment Pending'. "
                  f"Customer must select payment method. Total: ₹{total_amount:,.2f}", "success")
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
        LEFT JOIN bookings b ON c.id=b.customer_id
        GROUP BY c.id ORDER BY c.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin_customers.html", customers=customers)


@admin_bp.route("/customers/delete/<int:customer_id>", methods=["POST"])
@admin_required
def delete_customer(customer_id):
    conn = get_db()
    conn.execute("DELETE FROM notifications WHERE customer_id=?", (customer_id,))
    conn.execute("DELETE FROM bookings WHERE customer_id=?", (customer_id,))
    conn.execute("DELETE FROM customers WHERE id=?", (customer_id,))
    conn.commit()
    conn.close()
    flash("Customer deleted successfully.", "success")
    return redirect(url_for("admin.admin_customers"))


# ─── MECHANIC MANAGEMENT ─────────────────────────────────────────────────────

@admin_bp.route("/mechanics")
@admin_required
def admin_mechanics():
    conn = get_db()
    mechanics = conn.execute("""
        SELECT m.*,
               COUNT(b.id) as task_count
        FROM mechanics m
        LEFT JOIN bookings b ON b.mechanic_id = m.id
            AND b.status IN ('Accepted','In Progress')
        GROUP BY m.id ORDER BY m.id DESC
    """).fetchall()
    conn.close()
    return render_template("admin_mechanics.html", mechanics=mechanics)


@admin_bp.route("/mechanics/add", methods=["POST"])
@admin_required
def add_mechanic():
    name             = request.form.get("name", "").strip()
    phone            = request.form.get("phone", "").strip()
    experience_years = request.form.get("experience_years", "0").strip()
    specialization   = request.form.get("specialization", "General").strip()
    status           = request.form.get("status", "Active").strip()
    if not name or not phone:
        flash("Name and phone are required.", "error")
        return redirect(url_for("admin.admin_mechanics"))
    if not phone.isdigit() or len(phone) != 10:
        flash("Phone must be exactly 10 digits.", "error")
        return redirect(url_for("admin.admin_mechanics"))
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO mechanics (name, phone, experience_years, specialization, status) VALUES (?,?,?,?,?)",
            (name, phone, int(experience_years), specialization, status)
        )
        conn.commit()
        conn.close()
        flash(f"Mechanic '{name}' added successfully.", "success")
    except sqlite3.IntegrityError:
        flash("A mechanic with that phone number already exists.", "error")
    return redirect(url_for("admin.admin_mechanics"))


@admin_bp.route("/mechanics/edit/<int:mechanic_id>", methods=["POST"])
@admin_required
def edit_mechanic(mechanic_id):
    name             = request.form.get("name", "").strip()
    phone            = request.form.get("phone", "").strip()
    experience_years = request.form.get("experience_years", "0").strip()
    specialization   = request.form.get("specialization", "General").strip()
    status_val       = request.form.get("status", "Active").strip()
    if not name or not phone:
        flash("Name and phone are required.", "error")
        return redirect(url_for("admin.admin_mechanics"))
    try:
        conn = get_db()
        conn.execute(
            "UPDATE mechanics SET name=?, phone=?, experience_years=?, specialization=?, status=? WHERE id=?",
            (name, phone, int(experience_years), specialization, status_val, mechanic_id)
        )
        conn.commit()
        conn.close()
        flash(f"Mechanic '{name}' updated.", "success")
    except sqlite3.IntegrityError:
        flash("Phone number already in use by another mechanic.", "error")
    return redirect(url_for("admin.admin_mechanics"))


@admin_bp.route("/mechanics/delete/<int:mechanic_id>", methods=["POST"])
@admin_required
def delete_mechanic(mechanic_id):
    conn = get_db()
    active = conn.execute(
        "SELECT COUNT(*) as c FROM bookings WHERE mechanic_id=? AND status IN ('Accepted','In Progress')",
        (mechanic_id,)
    ).fetchone()["c"]
    if active > 0:
        conn.close()
        flash("Cannot delete mechanic with active bookings. Please reassign or complete them first.", "error")
        return redirect(url_for("admin.admin_mechanics"))
    # Nullify mechanic_id in non-active bookings before deleting
    conn.execute("UPDATE bookings SET mechanic_id=NULL WHERE mechanic_id=?", (mechanic_id,))
    conn.execute("DELETE FROM mechanics WHERE id=?", (mechanic_id,))
    conn.commit()
    conn.close()
    flash("Mechanic deleted successfully.", "success")
    return redirect(url_for("admin.admin_mechanics"))
