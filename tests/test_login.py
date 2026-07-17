import app as spendly_app


def _client():
    spendly_app.app.config["TESTING"] = True
    return spendly_app.app.test_client()


def test_login_success_sets_session_and_redirects():
    client = _client()
    resp = client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    with client.session_transaction() as sess:
        assert sess["user_id"] is not None


def test_login_failure_wrong_password():
    client = _client()
    resp = client.post("/login", data={"email": "demo@spendly.com", "password": "wrongpass"})
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_failure_unknown_email():
    client = _client()
    resp = client.post("/login", data={"email": "nobody@nowhere.com", "password": "whatever"})
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_login_get_renders_form():
    client = _client()
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Welcome back" in resp.data


def test_logout_clears_session_and_redirects():
    client = _client()
    client.post("/login", data={"email": "demo@spendly.com", "password": "demo123"})
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess