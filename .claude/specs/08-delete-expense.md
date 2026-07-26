# Spec: Delete Expense

## Overview
Delete Expense turns the `GET /expenses/<id>/delete` stub into a working feature so
a logged-in user can permanently remove an expense they previously recorded. `GET`
renders a small confirmation page showing the expense about to be deleted; `POST`
performs the delete — scoped to the current user — and redirects back to the
profile dashboard, where the row disappears and the summary count/total drop
accordingly. This completes the expense CRUD loop started in Step 05 (read),
Step 06 (create) and Step 07 (update), and it is the last route in the CLAUDE.md
table still returning a raw string. Ownership enforcement is central: a user must
never be able to delete — or even see the details of — another user's expense.

> **Numbering note:** this is spec file `08`, but the CLAUDE.md route table and the
> current stub string both label delete as **"Step 9"** (spec files have run one
> behind the step labels since edit expense was written as spec `07`). Same
> feature, two labels. When updating CLAUDE.md, just mark the route implemented —
> do not renumber the table.

## Depends on
- **Step 01 — Database setup**: `expenses` table + `get_db()` with
  `PRAGMA foreign_keys = ON` (`database/db.py:11-16`, `database/db.py:33-45`).
- **Step 03 — Login and logout**: `session["user_id"]` must exist; the route is
  gated behind it.
- **Step 04/05 — Profile page**: the redirect target after a successful delete, and
  where the removal is reflected (`get_expenses` / `get_expense_summary`). The
  `#expense-data` JSON contract frozen by Step 05 must not change.
- **Step 07 — Edit expense**: this spec reuses its ownership-scoped fetch
  (`get_expense_by_id` at `database/db.py:167-179`), its `abort(404)` pattern
  (`app.py:196-198`), its DB write-helper house style (`update_expense` at
  `database/db.py:182-198`), and its per-row action affordance in
  `static/js/profile.js` `renderTable()` (`static/js/profile.js:388-394`).

## Routes
- `GET, POST /expenses/<int:id>/delete` — GET fetches the expense (scoped to the
  logged-in user) and renders a confirmation page showing its amount, category,
  date and description with a "Delete expense" submit button and a "Cancel" link
  back to `/profile`; POST deletes that expense and redirects to `/profile`. If the
  expense does not exist or is not owned by the session user, respond with
  `abort(404)` — for **both** methods. Logged out, both methods redirect to
  `/login` without touching any row. **Logged-in only.**

The current stub is `GET`-only and returns a raw string (`app.py:250-252`):
```python
@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"
```
It must become `methods=["GET", "POST"]` and render a template (per CLAUDE.md:
"Never use raw string returns for stub routes once a step is implemented").

**Why the delete happens on POST, not GET (decide this once, here):** the stub's
URL is reached from a plain `<a>` link, and a destructive action behind a bare GET
is unsafe — browser prefetch, a crawler, or an `<img src>` on any page could wipe a
row, and there is no CSRF protection anywhere in this app (no Flask-WTF, no token).
So GET is read-only (the confirmation page) and the actual `DELETE` runs only on
POST from a real `<form method="POST">`. Do **not** implement a one-click GET
delete, and do **not** add a CSRF library — that is out of scope for this step.

## Database changes
**No schema changes.** The `expenses` table already has every needed column, and
the `user_id` foreign key is a plain inline `REFERENCES users(id)` with no
`ON DELETE` clause (`database/db.py:33-45`) — deleting an *expense* row has no FK
consequences (the FK only constrains deleting a *user*), so no cascade rule is
needed.

One new **DB helper** must be added to `database/db.py` (code, not a schema
change), mirroring the existing house style (`get_db()`, parameterized query,
`conn.commit()`, `try/finally: conn.close()`):

- `delete_expense_by_id(expense_id, user_id)` — runs
  `DELETE FROM expenses WHERE id = ? AND user_id = ?`, then `conn.commit()`, and
  returns `cursor.rowcount` (`0` when the row does not exist or is not owned).
  Model on `update_expense` (`database/db.py:182-198`). The `AND user_id = ?`
  clause is a second ownership guard behind the route's `get_expense_by_id` check.
  **Name it `delete_expense_by_id`, not `delete_expense`** — `delete_expense` is
  already the route function name in `app.py`, and importing a DB helper of the
  same name into `app.py` would shadow it and break the route.

No changes to `get_expense_by_id`, `get_expenses`, or `get_expense_summary` — the
summary recomputes from the table on the next `/profile` load.

