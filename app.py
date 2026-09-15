from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime

app = Flask(__name__)

# ==========================================================
# APP CONFIGURATION
# ==========================================================

app.secret_key = "smart_virtual_queue_secret_key"

DATABASE = "queue.db"


# ==========================================================
# DATABASE
# ==========================================================

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_db()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE,
            name TEXT NOT NULL,
            mobile TEXT NOT NULL,
            email TEXT,
            service TEXT NOT NULL,
            people INTEGER DEFAULT 1,
            priority TEXT DEFAULT 'Normal',
            preferred_time TEXT,
            message TEXT,
            status TEXT DEFAULT 'Waiting',
            counter TEXT DEFAULT 'Counter 1',
            created_at TEXT
        )
    """)

    connection.commit()
    connection.close()


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================================
# JOIN QUEUE
# ==========================================================

@app.route("/join-queue", methods=["GET", "POST"])
def join_queue():

    if request.method == "GET":
        return render_template("join-queue.html")

    name = request.form.get("name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    email = request.form.get("email", "").strip()
    service = request.form.get("service", "").strip()

    people = request.form.get("people", "1")
    priority = request.form.get("priority", "Normal")
    preferred_time = request.form.get("preferred_time", "")
    message = request.form.get("message", "")

    priority_map = {
        "normal": "Normal",
        "senior": "Senior Citizen",
        "emergency": "Emergency"
    }

    priority = priority_map.get(priority, priority)

    if not name or not mobile or not service:
        return render_template(
            "join-queue.html",
            error="Please fill in Name, Mobile Number and Service."
        )

    try:
        people = int(people)
    except ValueError:
        people = 1

    if people < 1:
        people = 1

    connection = get_db()

    row = connection.execute("""
        SELECT token
        FROM users
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    if row:
        try:
            last_number = int(row["token"].split("-")[1])
            next_number = last_number + 1
        except (ValueError, IndexError):
            next_number = 101
    else:
        next_number = 101

    token = f"A-{next_number}"

    if service == "Document Verification":
        counter = "Counter 2"
    elif service == "Certificate Collection":
        counter = "Counter 3"
    else:
        counter = "Counter 1"

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection.execute("""
        INSERT INTO users
        (
            token, name, mobile, email, service, people,
            priority, preferred_time, message, status,
            counter, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        token,
        name,
        mobile,
        email,
        service,
        people,
        priority,
        preferred_time,
        message,
        "Waiting",
        counter,
        created_at
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("token_page", token=token))


# ==========================================================
# LEGACY TOKEN.HTML COMPATIBILITY
# ==========================================================

@app.route("/token.html", methods=["GET", "POST"])
def legacy_token():

    data = request.form if request.method == "POST" else request.args

    name = data.get("name", "").strip()
    mobile = data.get("mobile", "").strip()
    email = data.get("email", "").strip()
    service = data.get("service", "").strip()

    people = data.get("people", "1")
    priority = data.get("priority", "Normal")

    preferred_time = data.get(
        "preferred_time",
        data.get("time", "")
    )

    message = data.get("message", "")

    priority_map = {
        "normal": "Normal",
        "senior": "Senior Citizen",
        "emergency": "Emergency"
    }

    priority = priority_map.get(priority, priority)

    if not name or not mobile or not service:
        return """
        <h2>Missing Information</h2>
        <p>Please go back and fill in Name, Mobile Number and Service.</p>
        <p><a href="/join-queue">Back to Join Queue</a></p>
        """, 400

    try:
        people = int(people)
    except ValueError:
        people = 1

    if people < 1:
        people = 1

    connection = get_db()

    row = connection.execute("""
        SELECT token
        FROM users
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()

    if row:
        try:
            last_number = int(row["token"].split("-")[1])
            next_number = last_number + 1
        except (ValueError, IndexError):
            next_number = 101
    else:
        next_number = 101

    token = f"A-{next_number}"

    if service == "Document Verification":
        counter = "Counter 2"
    elif service == "Certificate Collection":
        counter = "Counter 3"
    else:
        counter = "Counter 1"

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    connection.execute("""
        INSERT INTO users
        (
            token, name, mobile, email, service, people,
            priority, preferred_time, message, status,
            counter, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        token,
        name,
        mobile,
        email,
        service,
        people,
        priority,
        preferred_time,
        message,
        "Waiting",
        counter,
        created_at
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("token_page", token=token))


# ==========================================================
# TOKEN PAGE
# ==========================================================

@app.route("/token/<token>")
def token_page(token):

    connection = get_db()

    user = connection.execute("""
        SELECT *
        FROM users
        WHERE token = ?
    """, (token,)).fetchone()

    if not user:
        connection.close()
        return "Token not found", 404

    people_ahead = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE id < ?
        AND status = 'Waiting'
    """, (user["id"],)).fetchone()["count"]

    waiting_time = people_ahead * 5

    serving = connection.execute("""
        SELECT token
        FROM users
        WHERE status = 'Serving'
        ORDER BY id
        LIMIT 1
    """).fetchone()

    current_token = serving["token"] if serving else "None"

    connection.close()

    return render_template(
        "token.html",
        user=user,
        people_ahead=people_ahead,
        waiting_time=waiting_time,
        current_token=current_token
    )


# ==========================================================
# QUEUE STATUS
# ==========================================================

@app.route("/queue-status")
def queue_status():

    connection = get_db()

    users = connection.execute("""
        SELECT *
        FROM users
        ORDER BY id
    """).fetchall()

    current_user = connection.execute(
        """
        SELECT *
        FROM users
        WHERE status = 'Serving'
        ORDER BY id ASC
        LIMIT 1
        """
    ).fetchone()

    connection.close()

    return render_template(
        "queue-status.html",
        users=users,
        current_user=current_user
    )


# ==========================================================
# ADMIN LOGIN
# ==========================================================

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        username = request.form.get("username", "")
        password = request.form.get("password", "")

        if username == "admin" and password == "admin123":
            session["admin"] = True
            return redirect(url_for("admin"))

        return render_template(
            "admin-login.html",
            error="Invalid username or password"
        )

    return render_template("admin-login.html")


# ==========================================================
# ADMIN DASHBOARD
# ==========================================================

@app.route("/admin")
def admin():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    connection = get_db()

    users = connection.execute("""
        SELECT *
        FROM users
        ORDER BY id
    """).fetchall()

    serving = connection.execute("""
        SELECT token
        FROM users
        WHERE status = 'Serving'
        ORDER BY id
        LIMIT 1
    """).fetchone()

    waiting_users = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE status = 'Waiting'
    """).fetchone()["count"]

    completed_today = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE status = 'Completed'
    """).fetchone()["count"]

    next_user = connection.execute("""
        SELECT token
        FROM users
        WHERE status = 'Waiting'
        ORDER BY
            CASE priority
                WHEN 'Emergency' THEN 1
                WHEN 'Senior Citizen' THEN 2
                ELSE 3
            END,
            id
        LIMIT 1
    """).fetchone()

    connection.close()

    current_token = serving["token"] if serving else "None"
    next_token = next_user["token"] if next_user else "None"

    return render_template(
        "admin.html",
        users=users,
        current_token=current_token,
        next_token=next_token,
        waiting_users=waiting_users,
        completed_today=completed_today
    )


