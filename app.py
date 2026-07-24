import sqlite3
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import check_password_hash

from database.db import (
    get_db,
    init_db,
    seed_db,
    get_user_by_email,
    get_user_by_id,
    get_expense_summary,
    get_expenses,
    create_user,
    create_expense,
    get_expense_by_id,
    update_expense,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key-change-in-production"

# The canonical expense categories — single source of truth for both the
# add-expense form and its server-side validation.
CATEGORIES = ["Food", "Transport", "Bills", "Health",
              "Entertainment", "Shopping", "Other"]

# Ensure the database exists and is seeded before any request is handled.
with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            error = "All fields are required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif get_user_by_email(email):
            error = "An account with that email already exists."
        else:
            try:
                create_user(name, email, password)
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                # Race: another request registered this email between the
                # check above and the insert. Same user-facing message.
                error = "An account with that email already exists."

        return render_template(
            "register.html", error=error, name=name, email=email
        )

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("profile"))

        error = "Invalid email or password."
        return render_template("login.html", error=error, email=email)

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))

    user_row = get_user_by_id(user_id)
    if user_row is None:
        # Stale session: id points at a user that no longer exists.
        session.clear()
        return redirect(url_for("login"))

    member_since = datetime.strptime(
        user_row["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %d, %Y")
    summary = get_expense_summary(user_id)
    expenses = [dict(row) for row in get_expenses(user_id)]

    # Only safe fields reach the template — never the password hash.
    user = {"name": user_row["name"], "email": user_row["email"]}

    return render_template(
        "profile.html",
        user=user,
        member_since=member_since,
        summary=summary,
        expenses=expenses,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))

    today = datetime.now().strftime("%Y-%m-%d")

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        try:
            amount = float(amount_raw)
        except ValueError:
            amount = None

        error = None
        if amount is None or amount <= 0:
            error = "Amount must be a number greater than zero."
        elif category not in CATEGORIES:
            error = "Please choose a valid category."
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                error = "Please enter a valid date."

        if error:
            return render_template(
                "add_expense.html",
                error=error,
                categories=CATEGORIES,
                amount=amount_raw,
                category=category,
                date=date or today,
                description=description,
            )

        # user_id comes only from the session — never from the form, so a user
        # can only add expenses for themselves.
        create_expense(user_id, amount, category, date, description or None)
        return redirect(url_for("profile"))

    return render_template("add_expense.html", categories=CATEGORIES, date=today)


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if user_id is None:
        return redirect(url_for("login"))

    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        date = request.form.get("date", "").strip()
        description = request.form.get("description", "").strip()

        error = None
        try:
            amount = float(amount_raw)
        except ValueError:
            amount = None

        if amount is None or amount <= 0:
            error = "Amount must be a number greater than zero."
        elif category not in CATEGORIES:
            error = "Please choose a valid category."
        else:
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                error = "Please enter a valid date."

        if error:
            return render_template(
                "edit_expense.html",
                error=error,
                categories=CATEGORIES,
                expense_id=id,
                amount=amount_raw,
                category=category,
                date=date,
                description=description,
            )

        # user_id comes only from the session — never from the form, so a user
        # can only edit their own expenses.
        update_expense(id, user_id, amount, category, date, description or None)
        return redirect(url_for("profile"))

    return render_template(
        "edit_expense.html",
        categories=CATEGORIES,
        expense_id=id,
        amount=expense["amount"],
        category=expense["category"],
        date=expense["date"],
        description=expense["description"],
    )


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
