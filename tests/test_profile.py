import json
import re
from datetime import datetime

import app as spendly_app
from database.db import get_user_by_email

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


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
    assert match is not None, "expense-data JSON block missing from /profile"
    return json.loads(match.group(1))


def test_profile_requires_login():
    client = _client()
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_profile_renders_user_identity():
    client = _logged_in_client()
    resp = client.get("/profile")
    assert resp.status_code == 200

    user = get_user_by_email(DEMO_EMAIL)
    assert user["name"].encode() in resp.data
    assert user["email"].encode() in resp.data


def test_profile_member_since_format():
    client = _logged_in_client()
    resp = client.get("/profile")

    user = get_user_by_email(DEMO_EMAIL)
    expected = datetime.strptime(
        user["created_at"], "%Y-%m-%d %H:%M:%S"
    ).strftime("%B %d, %Y")
    assert f"Member since {expected}".encode() in resp.data


def test_profile_embeds_expense_json():
    client = _logged_in_client()
    resp = client.get("/profile")

    expenses = _expense_json(resp)
    assert isinstance(expenses, list)
    assert len(expenses) > 0

    for expense in expenses:
        assert set(expense.keys()) == {
            "id", "amount", "category", "date", "description",
        }

    dates = [expense["date"] for expense in expenses]
    assert dates == sorted(dates, reverse=True)


def test_profile_never_exposes_password_hash():
    client = _logged_in_client()
    resp = client.get("/profile")

    user = get_user_by_email(DEMO_EMAIL)
    assert b"password_hash" not in resp.data
    assert user["password_hash"].encode() not in resp.data


def test_profile_stale_session_redirects_to_login():
    client = _client()
    with client.session_transaction() as sess:
        sess["user_id"] = 999999

    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess
