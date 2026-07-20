import json
import re
from datetime import datetime

import app as spendly_app
from database.db import get_user_by_email, get_expense_summary

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

STALE_USER_ID = 999999  # does not exist in the seeded DB


def _client():
    spendly_app.app.config["TESTING"] = True
    return spendly_app.app.test_client()


def _logged_in_client():
    client = _client()
    client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    return client


def _expense_json(resp):
    match = re.search(
        r'<script type="application/json" id="expense-data">(.*?)</script>',
        resp.data.decode(),
        re.DOTALL,
    )
    assert match is not None, "expense-data JSON block missing from /profile response"
    return json.loads(match.group(1))


# --- Auth guard: logged-out access -------------------------------------- #

def test_logged_out_get_profile_redirects_to_login():
    """DoD: Logged-out GET /profile responds 302 to /login."""
    client = _client()
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_logged_out_get_profile_does_not_leak_page_body():
    """A logged-out request must not render any profile content in the body."""
    client = _client()
    resp = client.get("/profile")
    assert b"expense-data" not in resp.data


# --- Happy path: identity -------------------------------------------------- #

def test_logged_in_get_profile_returns_200():
    """DoD: After logging in, GET /profile responds 200."""
    client = _logged_in_client()
    resp = client.get("/profile")
    assert resp.status_code == 200


def test_profile_page_shows_user_name_and_email():
    """DoD: the page shows the user's name and email."""
    client = _logged_in_client()
    resp = client.get("/profile")

    user = get_user_by_email(DEMO_EMAIL)
    assert user["name"].encode() in resp.data
    assert user["email"].encode() in resp.data


# --- Member since formatting ---------------------------------------------- #

def test_member_since_uses_percent_B_percent_d_percent_Y_format():
    """DoD: "Member since" renders in "%B %d, %Y" format."""
    client = _logged_in_client()
    resp = client.get("/profile")

    user = get_user_by_email(DEMO_EMAIL)
    expected = datetime.strptime(
        user["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %d, %Y")
    assert f"Member since {expected}".encode() in resp.data

    # Sanity-check the exact shape (Month DD, YYYY) rather than just presence
    # of the substring, since the spec pins the strftime pattern precisely.
    assert re.match(r"^[A-Z][a-z]+ \d{2}, \d{4}$", expected)


# --- Embedded expense JSON data contract ----------------------------------- #

def test_expense_data_script_tag_is_present_and_is_json():
    """DoD: response contains the expense-data script tag with valid JSON."""
    client = _logged_in_client()
    resp = client.get("/profile")
    expenses = _expense_json(resp)
    assert isinstance(expenses, list)
    assert len(expenses) > 0


def test_expense_data_objects_have_exact_key_set():
    """DoD: JSON objects have exactly id, amount, category, date, description."""
    client = _logged_in_client()
    resp = client.get("/profile")
    expenses = _expense_json(resp)

    expected_keys = {"id", "amount", "category", "date", "description"}
    for expense in expenses:
        assert set(expense.keys()) == expected_keys


def test_expense_data_date_field_is_iso_format():
    """Spec: date field is formatted as YYYY-MM-DD."""
    client = _logged_in_client()
    resp = client.get("/profile")
    expenses = _expense_json(resp)

    for expense in expenses:
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", expense["date"])


def test_expense_data_ordered_newest_first():
    """DoD: expense list is ordered newest first."""
    client = _logged_in_client()
    resp = client.get("/profile")
    expenses = _expense_json(resp)

    dates = [expense["date"] for expense in expenses]
    assert dates == sorted(dates, reverse=True)


def test_expense_data_matches_db_summary_totals():
    """Cross-check: the rendered expense list is consistent with the
    get_expense_summary() helper for the same user (count and total)."""
    client = _logged_in_client()
    resp = client.get("/profile")
    expenses = _expense_json(resp)

    user = get_user_by_email(DEMO_EMAIL)
    summary = get_expense_summary(user["id"])

    assert len(expenses) == summary["count"]
    assert round(sum(e["amount"] for e in expenses), 2) == round(summary["total"], 2)


# --- password_hash must never leak ----------------------------------------- #

def test_password_hash_key_never_appears_in_response():
    """DoD: the string password_hash appears nowhere in the response body."""
    client = _logged_in_client()
    resp = client.get("/profile")
    assert b"password_hash" not in resp.data


def test_password_hash_value_never_appears_in_response():
    """DoD: the stored hash value appears nowhere in the response body."""
    client = _logged_in_client()
    resp = client.get("/profile")

    user = get_user_by_email(DEMO_EMAIL)
    assert user["password_hash"].encode() not in resp.data


# --- Stale session handling ------------------------------------------------ #

def test_stale_session_redirects_to_login():
    """DoD: a session pointing at a deleted user id is redirected to /login."""
    client = _client()
    with client.session_transaction() as sess:
        sess["user_id"] = STALE_USER_ID

    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_stale_session_is_cleared():
    """DoD: a session pointing at a deleted user id is cleared (session.clear())."""
    client = _client()
    with client.session_transaction() as sess:
        sess["user_id"] = STALE_USER_ID

    client.get("/profile")

    with client.session_transaction() as sess:
        assert "user_id" not in sess
        assert len(sess) == 0


# --- GET /profile has no DB side effects ------------------------------------ #

def test_repeated_get_profile_does_not_change_expense_summary():
    """Spec implies GET /profile is a read-only route: repeated requests must
    not alter the user's expense count/total in the database."""
    client = _logged_in_client()
    user = get_user_by_email(DEMO_EMAIL)

    before = get_expense_summary(user["id"])
    client.get("/profile")
    client.get("/profile")
    after = get_expense_summary(user["id"])

    assert before == after


def test_repeated_get_profile_does_not_change_user_identity():
    """Repeated GETs must not mutate the user's stored name/email/created_at."""
    client = _logged_in_client()

    before = get_user_by_email(DEMO_EMAIL)
    client.get("/profile")
    after = get_user_by_email(DEMO_EMAIL)

    assert before["name"] == after["name"]
    assert before["email"] == after["email"]
    assert before["created_at"] == after["created_at"]
    assert before["password_hash"] == after["password_hash"]
