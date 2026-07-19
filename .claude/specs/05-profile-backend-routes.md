# Spec: Backend Routes for Profile Page

## Overview
This step formalizes and hardens the backend that feeds the profile dashboard.
The `GET /profile` route and its DB helpers (`get_user_by_id`,
`get_expense_summary`, `get_expenses`) were implemented ahead of this spec and
already ship on `main`, but the data contract was never written down, the route
leaks the full user row (including `password_hash`) into the template context,
there is no `tests/test_profile.py`, and CLAUDE.md still describes `/profile`
as a stub and `database/db.py` as empty. Step 05 locks in the backend contract
the frontend (`profile.html` + `profile.js`) depends on, closes the
`password_hash` exposure, adds the missing tests, and syncs the docs. No JSON
or AJAX endpoint is added — `profile.js` performs no fetch calls; all data is
server-rendered.

## Depends on
- Step 01 — Database setup (`get_db`, `init_db`, `seed_db`, `users` + `expenses` schema)
- Step 03 — Login and logout (`session["user_id"]` is set on login)
- Step 04 — Profile page design (`profile.html`, `profile.css`, `profile.js`)

## Routes
No new routes. This step finalizes the existing `GET /profile` (logged-in only) contract:

- Reads `session["user_id"]`; if absent, redirect to `url_for("login")`.
- If the session user id no longer matches a user (stale session), call
  `session.clear()` and redirect to `url_for("login")`.
- Template context passed to `profile.html`:
  - `user` — **safe fields only**: `name`, `email` (never `password_hash`, never the raw DB row)
  - `member_since` — `created_at` formatted as `"%B %d, %Y"` (e.g. "June 05, 2026")
  - `summary` — `{"count": int, "total": float}` from `get_expense_summary`
  - `expenses` — list of dicts with exactly `id`, `amount`, `category`, `date`
    (`YYYY-MM-DD`), `description` (nullable), newest first — embedded in the
    page as JSON via the existing `<script type="application/json" id="expense-data">` block

## Database changes
No database changes. All required helpers already exist in `database/db.py`:
`get_user_by_id`, `get_expense_summary`, `get_expenses`. Do not add tables or columns.

## Templates
- **Create:** none
- **Modify:** none — `templates/profile.html` already consumes `user["name"]`,
  `user["email"]`, `member_since`, and the `expenses|tojson` block, all of which
  keep working when `user` becomes a safe-fields dict (it uses subscript access)

## Files to change
- `app.py` — in the `profile` view, build a safe `user` context dict
  (`name`, `email`) instead of passing the raw `sqlite3.Row`; no other behavior changes
- `CLAUDE.md` — route table: mark `GET /profile` as Implemented; remove the
  stale "`database/db.py` is currently empty" warning

## Files to create
- `tests/test_profile.py` — backend tests for the `/profile` contract (see Definition of done)

## New dependencies
No new dependencies. Tests use the already-installed `pytest` + `pytest-flask`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings in SQL
- Passwords hashed with werkzeug — `password_hash` must never reach a template context or response body
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic stays in `database/db.py` — no SQL in `app.py`
- Do not touch the `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` stubs (Steps 7–9)
- Do not modify `templates/profile.html`, `static/js/profile.js`, or `static/css/profile.css` — the frontend contract is fixed
- Do not add JSON/AJAX endpoints — the page is server-rendered
- Use `url_for()` for every redirect target; `abort()` for HTTP errors
- App stays on port 5001

## Definition of done
- [ ] Logged-out `GET /profile` responds 302 to `/login`
- [ ] After logging in (e.g. seeded `demo@spendly.com` / `demo123`), `GET /profile` responds 200 and the page shows the user's name and email
- [ ] "Member since" renders in `"%B %d, %Y"` format
- [ ] The response contains `<script type="application/json" id="expense-data">` whose JSON is a list of objects with keys `id`, `amount`, `category`, `date`, `description`, ordered newest first
- [ ] The string `password_hash` (and the stored hash value) appears nowhere in the `/profile` response body
- [ ] A session pointing at a deleted user id is cleared and redirected to `/login`
- [ ] `pytest` passes, including the new `tests/test_profile.py` covering every item above
- [ ] CLAUDE.md route table lists `GET /profile` as Implemented and no longer claims `database/db.py` is empty
- [ ] `python app.py` still serves on port 5001 with the profile dashboard fully working