## Templates
- **Create:**
  - `templates/delete_expense.html` — the confirmation page. Extends `base.html`.
    Structurally a slimmed-down `edit_expense.html` (`templates/edit_expense.html`)
    reusing the same `.auth-section` / `.auth-container` / `.auth-header` /
    `.auth-card` wrappers:
    - `{% block title %}` → "Delete Expense — Spendly"; heading/subtitle worded as
      a confirmation ("Delete this expense?" / "This can't be undone.").
    - A read-only summary of the expense being deleted — amount, category, date,
      description (show a dash or "—" when description is empty). Plain markup,
      **no form inputs** for these values; nothing about the expense is editable
      here.
    - `<form method="POST" action="{{ url_for('delete_expense', id=expense_id) }}">`
      containing a single submit button labelled "Delete expense".
    - A "Cancel" link to `url_for('profile')` (mirror the existing
      `<p class="auth-switch">` back-link at `templates/edit_expense.html:48`).
    - No `error=` block is needed (there is no user input to validate), so do not
      add one, and do not introduce `flash()`.
- **Modify:**
  - `templates/profile.html` — add a second server-injected URL template to the
    transactions `<tbody>` so JS can build per-row delete links without hardcoding
    a path. The `<tbody>` currently reads (`templates/profile.html:105`):
    ```html
    <tbody id="txn-body" data-edit-url="{{ url_for('edit_expense', id=0) }}"></tbody>
    ```
    Add `data-delete-url="{{ url_for('delete_expense', id=0) }}"` alongside it.
    The "Actions" `<th>` already exists (`templates/profile.html:102`) — **no other
    change to this template.** Do not restructure the table and do not touch the
    `#expense-data` block (frozen by Step 05).

## Files to change
- `app.py` — implement the `delete_expense(id)` route: change the decorator to
  `methods=["GET", "POST"]`; add the session guard (mirror `profile` /
  `edit_expense`: if `session.get("user_id")` is `None`, redirect to `login`);
  fetch via `get_expense_by_id(id, user_id)` and `abort(404)` if `None`; on GET
  render `delete_expense.html` with `expense_id=id` plus the expense's fields
  (mirror the flat-variable style used by `edit_expense`'s GET branch at
  `app.py:239-247`, which passes `expense_id` rather than an `expense` object); on
  POST call `delete_expense_by_id(id, user_id)` and
  `return redirect(url_for("profile"))`. Add `delete_expense_by_id` to the
  `database.db` import block (`app.py:7-19`).
- `database/db.py` — add `delete_expense_by_id(expense_id, user_id)` (see Database
  changes).
- `static/js/profile.js` — in `renderTable()`, read the second injected template
  (`body.dataset.deleteUrl`, alongside the existing `editUrlTemplate` at
  `static/js/profile.js:348`) and append a "Delete" link into the **existing**
  `actionTd` cell after the Edit link (`static/js/profile.js:388-394`), built the
  same way: `deleteUrlTemplate.replace("/0/", "/" + e.id + "/")`. Give it a
  `txn-delete-link` class. Because the link points at the GET confirmation page,
  **no `window.confirm` or JS interception is required** — the confirmation is a
  real page. Do not add `fetch`/AJAX (the file is currently pure client-side
  render/filter, and `static/js/main.js` is an empty placeholder). Keep the change
  scoped to adding the one link.
- `static/css/profile.css` — add a `.txn-delete-link` rule next to the existing
  `.txn-edit-link` rules (`static/css/profile.css:463-470`), using
  `color: var(--danger)` and the same weight/`text-decoration` treatment, plus
  spacing between the two action links. **Variables only — no hex values.**
- `CLAUDE.md` — update the route table row
  `| \`GET /expenses/<id>/delete\` | Stub — Step 9 |` (CLAUDE.md:102) to reflect it
  is now implemented (GET+POST, session-protected, renders `delete_expense.html`,
  deletes an expense). Also update the `GET /expenses/<id>/edit` row if it is still
  listed as a stub — Step 07 shipped it but the table was left stale.

## Files to create
- `templates/delete_expense.html` — the confirmation page.
- `static/css/delete-expense.css` — page-specific styles for the confirmation page,
  **only if** needed beyond what `style.css` already provides: a danger-styled
  submit button (there is no `.btn-danger` in the codebase; `.btn-submit` at
  `static/css/style.css:534-549` is `background: var(--ink)`) and the read-only
  expense summary block. Load it via the template's `{% block head %}` with
  `url_for('static', ...)`. If `.btn-submit` plus existing utilities genuinely
  suffice, skip the file. **No inline `<style>` tags either way.**
- `tests/test_08-delete-expense.py` — pytest coverage (see Definition of done),
  following the existing `tests/test_NN-slug.py` naming.

