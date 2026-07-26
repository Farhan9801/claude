import os
import sqlite3

from werkzeug.security import generate_password_hash

# Anchor the database file to the project root (one level up from this file)
# so the path resolves correctly regardless of the current working directory.
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "expense_tracker.db")


def get_db():
    """Return a SQLite connection with dict-like rows and FK enforcement on."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create both tables if they don't exist. Safe to call repeatedly."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            email         TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL REFERENCES users(id),
            amount      REAL NOT NULL,
            category    TEXT NOT NULL,
            date        TEXT NOT NULL,
            description TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()
    conn.close()


def seed_db():
    """Insert demo data once. No-op if the users table already has rows."""
    conn = get_db()

    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        return

    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
    )
    user_id = cursor.lastrowid

    # (amount, category, date, description) — covers all 7 categories,
    # dates spread across the current month (YYYY-MM-DD).
    expenses = [
        (42.50, "Food", "2026-06-02", "Groceries"),
        (18.00, "Transport", "2026-06-04", "Bus pass top-up"),
        (120.00, "Bills", "2026-06-05", "Electricity bill"),
        (35.75, "Health", "2026-06-08", "Pharmacy"),
        (60.00, "Entertainment", "2026-06-11", "Concert ticket"),
        (89.99, "Shopping", "2026-06-13", "New shoes"),
        (25.00, "Other", "2026-06-15", "Gift"),
        (15.25, "Food", "2026-06-17", "Lunch out"),
    ]
    conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        [(user_id, *row) for row in expenses],
    )

    conn.commit()
    conn.close()


def get_user_by_email(email):
    """Return the users row matching email, or None if there is no such user."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    """Return the users row matching id, or None if there is no such user."""
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row


def get_expense_summary(user_id):
    """Return {'count': int, 'total': float} for a user's expenses."""
    conn = get_db()
    row = conn.execute(
        "SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total "
        "FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    return {"count": row["count"], "total": row["total"]}


def get_expenses(user_id):
    """Return all of a user's expenses, newest first."""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE user_id = ? ORDER BY date DESC, id DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def create_user(name, email, password):
    """Create a user with a hashed password. Return the new user's id.

    Raises sqlite3.IntegrityError if the email already exists (UNIQUE
    constraint) — callers should handle it.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def create_expense(user_id, amount, category, date, description):
    """Insert one expense for a user and return the new expense's id.

    created_at is defaulted by the database, so it is not passed here.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense_by_id(expense_id, user_id):
    """Return one expense owned by user_id, or None.

    Scoped by both id and user_id so a user can only fetch their own expense.
    """
    conn = get_db()
    row = conn.execute(
        "SELECT id, amount, category, date, description FROM expenses "
        "WHERE id = ? AND user_id = ?",
        (expense_id, user_id),
    ).fetchone()
    conn.close()
    return row


def update_expense(expense_id, user_id, amount, category, date, description):
    """Update one expense owned by user_id and return rows changed (0 if not owned).

    Never touches id, user_id, or created_at. The WHERE ... AND user_id = ?
    clause is a second ownership guard.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?, description = ? "
            "WHERE id = ? AND user_id = ?",
            (amount, category, date, description, expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_expense_by_id(expense_id, user_id):
    """Delete one expense owned by user_id and return rows deleted (0 if not owned).

    Named *_by_id, not delete_expense, because delete_expense is the route
    function name in app.py — importing a same-named helper would shadow it.
    The WHERE ... AND user_id = ? clause is a second ownership guard behind the
    route's get_expense_by_id check, and guarantees at most one row is removed.
    """
    conn = get_db()
    try:
        cursor = conn.execute(
            "DELETE FROM expenses WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
