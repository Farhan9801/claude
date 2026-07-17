import sqlite3

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import check_password_hash

from database.db import (
    get_db,
    init_db,
    seed_db,
    get_user_by_email,
    create_user,
)

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key-change-in-production"

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
    return "Profile page — coming in Step 4"


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
