import json
import re
import uuid

import pytest

import app as spendly_app
from database.db import (
    create_expense,
    create_user,
    get_db,
    get_expense_by_id,
    get_expense_summary,
    get_expenses,
    get_user_by_email,
)

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"

NONEXISTENT_EXPENSE_ID = 999999999  # does not exist in the seeded DB


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
    return f"test-07-edit-expense-{label}-{uuid.uuid4().hex[:8]}"


def _unique_email(label):
    return f"test-07-edit-expense-{label}-{uuid.uuid4().hex[:8]}@example.com"


def _valid_payload(description, **overrides):
    payload = {
        "amount": "42.00",
        "category": "Food",
        "date": "2026-06-15",
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


def _delete_test_user(email):
    """Remove a test-created user, so tests don't leave residue in the
    shared DB. Only ever used on emails created within this file."""
    conn = get_db()
    try:
        conn.execute("DELETE FROM users WHERE email = ?", (email,))
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


# --- DoD 1: logged-out GET redirects to /login ------------------------------ #

def test_edit_get_requires_login():
    """DoD 1: GET /expenses/<id>/edit while logged out redirects to /login (302)."""
    client = _client()
    resp = client.get(f"/expenses/{NONEXISTENT_EXPENSE_ID}/edit")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# --- DoD 2: logged-in GET renders a pre-filled form for an owned expense --- #

def test_edit_get_renders_prefilled_form_for_owned_expense():
    """DoD 2: GET for an owned expense returns 200 and pre-fills the form
    with that expense's amount, category (correct option selected), date,
    and description."""
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("prefill")
    expense_id = create_expense(user_id, 63.40, "Bills", "2026-06-10", description)

    try:
        expense = get_expense_by_id(expense_id, user_id)
        resp = client.get(f"/expenses/{expense_id}/edit")
        assert resp.status_code == 200

        body = resp.data.decode()
        assert str(expense["amount"]) in body
        assert expense["date"] in body
        assert expense["description"] in body

        # the current category's <option> must be marked selected
        selected_option = re.search(
            rf'<option value="{re.escape(expense["category"])}"[^>]*selected',
            body,
        )
        assert selected_option is not None, (
            f"expected the {expense['category']!r} option to be selected"
        )
    finally:
        _delete_test_expense(description)


# --- DoD 3: valid POST updates exactly that one row, no new row created --- #

def test_valid_post_updates_the_existing_row_in_place():
    """DoD 3: valid POST updates amount/category/date/description on the
    same row, redirects (302) to /profile, creates no new row, and leaves
    the row's id (and, by extension, its ownership) unchanged."""
    client = _logged_in_client()
    user_id = _demo_user_id()
    original_description = _unique_description("update-original")
    updated_description = _unique_description("update-changed")
    expense_id = create_expense(user_id, 20.00, "Food", "2026-06-01", original_description)

    before_count = len(get_expenses(user_id))

    try:
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_payload(
                updated_description, amount="99.99", category="Bills", date="2026-06-20"
            ),
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/profile")

        after_count = len(get_expenses(user_id))
        assert after_count == before_count  # no new row created

        updated = get_expense_by_id(expense_id, user_id)
        assert updated is not None  # still owned by / found under the same user
        assert updated["id"] == expense_id
        assert updated["amount"] == pytest.approx(99.99)
        assert updated["category"] == "Bills"
        assert updated["date"] == "2026-06-20"
        assert updated["description"] == updated_description
    finally:
        _delete_test_expense(updated_description)
        _delete_test_expense(original_description)  # safety net if update failed


# --- DoD 4: edited values show up on /profile; summary count unchanged ---- #

def test_edited_values_appear_on_profile_and_summary_reflects_change():
    """DoD 4: the edited values appear on /profile, the expense count is
    unchanged, and the total reflects the amount change."""
    client = _logged_in_client()
    user_id = _demo_user_id()
    original_description = _unique_description("visible-original")
    new_description = _unique_description("visible-changed")
    expense_id = create_expense(user_id, 10.00, "Food", "2026-06-01", original_description)

    before_summary = get_expense_summary(user_id)

    try:
        post_resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_payload(
                new_description, amount="88.00", category="Shopping", date="2026-06-22"
            ),
        )
        assert post_resp.status_code == 302

        profile_resp = client.get("/profile")
        assert profile_resp.status_code == 200
        expenses = _expense_json(profile_resp)

        edited = next((e for e in expenses if e["id"] == expense_id), None)
        assert edited is not None, "edited expense must still be present on /profile"
        assert edited["description"] == new_description
        assert edited["amount"] == pytest.approx(88.00)
        assert edited["category"] == "Shopping"
        assert edited["date"] == "2026-06-22"

        after_summary = get_expense_summary(user_id)
        assert after_summary["count"] == before_summary["count"]
        assert after_summary["total"] == pytest.approx(
            before_summary["total"] - 10.00 + 88.00
        )
    finally:
        _delete_test_expense(new_description)
        _delete_test_expense(original_description)  # safety net if update failed


# --- DoD 5: invalid amount re-renders with an error, row untouched -------- #

@pytest.mark.parametrize("bad_amount", ["", "not-a-number", "0", "-5"])
def test_invalid_amount_rerenders_form_without_modifying_row(bad_amount):
    """DoD 5: POST with a missing/blank/non-numeric amount or amount <= 0
    re-renders the form (200) with a visible error and does not modify
    the row."""
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("bad-amount")
    expense_id = create_expense(user_id, 15.00, "Food", "2026-06-01", description)

    try:
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_payload(
                _unique_description("bad-amount-attempt"), amount=bad_amount
            ),
        )
        assert resp.status_code == 200
        assert b"auth-error" in resp.data

        unchanged = get_expense_by_id(expense_id, user_id)
        assert unchanged["amount"] == pytest.approx(15.00)
        assert unchanged["category"] == "Food"
        assert unchanged["date"] == "2026-06-01"
        assert unchanged["description"] == description
    finally:
        _delete_test_expense(description)


