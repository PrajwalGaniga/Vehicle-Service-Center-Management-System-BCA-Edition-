# 🏍️ Viva Preparation Guide
## Project: MotoServ Centre — Vehicle Service Management System

**BCA Final Year Project | Viva Date: Thursday, March 5, 2026 (11:00 AM onwards)**

---

## 📋 Project Overview

**MotoServ Centre** is a full-stack web-based Vehicle Service Management System built using:
- **Backend**: Python (Flask Framework)
- **Database**: SQLite (zero-setup, file-based)
- **Frontend**: HTML5, CSS3, JavaScript
- **Architecture**: MVC-based with Flask Blueprints

The system supports three roles — **Customer**, **Admin**, and **Mechanic** — each with their own dedicated portal.

---

## 🚀 Running Instructions

### Step 1: Install Dependencies
```bash
pip install flask
```

### Step 2: Run the Application
```bash
python main.py
```
- The app runs at **http://127.0.0.1:5000**
- If `ngrok.exe` is present in the project folder, a public URL is printed automatically
- The database is auto-created and seeded on the first run

### Default Credentials (Auto-Seeded)
| Role     | Login Field | Credential        |
|----------|-------------|-------------------|
| Admin    | Username    | `Admin`           |
| Admin    | Password    | `12345`           |
| Mechanic | Phone       | `9876543210` (Rajesh Kumar) |
| Mechanic | Phone       | `9123456789` (Suresh Sharma) |
| Mechanic | Phone       | `9988776655` (Priya Patel)   |

### Ngrok (Public URL for Mobile Testing)
1. Ensure `ngrok.exe` is in the project folder
2. Run `python main.py` — Ngrok starts automatically
3. The public HTTPS URL is printed in the terminal

---

## 📂 File Structure

```
Vehicle Service Center/
├── main.py            # App init, DB seeding, Ngrok integration
├── customer.py        # Customer blueprint (login, signup, booking, payment)
├── admin.py           # Admin blueprint (dashboard, tickets, billing, mechanics)
├── mechanic.py        # Mechanic blueprint (login, task management)
├── database.db        # SQLite database (auto-created)
├── ngrok.exe          # Ngrok for public URL tunneling
└── templates/
    ├── base.html          # Shared layout (theme toggle, navbar, flash alerts)
    ├── login.html         # Customer login + signup
    ├── customer_dashboard.html
    ├── book_service.html
    ├── view_bookings.html
    ├── pay_now.html
    ├── bill_detail.html
    ├── admin_login.html
    ├── admin_dashboard.html
    ├── admin_tickets.html
    ├── admin_mechanics.html
    ├── admin_customers.html
    ├── admin_add_bill.html
    ├── mechanic_login.html
    └── mechanic_dashboard.html
```

---

## 🗄️ Database Table Descriptions (3NF Normalized)

### Table 1: `customers`
| Field    | Type    | Description                                    |
|----------|---------|------------------------------------------------|
| id       | INTEGER | Primary Key, auto-incremented unique identifier|
| name     | TEXT    | Full name of the customer                      |
| email    | TEXT    | Customer email address (unique contact)        |
| phone    | TEXT    | 10-digit phone number (UNIQUE, used for login) |
| password | TEXT    | SHA-256 hashed password for security           |

### Table 2: `mechanics`
| Field            | Type    | Description                                        |
|------------------|---------|----------------------------------------------------|
| id               | INTEGER | Primary Key, auto-incremented unique identifier    |
| name             | TEXT    | Full name of the mechanic                          |
| phone            | TEXT    | 10-digit phone number (UNIQUE, used for login)     |
| experience_years | INTEGER | Number of years of professional experience         |
| specialization   | TEXT    | Area of expertise (e.g., Engine, Electrical, Body) |
| status           | TEXT    | Active or Inactive (controls login access)         |

