# Spec: Add Expense

## Overview
Add Expense turns the `/expenses/add` stub into a working feature so a logged-in
user can record a new spend. It presents a form (amount, category, date,
optional description), validates the input server-side, writes one row to the
`expenses` table scoped to the current user, and redirects back to the profile
dashboard where the new expense appears. This is the first spec to touch the
expense **write** path — steps 01–05 built the schema, auth, and the read-only
profile dashboard; this step lets users actually create data. It is the
foundation for the edit (Step 8) and delete (Step 9) stubs that follow.

## Depends on
- **Step 01 — Database setup**: `expenses` table + `get_db()` with
  `PRAGMA foreign_keys = ON`.
- **Step 03 — Login and logout**: `session["user_id"]` must exist; the route is
  gated behind it.
- **Step 04/05 — Profile page**: the redirect target and where the new expense
  is displayed (`get_expenses` / `get_expense_summary`).

## Routes
- `GET, POST /expenses/add` — GET renders the add-expense form; POST validates
  the submission and, on success, inserts a new expense for the logged-in user
  then redirects to `/profile`. On validation failure it re-renders the form
  with an `error` message and the previously entered values. **Logged-in only.**

The current stub is `GET`-only (`app.py:133-135`) and must be changed to
`methods=["GET", "POST"]`.

## Database changes
**No schema changes.** The `expenses` table already exists with the required
columns (`db.py:35-44`):

```
id INTEGER PK | user_id INTEGER NOT NULL FK→users(id) | amount REAL NOT NULL
| category TEXT NOT NULL | date TEXT NOT NULL | description TEXT (nullable)
| created_at TEXT DEFAULT (datetime('now'))
```

A new **DB helper** must be added to `database/db.py` (this is code, not a schema
change): `create_expense(user_id, amount, category, date, description)` — inserts
one row and returns `cursor.lastrowid`. It must mirror the `create_user` house
style (`db.py:131-146`): `get_db()`, parameterized `INSERT`, `conn.commit()`,
`try/finally: conn.close()`. Do **not** pass `created_at` — it is DB-defaulted.
Column order to match the existing seed insert (`db.py:77-81`):
`INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)`.

## Templates
- **Create:**
  - `templates/add_expense.html` — extends `base.html`. Mirrors the
    `register.html` / `login.html` form pattern (`auth-section` → `auth-card`
    → `form-group` → `btn-submit`). Fields:
    - `amount` — `<input type="number" step="0.01" min="0.01" required>`
    - `category` — `<select required>` populated with the 7 canonical
      categories: **Food, Transport, Bills, Health, Entertainment, Shopping,
      Other**
    - `date` — `<input type="date" required>`, defaulting to today
    - `description` — optional `<input type="text">` / `<textarea>`
    - Re-renders prior values on error via `value="{{ ... or '' }}"` and shows
      `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}`.
    - Form posts to `{{ url_for('add_expense') }}`.
- **Modify:**
  - `templates/profile.html` — add a primary "Add expense" link/button
    (e.g. near the dashboard header) pointing at `{{ url_for('add_expense') }}`,
    so the feature is reachable. **Note:** this file was frozen by Step 05 —
    keep the change minimal (one link/button, no restructuring of the existing
    read-only table or `#expense-data` JSON block).

## Files to change
- `app.py` — implement the `add_expense` route (GET+POST, auth guard mirroring
  `profile` at `app.py:103-113`, validation, call `create_expense`, redirect to
  `profile`). Add `create_expense` to the `database.db` import. Keep the existing
  `error=`-template-variable convention — do **not** introduce `flash()`.
- `database/db.py` — add the `create_expense(...)` helper.
- `templates/profile.html` — add the "Add expense" entry point (see above).
- `CLAUDE.md` — update the route table row
  `| \`GET /expenses/add\` | Stub — Step 7 |` to reflect it is now implemented
  (renders `add_expense.html`, GET+POST, logged-in only).

## Files to create
- `templates/add_expense.html` — the add-expense form page.
- `static/css/add-expense.css` — page-specific styles (loaded via base.html's
  `head` block), only if the `<select>` / `<input type="date">` / `<textarea>`
  need styling beyond the shared `.form-input` rules. No inline `<style>`.
- `tests/test_add_expense.py` — pytest coverage (see Definition of done).

## New dependencies
No new dependencies. `flask`, `werkzeug`, `pytest`, `pytest-flask` already cover
this feature (`requirements.txt`).

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only (`?` placeholders) — never f-strings in SQL.
- DB logic lives in `database/db.py` only — never inline SQL in the route.
- Passwords hashed with werkzeug (unchanged here; no auth code added).
- Use CSS variables from `style.css` `:root` — never hardcode hex values.
- All templates extend `base.html`; every internal link uses `url_for()`.
- New route goes in `app.py` only — no blueprints.
- Auth guard: if `session.get("user_id")` is `None`, redirect to `login`
  (mirror the inline pattern in `profile`; there is no `@login_required`).
- Server-side validation (do not trust the client):
  - `amount` must parse as a float and be `> 0`; reject otherwise.
  - `category` must be one of the 7 allowed categories (define the list once).
  - `date` must be a valid `YYYY-MM-DD` string (validate with
    `datetime.strptime`); default to today if the design chooses.
  - `description` is optional; store `None`/empty as allowed by the nullable
    column.
  - On any failure, re-render the form with `error=` and the submitted values —
    do not insert a partial/invalid row.
- The inserted `user_id` must come from `session["user_id"]`, never from the
  form — a user can only add expenses for themselves.
- Use `abort()` for HTTP errors rather than bare string returns; add `abort` to
  the flask import only if actually used.

## Definition of done
Verifiable by running the app (`python app.py`, port 5001) and `pytest`:

1. `GET /expenses/add` while **logged out** redirects to `/login` (302).
2. `GET /expenses/add` while **logged in** returns 200 and renders the form with
   an amount field, a category `<select>` showing all 7 categories, a date
   field, and a description field.
3. `POST /expenses/add` with valid data creates exactly one new row in
   `expenses` for the current user and redirects (302) to `/profile`.
4. The newly added expense appears on `/profile` and the summary count/total
   reflect it.
5. `POST` with a missing/blank amount, a non-numeric amount, or amount `<= 0`
   re-renders the form (200) with a visible error and inserts **no** row.
6. `POST` with an invalid/empty category or malformed date re-renders with an
   error and inserts **no** row.
7. `POST /expenses/add` while logged out does not create a row and redirects to
   `/login`.
8. The `expenses.user_id` of the created row equals the session user's id (a
   user cannot create expenses for another user).
9. No hardcoded hex colors in `add_expense.html` / `add-expense.css`; the
   template extends `base.html` and all links use `url_for()`.
10. The CLAUDE.md route table no longer lists `/expenses/add` as a stub.