# --- DoD 6: invalid category / malformed date re-render, row untouched --- #

@pytest.mark.parametrize("bad_category", ["", "NotACategory", "food"])
def test_invalid_category_rerenders_form_without_modifying_row(bad_category):
    """DoD 6: POST with an invalid category re-renders with an error and
    does not modify the row."""
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("bad-category")
    expense_id = create_expense(user_id, 15.00, "Food", "2026-06-01", description)

    try:
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_payload(
                _unique_description("bad-category-attempt"), category=bad_category
            ),
        )
        assert resp.status_code == 200
        assert b"auth-error" in resp.data

        unchanged = get_expense_by_id(expense_id, user_id)
        assert unchanged["amount"] == pytest.approx(15.00)
        assert unchanged["category"] == "Food"
        assert unchanged["date"] == "2026-06-01"
        assert unchanged["description"] == description
    finally:
        _delete_test_expense(description)


@pytest.mark.parametrize("bad_date", ["", "not-a-date", "07-15-2026", "2026-13-40"])
def test_invalid_date_rerenders_form_without_modifying_row(bad_date):
    """DoD 6: POST with a malformed date re-renders with an error and does
    not modify the row."""
    client = _logged_in_client()
    user_id = _demo_user_id()
    description = _unique_description("bad-date")
    expense_id = create_expense(user_id, 15.00, "Food", "2026-06-01", description)

    try:
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_payload(
                _unique_description("bad-date-attempt"), date=bad_date
            ),
        )
        assert resp.status_code == 200
        assert b"auth-error" in resp.data

        unchanged = get_expense_by_id(expense_id, user_id)
        assert unchanged["amount"] == pytest.approx(15.00)
        assert unchanged["category"] == "Food"
        assert unchanged["date"] == "2026-06-01"
        assert unchanged["description"] == description
    finally:
        _delete_test_expense(description)


# --- DoD 7: another user's expense, or a non-existent id, is a 404 -------- #

def test_edit_get_and_post_for_another_users_expense_returns_404():
    """DoD 7: GET or POST for an expense owned by another user returns 404
    and does not read/modify the row."""
    other_email = _unique_email("owner")
    other_user_id = create_user("Other Owner", other_email, "password123")
    other_description = _unique_description("other-owner")
    other_expense_id = create_expense(
        other_user_id, 50.00, "Food", "2026-06-05", other_description
    )

    client = _logged_in_client()  # logged in as the demo user, not the owner

    try:
        get_resp = client.get(f"/expenses/{other_expense_id}/edit")
        assert get_resp.status_code == 404

        post_resp = client.post(
            f"/expenses/{other_expense_id}/edit",
            data=_valid_payload(_unique_description("other-owner-attempt")),
        )
        assert post_resp.status_code == 404

        untouched = get_expense_by_id(other_expense_id, other_user_id)
        assert untouched is not None
        assert untouched["amount"] == pytest.approx(50.00)
        assert untouched["category"] == "Food"
        assert untouched["date"] == "2026-06-05"
        assert untouched["description"] == other_description
    finally:
        _delete_test_expense(other_description)
        _delete_test_user(other_email)


def test_edit_get_and_post_for_nonexistent_expense_returns_404():
    """DoD 7: GET or POST for a non-existent expense id returns 404."""
    client = _logged_in_client()

    get_resp = client.get(f"/expenses/{NONEXISTENT_EXPENSE_ID}/edit")
    assert get_resp.status_code == 404

    post_resp = client.post(
        f"/expenses/{NONEXISTENT_EXPENSE_ID}/edit",
        data=_valid_payload(_unique_description("nonexistent-attempt")),
    )
    assert post_resp.status_code == 404


# --- DoD 8: logged-out POST does not modify the row, redirects to /login - #

def test_edit_post_requires_login():
    """DoD 8: POST /expenses/<id>/edit while logged out does not modify any
    row and redirects to /login."""
    user_id = _demo_user_id()
    description = _unique_description("logged-out-setup")
    expense_id = create_expense(user_id, 20.00, "Food", "2026-06-01", description)

    client = _client()  # not logged in

    try:
        resp = client.post(
            f"/expenses/{expense_id}/edit",
            data=_valid_payload(_unique_description("logged-out-attempt")),
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

        unchanged = get_expense_by_id(expense_id, user_id)
        assert unchanged["amount"] == pytest.approx(20.00)
        assert unchanged["category"] == "Food"
        assert unchanged["date"] == "2026-06-01"
        assert unchanged["description"] == description
    finally:
        _delete_test_expense(description)


# --- DoD 9: profile.html exposes the Actions column + an edit-url hook --- #

def test_profile_has_actions_column_and_edit_url_template_hook():
    """DoD 9: the profile transactions table has an Actions column header,
    and the server-rendered markup exposes a data-edit-url template so the
    JS-built per-row Edit link is not a hardcoded /expenses/<id>/edit path."""
    client = _logged_in_client()
    resp = client.get("/profile")
    assert resp.status_code == 200

    body = resp.data.decode()
    assert "Actions" in body

    match = re.search(r'data-edit-url="([^"]+)"', body)
    assert match is not None, "profile.html must expose a data-edit-url template hook"

    edit_url_template = match.group(1)
    assert edit_url_template.startswith("/expenses/")
    assert edit_url_template.endswith("/edit")
