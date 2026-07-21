import json
import re
import uuid
from datetime import datetime

import pytest

import app as spendly_app
from database.db import get_db, get_expenses, get_expense_summary, get_user_by_email

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

ALL_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]

TODAY = datetime.now().strftime("%Y-%m-%d")


def _client():
    spendly_app.app.config["TESTING"] = True
    return spendly_app.app.test_client()


def _logged_in_client():
    client = _client()
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    return client


def _demo_user_id():
    return get_user_by_email(DEMO_EMAIL)["id"]


def _unique_description(label):
    return f"test-06-add-expense-{label}-{uuid.uuid4().hex[:8]}"


def _valid_payload(description, **overrides):
    payload = {
        "amount": "12.34",
        "category": "Food",
        "date": TODAY,
        "description": description,
    }
    payload.update(overrides)
    return payload


def _delete_test_expense(description):
    """Remove a test-created expense row, identified by its unique
    description marker, so tests don't leave residue in the shared DB."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM expenses WHERE description = ?", (description,))
        conn.commit()
    finally:
        conn.close()


def _expense_json(resp):
    match = re.search(
        r'<script type="application/json" id="expense-data">(.*?)</script>',
        resp.data.decode(),
        re.DOTALL,
    )
    assert match is not None, "expense-data JSON block missing from /profile"
    return json.loads(match.group(1))


def test_add_expense_get_requires_login():
    client = _client()
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_add_expense_form_renders_when_logged_in():
    client = _logged_in_client()
    resp = client.get("/expenses/add")
    assert resp.status_code == 200

    body = resp.data
    assert b'name="amount"' in body
    assert b'name="date"' in body
    assert b'name="description"' in body
    assert b"<select" in body

    for category in ALL_CATEGORIES:
        assert category.encode() in body


def test_valid_post_creates_exactly_one_row_and_redirects_to_profile():
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("valid")

    before = get_expense_summary(user_id)["count"]
    try:
        resp = client.post("/expenses/add", data=_valid_payload(description))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

        after = get_expense_summary(user_id)["count"]
        assert after - before == 1
    finally:
        _delete_test_expense(description)


def test_new_expense_appears_on_profile():
    client = _logged_in_client()
    description = _unique_description("appears")

    try:
        post_resp = client.post("/expenses/add", data=_valid_payload(description))
        assert post_resp.status_code == 302

        resp = client.get("/profile")
        assert resp.status_code == 200

        expenses = _expense_json(resp)
        descriptions = [e["description"] for e in expenses]
        assert description in descriptions
    finally:
        _delete_test_expense(description)


@pytest.mark.parametrize("bad_amount", ["", "not-a-number", "0", "-5"])
def test_invalid_amount_rerenders_form_without_inserting(bad_amount):
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("bad-amount")

    before = get_expense_summary(user_id)["count"]
    try:
        resp = client.post(
            "/expenses/add", data=_valid_payload(description, amount=bad_amount)
        )
        assert resp.status_code == 200
        assert b"auth-error" in resp.data

        after = get_expense_summary(user_id)["count"]
        assert after == before
    finally:
        _delete_test_expense(description)


@pytest.mark.parametrize("bad_category", ["", "NotACategory", "food"])
def test_invalid_category_rerenders_form_without_inserting(bad_category):
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("bad-category")

    before = get_expense_summary(user_id)["count"]
    try:
        resp = client.post(
            "/expenses/add", data=_valid_payload(description, category=bad_category)
        )
        assert resp.status_code == 200
        assert b"auth-error" in resp.data

        after = get_expense_summary(user_id)["count"]
        assert after == before
    finally:
        _delete_test_expense(description)


@pytest.mark.parametrize("bad_date", ["", "not-a-date", "07-15-2026", "2026-13-40"])
def test_invalid_date_rerenders_form_without_inserting(bad_date):
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("bad-date")

    before = get_expense_summary(user_id)["count"]
    try:
        resp = client.post(
            "/expenses/add", data=_valid_payload(description, date=bad_date)
        )
        assert resp.status_code == 200
        assert b"auth-error" in resp.data

        after = get_expense_summary(user_id)["count"]
        assert after == before
    finally:
        _delete_test_expense(description)


def test_add_expense_post_requires_login():
    client = _client()
    user_id = _demo_user_id()
    description = _unique_description("logged-out")

    before = get_expense_summary(user_id)["count"]
    try:
        resp = client.post("/expenses/add", data=_valid_payload(description))
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

        after = get_expense_summary(user_id)["count"]
        assert after == before
    finally:
        _delete_test_expense(description)


def test_created_expense_is_scoped_to_session_user_not_the_form():
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("scoping")

    # Attempt to spoof a different owner via an extra form field; the route
    # must ignore it and always use session["user_id"].
    payload = _valid_payload(description, user_id="999999")

    try:
        resp = client.post("/expenses/add", data=payload)
        assert resp.status_code == 302

        expenses = get_expenses(user_id)
        assert len(expenses) > 0
        newest = expenses[0]
        assert newest["description"] == description
        assert newest["amount"] == pytest.approx(12.34)
        assert newest["category"] == "Food"
    finally:
        _delete_test_expense(description)