### Table 3: `bookings`
| Field          | Type    | Description                                           |
|----------------|---------|-------------------------------------------------------|
| id             | INTEGER | Primary Key, auto-incremented unique identifier       |
| ticket_id      | TEXT    | Unique ticket reference (format: MOTO-1001, MOTO-1002)|
| customer_id    | INTEGER | Foreign Key → customers.id (who booked)               |
| mechanic_id    | INTEGER | Foreign Key → mechanics.id (who is assigned, nullable)|
| vehicle_name   | TEXT    | Brand/make of the vehicle (e.g., Honda, Yamaha)       |
| vehicle_type   | TEXT    | Type: Bike, Car, Truck, etc.                          |
| vehicle_number | TEXT    | License plate / registration number                   |
| model          | TEXT    | Specific model name (e.g., Activa, Pulsar)            |
| body_type      | TEXT    | Body configuration (Sedan, SUV, Scooter, etc.)        |
| model_year     | TEXT    | Manufacturing year of the vehicle                     |
| problem        | TEXT    | Description of the issue/service required             |
| status         | TEXT    | Current workflow status (see status flow below)       |
| preferred_date | TEXT    | Customer's preferred service date                     |
| payment_method | TEXT    | Cash or Online (set when customer pays)               |
| work_status    | TEXT    | Mechanic's internal progress (In Progress, Ready for Billing)|
| created_at     | TEXT    | Timestamp of booking creation                         |
| updated_at     | TEXT    | Timestamp of last status update                       |

### Table 4: `bills`
| Field          | Type    | Description                                        |
|----------------|---------|----------------------------------------------------|
| id             | INTEGER | Primary Key, auto-incremented unique identifier    |
| booking_id     | INTEGER | Foreign Key → bookings.id (UNIQUE — 1 bill/booking)|
| spare_parts    | REAL    | Cost of spare parts used in the service            |
| labor_charge   | REAL    | Mechanic labour charge                             |
| service_charge | REAL    | General service/overhead charge                    |
| tax            | REAL    | Tax percentage applied to subtotal                 |
| total_amount   | REAL    | Final computed total (parts+labor+service+tax%)    |

### Table 5: `notifications`
| Field       | Type    | Description                                        |
|-------------|---------|----------------------------------------------------|
| id          | INTEGER | Primary Key, auto-incremented                      |
| customer_id | INTEGER | Foreign Key → customers.id                         |
| message     | TEXT    | Notification text (status update info)             |
| is_read     | INTEGER | 0 = unread, 1 = read                               |
| created_at  | TEXT    | Timestamp when notification was generated          |

---

## 📐 Normalization Explanation

### First Normal Form (1NF) ✅
> **Rule**: Every column must hold atomic (indivisible) values. No repeating groups.

**Applied in MotoServ Centre:**
- Every field contains a single, atomic value. For example:
  - `vehicle_name` stores only the brand name (not "Honda, Yamaha")
  - `phone` stores one 10-digit number
  - `spare_parts`, `labor_charge`, `service_charge` are separate columns — not combined in one field
- There are no repeating groups anywhere in the schema

### Second Normal Form (2NF) ✅
> **Rule**: Must be in 1NF + every non-key column must depend on the **entire** primary key (no partial dependencies). Relevant for composite keys.

**Applied in MotoServ Centre:**
- All tables use a single-column integer primary key (`id`), so partial dependency is not possible
- Every non-key column in `bookings` (e.g., `vehicle_name`, `problem`, `status`) depends entirely on `bookings.id`
- Customer information (name, phone, email) is NOT stored in `bookings`—only `customer_id` (FK) is stored, avoiding data duplication

### Third Normal Form (3NF) ✅
> **Rule**: Must be in 2NF + no transitive dependencies (non-key columns must not depend on other non-key columns).

**Applied in MotoServ Centre:**
- **`bookings` table**: `mechanic_id` (FK) stores only the reference. The mechanic's `name`, `phone`, and `specialization` are NOT repeated in `bookings`—they live exclusively in `mechanics`. This eliminates transitive dependency.
- **`bills` table**: The `total_amount` is computed from `spare_parts + labor_charge + service_charge + tax%`. Although derived, it is stored to avoid repeated re-computation and all source columns are in the same table — no transitive dependency through a non-key intermediary.
- **`notifications` table**: Only `customer_id` links to the customer. The customer name is NOT stored in notifications—it's retrieved via JOIN, preventing transitive dependency.