## New dependencies
No new dependencies. `flask==3.1.3`, `werkzeug==3.1.6`, `pytest==8.3.5` and
`pytest-flask==1.3.0` already cover this feature (`requirements.txt`).

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only.
- Parameterised queries only (`?` placeholders) — never f-strings in SQL.
- DB logic lives in `database/db.py` only — never inline SQL in the route.
- Passwords hashed with werkzeug (unchanged here; no auth code added).
- Use CSS variables from the `style.css` `:root` block (`--danger`,
  `--danger-light`, `--border`, `--radius-md`, …) — never hardcode hex values.
- All templates extend `base.html`; every internal link and asset path uses
  `url_for()`. In JS, use the server-injected `data-*` URL template — never
  hardcode `/expenses/<id>/delete`.
- The route goes in `app.py` only — no blueprints. One responsibility per branch:
  GET renders, POST deletes and redirects.
- Auth guard: if `session.get("user_id")` is `None`, redirect to `login` (mirror
  the inline pattern in `profile` / `edit_expense`; there is no `@login_required`).
- **Ownership enforcement (critical):** `user_id` comes only from the session,
  never from the form or query string. The expense is fetched with
  `get_expense_by_id(id, user_id)` and deleted with
  `WHERE id = ? AND user_id = ?`. A non-existent id, or one belonging to another
  user, must `abort(404)` on both GET and POST — never leak another user's expense
  details on the confirmation page and never delete their row.
- **Destructive action safety:** the `DELETE` runs on POST only, from a real form.
  Never delete on GET. No CSRF token is added in this step (the app has none
  anywhere) — note it as a known gap, do not install Flask-WTF.
- Delete exactly one row. Never issue an unfiltered `DELETE FROM expenses`, never
  delete by `id` alone, and never touch the `users` table.
- Use `abort()` for HTTP errors rather than bare string returns.
- Keep the existing `error=`-template-variable convention — do **not** introduce
  `flash()`.
- Tests run against the real shared `expense_tracker.db` (there is no `conftest.py`
  and no temp-DB fixture). Follow `tests/test_07-edit-expense.py`: module-level
  `_client()` / `_logged_in_client()` helpers, uuid-suffixed unique descriptions to
  isolate rows, and `try/finally` cleanup via SQL `DELETE`. Never clean up by
  removing the database file — a `PreToolUse` hook in `.claude/settings.json`
  blocks `rm`/`unlink`/`truncate` against `expense_tracker.db`.

## Definition of done
Verifiable by running the app (`python app.py`, port 5001) and `pytest`:

1. `GET /expenses/<id>/delete` while **logged out** redirects to `/login` (302) and
   deletes nothing.
2. `POST /expenses/<id>/delete` while **logged out** redirects to `/login` (302) and
   the row still exists afterwards.
3. `GET /expenses/<id>/delete` while **logged in**, for an expense the user owns,
   returns 200 and shows that expense's amount, category, date and description,
   plus a `POST` form and a Cancel link to `/profile`. The row is **not** deleted by
   the GET.
4. `POST /expenses/<id>/delete` for an owned expense removes exactly that one row
   and redirects (302) to `/profile`; the user's other expenses are untouched.
5. After the delete, `/profile` no longer lists that expense, the summary `count`
   has dropped by exactly 1, and `total` has dropped by exactly that expense's
   amount.
6. `GET` **and** `POST /expenses/<id>/delete` for an expense owned by **another
   user** both return **404**, and that expense still exists in the DB afterwards.
7. `GET` and `POST /expenses/<id>/delete` for a non-existent id return **404**.
8. `POST` to the same delete URL twice: the first returns 302, the second returns
   404 (the row is gone) — no 500, no stack trace.
9. Deleting a user's last remaining expense leaves `/profile` rendering fine with
   `count` 0 and `total` 0 (no divide-by-zero or template crash in the charts).
10. The profile transactions table shows a "Delete" link per row that resolves to
    `/expenses/<that row's id>/delete`, alongside the existing Edit link; the
    `<tbody>` carries a `data-delete-url` attribute produced by `url_for()` and the
    path is not hardcoded in `static/js/profile.js`.
11. No hardcoded hex colors in `delete_expense.html`, the new `.txn-delete-link`
    rule, or any new CSS; the template extends `base.html` and all internal links
    use `url_for()`.
12. `python app.py` starts clean on port 5001, and the route no longer returns the
    raw `"Delete expense — coming in Step 9"` string anywhere.
13. The CLAUDE.md route table no longer lists `/expenses/<id>/delete` as a stub.
