# Spec: Edit Expense

## Overview
Edit Expense turns the `GET /expenses/<id>/edit` stub into a working feature so a
logged-in user can change an expense they previously recorded. It presents a
pre-filled form (amount, category, date, optional description) mirroring the
add-expense flow, validates the submission server-side, updates the matching row
in the `expenses` table — scoped to the current user — and redirects back to the
profile dashboard where the change is reflected. This is the second spec to touch
the expense **write** path: Step 06 added the create path; this step adds the
update path and completes the "read → create → update" loop before delete
(Step 9). Ownership enforcement is central here — a user must never be able to
view or edit another user's expense.

## Depends on
- **Step 01 — Database setup**: `expenses` table + `get_db()` with
  `PRAGMA foreign_keys = ON` (`database/db.py:11-16`, `database/db.py:33-45`).
- **Step 03 — Login and logout**: `session["user_id"]` must exist; the route is
  gated behind it.
- **Step 04/05 — Profile page**: the redirect target after a successful edit and
  where the change is displayed (`get_expenses` / `get_expense_summary`).
- **Step 06 — Add expense**: this spec mirrors its route logic, validation,
  `CATEGORIES` list, template, and DB helper house style (`app.py:139-185`,
  `templates/add_expense.html`, `create_expense` at `database/db.py:149-164`).

## Routes
- `GET, POST /expenses/<int:id>/edit` — GET fetches the expense (scoped to the
  logged-in user) and renders the edit form pre-filled with its current values;
  POST validates the submission and, on success, updates that expense then
  redirects to `/profile`. On validation failure it re-renders the form with an
  `error` message and the submitted values. If the expense does not exist or is
  not owned by the session user, respond with `abort(404)`. **Logged-in only.**