# ==========================================================
# CALL NEXT
# ==========================================================

@app.route("/admin/call-next", methods=["POST"])
def call_next():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    connection = get_db()

    connection.execute("""
        UPDATE users
        SET status = 'Completed'
        WHERE status = 'Serving'
    """)

    next_user = connection.execute("""
        SELECT id
        FROM users
        WHERE status = 'Waiting'
        ORDER BY
            CASE priority
                WHEN 'Emergency' THEN 1
                WHEN 'Senior Citizen' THEN 2
                ELSE 3
            END,
            id
        LIMIT 1
    """).fetchone()

    if next_user:
        connection.execute("""
            UPDATE users
            SET status = 'Serving'
            WHERE id = ?
        """, (next_user["id"],))

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# ==========================================================
# COMPLETE TOKEN
# ==========================================================

@app.route("/admin/complete", methods=["POST"])
def complete_token():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    connection = get_db()

    connection.execute("""
        UPDATE users
        SET status = 'Completed'
        WHERE status = 'Serving'
    """)

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# ==========================================================
# SKIP TOKEN
# ==========================================================

@app.route("/admin/skip", methods=["POST"])
def skip_token():

    if not session.get("admin"):
        return redirect(url_for("admin_login"))

    connection = get_db()

    connection.execute("""
        UPDATE users
        SET status = 'Skipped'
        WHERE status = 'Serving'
    """)

    connection.commit()
    connection.close()

    return redirect(url_for("admin"))


# ==========================================================
# QUEUE INFORMATION
# ==========================================================

@app.route("/queue-info")
def queue_info():

    connection = get_db()

    total = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
    """).fetchone()["count"]

    waiting = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE status = 'Waiting'
    """).fetchone()["count"]

    completed = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE status = 'Completed'
    """).fetchone()["count"]

    emergency = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE priority = 'Emergency'
        AND status = 'Waiting'
    """).fetchone()["count"]

    senior = connection.execute("""
        SELECT COUNT(*) AS count
        FROM users
        WHERE priority = 'Senior Citizen'
        AND status = 'Waiting'
    """).fetchone()["count"]

    users = connection.execute("""
        SELECT *
        FROM users
        WHERE status = 'Waiting'
        ORDER BY
            CASE
                WHEN priority = 'Emergency' THEN 1
                WHEN priority = 'Senior Citizen' THEN 2
                ELSE 3
            END,
            id ASC
    """).fetchall()

    counters = connection.execute("""
        SELECT
            counter,
            service,
            token,
            status
        FROM users
        WHERE status = 'Serving'
        ORDER BY counter
    """).fetchall()

    connection.close()

    average_wait = waiting * 5

    return render_template(
        "queue-info.html",
        user_count=total,
        waiting_count=waiting,
        completed_count=completed,
        average_wait=average_wait,
        emergency=emergency,
        senior=senior,
        users=users,
        counters=counters
    )


# ==========================================================
# ABOUT
# ==========================================================

@app.route("/about")
def about():
    return render_template("about.html")


# ==========================================================
# LOGOUT
# ==========================================================

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("home"))


# ==========================================================
# APPLICATION START
# ==========================================================

# Initialize database when application starts
init_db()


if __name__ == "__main__":

    print("\n==========================================")
    print(" SMART VIRTUAL QUEUE SYSTEM")
    print("==========================================")
    print("Development server:")
    print("http://127.0.0.1:2007/")
    print("==========================================\n")

    app.run(
        host="127.0.0.1",
        port=2007,
        debug=True
    )