### Summary Table
| NF   | Check | Reason |
|------|-------|--------|
| 1NF  | ✅    | All values are atomic; no repeating groups |
| 2NF  | ✅    | Single PK in all tables; no partial dependencies |
| 3NF  | ✅    | No non-key column depends on another non-key column |

---

## 🔄 Complete Workflow ("Golden Path")

```
Customer Signs Up
    → Books Service (Ticket generated: MOTO-1001)
        → Admin: Views "Pending Tickets" → Clicks "Accept & Assign" → Selects Mechanic
            → Status: Pending → Accepted
            → Mechanic: Logs in via Phone → Sees assigned jobs
                → Mechanic: Clicks "Start Work" → Status: In Progress
                → Mechanic: Clicks "Mark Ready for Billing"
                    → Admin: Sees "Ready for Billing" flag → Clicks "Generate Bill"
                    → Admin: Inputs Spare Parts, Labour, Service Charge, Tax %
                        → Status: Payment Pending
                        → Customer: Views Bill → Selects [Cash] or [Online]
                            → Status: Paid (Verifying)
                            → Admin: Confirms receipt → Marks "Completed"
                                → Status: Completed ✅
```

### Status Flow at a Glance

| Status           | Who Changes It       | How                             |
|------------------|---------------------|---------------------------------|
| Pending          | Customer            | Booking form submission         |
| Accepted         | Admin               | Accept & Assign Mechanic button |
| In Progress      | Mechanic            | "Start Work" button             |
| Ready for Billing| Mechanic            | "Mark Ready for Billing" button |
| Payment Pending  | Admin               | "Generate Bill" and save        |
| Paid (Verifying) | Customer            | Select payment method           |
| Completed        | Admin               | Confirm and mark complete       |
| Rejected         | Admin               | Reject ticket option            |

---

## 🎤 Likely Examiner Questions & Answers

**Q1: What is normalization? Why did you normalize your database?**
> Normalization is the process of organizing database tables to reduce data redundancy and improve data integrity. We applied 3NF to ensure atomic values (1NF), no partial dependencies (2NF), and no transitive dependencies (3NF). For example, mechanic details are stored only in the `mechanics` table and referenced via `mechanic_id` in `bookings`, not repeated.

**Q2: Explain your database schema.**
> We have 5 tables: `customers` (user accounts), `mechanics` (staff profiles), `bookings` (service tickets linking customers and mechanics), `bills` (cost breakdown per booking), and `notifications` (real-time status alerts). All tables use integer primary keys and foreign keys to maintain referential integrity.

**Q3: What is a Foreign Key?**
> A Foreign Key is a column that references the Primary Key of another table to establish a relationship. In `bookings`, `customer_id` references `customers.id` and `mechanic_id` references `mechanics.id`.

**Q4: How did you implement role-based access control?**
> We used Flask sessions to track user roles. When a customer logs in, `session['customer_id']` is set. For admin, `session['is_admin'] = True`. For mechanics, `session['mechanic_id']` is set. Decorator functions (`login_required`, `admin_required`, `mechanic_required`) check the session before serving protected pages.

**Q5: What is the ticket ID format?**
> Tickets are generated as `MOTO-1001`, `MOTO-1002`, etc. The number is computed as `1001 + total_booking_count`, ensuring unique, sequential, human-readable identifiers.

**Q6: How does the payment flow work?**
> 1. Admin generates a bill (sets status to "Payment Pending")
> 2. Customer views the bill and selects Cash or Online (status becomes "Paid (Verifying)")
> 3. Admin verifies and marks as "Completed"

**Q7: Why SQLite instead of MySQL/PostgreSQL?**
> SQLite is a zero-setup, serverless database stored as a single file (`database.db`). It's ideal for development and demonstration. The app can be migrated to PostgreSQL or MySQL in production with minimal code changes.

---

*MotoServ Centre — Built for BCA Final Year Project | March 2026*