The current stub is `GET`-only and returns a raw string (`app.py:188-190`):
```python
@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"
```
It must be changed to `methods=["GET", "POST"]` and render a template (per
CLAUDE.md: "Never use raw string returns for stub routes once a step is
implemented").

## Database changes
**No schema changes.** The `expenses` table already has every needed column
(`database/db.py:33-45`):

```
id INTEGER PK | user_id INTEGER NOT NULL FK→users(id) | amount REAL NOT NULL
| category TEXT NOT NULL | date TEXT NOT NULL | description TEXT (nullable)
| created_at TEXT DEFAULT (datetime('now'))
```

Two new **DB helpers** must be added to `database/db.py` (code, not schema
changes), both mirroring the existing house style (`get_db()`, parameterized
query, `conn.commit()` for writes, `try/finally: conn.close()`):

- `get_expense_by_id(expense_id, user_id)` — returns a single expense row (or
  `None`) using `SELECT id, amount, category, date, description FROM expenses
  WHERE id = ? AND user_id = ?`. Scoping by **both** `id` and `user_id` enforces
  ownership at the query level. Model on `get_user_by_id` (`database/db.py:97-104`).
- `update_expense(expense_id, user_id, amount, category, date, description)` —
  runs `UPDATE expenses SET amount = ?, category = ?, date = ?, description = ?
  WHERE id = ? AND user_id = ?`, then `conn.commit()`. The `WHERE ... AND
  user_id = ?` clause is a second ownership guard. Do **not** touch `id`,
  `user_id`, or `created_at`. Model on `create_expense` (`database/db.py:149-164`).

## Templates
- **Create:**
  - `templates/edit_expense.html` — extends `base.html`. Clone of
    `templates/add_expense.html` with these differences:
    - `{% block title %}` → "Edit Expense — Spendly"; heading/subtitle reworded
      for editing.
    - `<form method="POST" action="{{ url_for('edit_expense', id=expense.id) }}">`.
    - Every field pre-filled from the fetched expense (e.g.
      `value="{{ amount or expense.amount }}"`, and the `<select>` marks the
      current category `selected`). On re-render after a validation error, the
      submitted values take precedence over the stored ones.
    - Submit button reads "Save changes".
    - Keeps the `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}`
      convention (no `flash`).
    - "Back to dashboard" link via `url_for('profile')`.
- **Modify:**
  - `templates/profile.html` — add an `Edit` affordance to each transaction row.
    **Constraint:** the transactions table body is rendered client-side by
    `static/js/profile.js` `renderTable()` (the `<tbody id="txn-body">` is empty
    in Jinja and populated from the `#expense-data` JSON block), so the header
    column is added here and the per-row link is built in JS (see Files to
    change). Add one `<th>` (e.g. "Actions") to the static `<thead>`. Keep the
    change minimal — do not restructure the existing table or the
    `#expense-data` block (frozen by Step 05).

## Files to change
- `app.py` — implement the `edit_expense(id)` route: change to
  `methods=["GET", "POST"]`; add the session guard (mirror `profile` /
  `add_expense`: if `session.get("user_id")` is `None`, redirect to `login`);
  fetch via `get_expense_by_id(id, user_id)` and `abort(404)` if `None`; on GET
  render `edit_expense.html` pre-filled; on POST validate identically to
  `add_expense` (reuse the module-level `CATEGORIES`, `amount` as float `> 0`,
  `datetime.strptime(date, "%Y-%m-%d")`), call `update_expense(...)`, then
  `redirect(url_for("profile"))`; on validation failure re-render with `error=`
  and the submitted values. Add `abort` to the `flask` import and
  `get_expense_by_id`, `update_expense` to the `database.db` import.
- `database/db.py` — add `get_expense_by_id(...)` and `update_expense(...)`.
- `templates/profile.html` — add the "Actions" `<th>` to the transactions table
  header (see Templates → Modify).
- `static/js/profile.js` — in `renderTable()`, append a 5th `<td>` per row
  containing an Edit link built from `e.id`. Because URLs built in JS cannot call
  `url_for()`, inject a URL template from the server (recommended: a
  `data-edit-url-template` attribute or a second JSON block holding
  `url_for('edit_expense', id=0)` with the `0` replaced per row) rather than
  hardcoding the `/expenses/<id>/edit` path. **Flag:** hardcoding the path in JS
  would violate the "never hardcode URLs" convention — prefer the injected
  template. Keep the change scoped to adding the Actions cell.
- `CLAUDE.md` — update the route table row
  `| \`GET /expenses/<id>/edit\` | Stub — Step 8 |` to reflect it is now
  implemented (GET+POST, session-protected, renders `edit_expense.html`, updates
  an expense).

## Files to create
- `templates/edit_expense.html` — the pre-filled edit form page.
- `static/css/edit-expense.css` — page-specific styles, **only if** the edit form
  needs anything beyond what `add-expense.css` already covers (the `<select>` /
  optional-label rules). If not, reuse `add-expense.css` via the `head` block and
  do not create this file. No inline `<style>`.
- `tests/test_07-edit-expense.py` — pytest coverage (see Definition of done),
  following the existing `tests/test_NN-slug.py` naming.

## New dependencies
No new dependencies. `flask`, `werkzeug`, `pytest`, `pytest-flask` already cover
this feature (`requirements.txt`).

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only (`?` placeholders) — never f-strings in SQL.
- DB logic lives in `database/db.py` only — never inline SQL in the route.
- Passwords hashed with werkzeug (unchanged here; no auth code added).
- Use CSS variables from `style.css` `:root` — never hardcode hex values.
- All templates extend `base.html`; every internal link uses `url_for()` (in
  JS, inject the URL from the server rather than hardcoding a path).
- New/updated route goes in `app.py` only — no blueprints.
- Auth guard: if `session.get("user_id")` is `None`, redirect to `login`
  (mirror the inline pattern in `profile` / `add_expense`; there is no
  `@login_required`).
- **Ownership enforcement (critical):** the expense is always fetched and updated
  with `WHERE id = ? AND user_id = ?` using the session `user_id`. A request to
  edit an expense that does not exist, or belongs to another user, must
  `abort(404)` — never leak or mutate another user's data. The `user_id` must
  come only from the session, never from the form.
- Server-side validation (identical to add-expense; do not trust the client):
  - `amount` must parse as a float and be `> 0`; reject otherwise.
  - `category` must be one of the 7 canonical categories (reuse the existing
    module-level `CATEGORIES`).
  - `date` must be a valid `YYYY-MM-DD` string (validate with
    `datetime.strptime`).
  - `description` is optional; store `None` for empty (nullable column).
  - On any failure, re-render the form with `error=` and the submitted values —
    do not write a partial/invalid update.
- Use `abort()` for HTTP errors rather than bare string returns.
- Keep the existing `error=`-template-variable convention — do **not** introduce
  `flash()`.

## Definition of done
Verifiable by running the app (`python app.py`, port 5001) and `pytest`:

1. `GET /expenses/<id>/edit` while **logged out** redirects to `/login` (302).
2. `GET /expenses/<id>/edit` while **logged in**, for an expense the user owns,
   returns 200 and renders the form pre-filled with that expense's amount,
   category (correct option `selected`), date, and description.
3. `POST /expenses/<id>/edit` with valid data updates exactly that one row
   (amount/category/date/description changed) and redirects (302) to `/profile`;
   no new row is created and `id`, `user_id`, `created_at` are unchanged.
4. The edited values appear on `/profile` and the summary count is unchanged
   while the total reflects any amount change.
5. `POST` with a missing/blank/non-numeric amount or amount `<= 0` re-renders the
   form (200) with a visible error and does **not** modify the row.
6. `POST` with an invalid category or malformed date re-renders with an error and
   does **not** modify the row.
7. `GET` or `POST /expenses/<id>/edit` for an expense owned by **another user**,
   or a non-existent id, returns **404** and does not read/modify the row.
8. `POST /expenses/<id>/edit` while logged out does not modify any row and
   redirects to `/login`.
9. The profile transactions table shows an "Edit" link per row that resolves to
   `/expenses/<that row's id>/edit`; the link URL is not a hardcoded string in a
   way that violates the `url_for()` convention.
10. No hardcoded hex colors in `edit_expense.html` / any new CSS; the template
    extends `base.html` and all internal links use `url_for()`.
11. The CLAUDE.md route table no longer lists `/expenses/<id>/edit` as a stub.
