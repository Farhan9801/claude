# Spec: Profile Page Design

## Overview
The Profile Page gives a logged-in user a place to see their own account
details — their name, email, and when the account was created — behind
authentication. It is the first page in the Spendly roadmap that lives
entirely behind the login gate built in Step 03, converting the existing
`GET /profile` stub into a real, session-protected page. It establishes the
reusable "logged-in only" access pattern (and the `get_user_by_id` data
helper) that every later logged-in page — Add/Edit/Delete Expenses — will
reuse.

## Depends on
- **Step 01 — Database setup**: `users` table and `get_db()` / connection
  helpers in `database/db.py`.
- **Step 02 — Registration**: `create_user`, so real accounts exist to view.
- **Step 03 — Login and logout**: the session mechanism. This page reads
  `session["user_id"]` set by the login flow and redirects unauthenticated
  visitors back to `/login`.

## Routes
- `GET /profile` — renders the logged-in user's profile (name, email,
  account-created date) by looking up `session["user_id"]`. If no user is
  logged in, redirect to `GET /login`. — **logged-in only**

No other new routes. This converts the existing stub at `app.py:99-101`.

## Database changes
No schema changes. The `users` table already has every field the page needs
(`id`, `name`, `email`, `password_hash`, `created_at`).

**New DB helper required** (data-access only, not a schema change): add
`get_user_by_id(user_id)` to `database/db.py`. No lookup-by-id helper exists
today — only `get_user_by_email`. Per the "all DB logic lives in
`database/db.py`" rule, the route must not run inline SQL. The helper runs a
parameterized `SELECT * FROM users WHERE id = ?` and returns the row or
`None`.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; overrides `title`,
    `head` (to load the page-specific stylesheet), and `content` to display
    the user's name, email, and formatted account-created date.
- **Modify:**
  - `templates/base.html` — add a "Profile" nav link (using
    `url_for('profile')`) inside the existing `{% if session.user_id %}`
    branch of the nav, alongside "Log out".

## Files to change
- `app.py` — replace the `/profile` stub (`app.py:99-101`) with a real route:
  read `session.get("user_id")`, redirect to `login` if absent, fetch the
  user via `get_user_by_id`, and `render_template("profile.html", user=...)`.
  Add `get_user_by_id` to the existing `from database.db import ...` line.
- `database/db.py` — add the `get_user_by_id(user_id)` helper.
- `templates/base.html` — add the Profile nav link.

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles for the profile page,
  loaded via `{% block head %}` in `profile.html`.
- `tests/test_profile.py` — tests for the route (see Definition of done).

## New dependencies
No new dependencies. `pytest` / `pytest-flask` are already present from
earlier steps.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only (`?` placeholders) — never f-strings in SQL.
- Passwords hashed with werkzeug — never render or expose `password_hash`
  in the template or the route response.
- Use CSS variables (as defined in `static/css/style.css`) — never hardcode
  hex values in `profile.css`.
- All templates extend `base.html`.
- All DB access goes through a helper in `database/db.py` — no inline SQL in
  the route.
- Use `url_for()` for every internal link — never hardcode URLs.
- Flask only, SQLite only, vanilla JS only — no new pip packages.
- The route has a single responsibility: authenticate, fetch, render.
- Access control: if `session.get("user_id")` is missing, redirect to
  `url_for("login")`. If the id is present but no matching user row is found
  (stale session), `session.clear()` and redirect to `login`.

## Definition of done
- Running the app on port 5001, visiting `/profile` while **logged out**
  redirects to `/login`.
- After logging in (e.g. `demo@spendly.com` / `demo123`), visiting
  `/profile` renders `profile.html` showing the correct name, email, and a
  human-readable account-created date.
- The rendered page does **not** contain the `password_hash` value.
- The nav bar shows a working "Profile" link only while logged in; it is
  absent when logged out.
- `get_user_by_id` exists in `database/db.py`, uses a parameterized query,
  and returns `None` for a nonexistent id.
- `pytest tests/test_profile.py` passes: covers (a) logged-out redirect to
  login, (b) logged-in render showing the user's name/email, (c)
  password_hash not present in the response body.
- No inline SQL in `app.py`; no hardcoded URLs in templates; no hardcoded
  hex values in `profile.css`.