# Spec: Login and Logout

## Overview
This step turns Spendly's existing `login.html` form into a working
authentication flow and implements session-based logout. Registration
(Step 02) already creates accounts and hashes passwords, but there is
currently no way to sign in: `/login` is `GET`-only and no `session` or
`secret_key` exists anywhere in the app. Step 03 introduces Flask
session management for the first time — verifying credentials against the
`users` table with `check_password_hash`, persisting the logged-in user in
the session on success, and clearing that session on logout. This is the
gateway feature that every logged-in page (profile, expenses) will depend
on in later steps.

## Depends on
- **Step 01 — Database setup**: `get_db()`, `users` table, and the
  `get_user_by_email(email)` helper must exist. (Complete.)
- **Step 02 — Registration**: accounts must be creatable so there are
  credentials to log in with; `password_hash` is written via
  `werkzeug.security.generate_password_hash`. (Complete.)

## Routes
- `POST /login` — verify submitted email + password against the `users`
  table; on success store the user id in `session` and redirect to
  `/profile`; on failure re-render `login.html` with an error — public
- `GET /login` — render the login form (already implemented; keep as-is,
  extend the handler to accept `POST`) — public
- `GET /logout` — clear the session and redirect to `/login` — logged-in
  (harmless if called while logged out; just clears an empty session)

No other new routes.

## Database changes
No database changes. The `users` table already has `email` and
`password_hash`, and `get_user_by_email(email)` already returns the row.
Do **not** add columns, tables, or new DB helpers — login only reads.

## Templates
- **Create:** none.
- **Modify:**
  - `templates/login.html` — change the hardcoded `action="/login"` to
    `action="{{ url_for('login') }}"` to satisfy the `url_for` rule. The
    existing `{% if error %}<div class="auth-error">{{ error }}</div>{% endif %}`
    block and the `email` / `password` field names already match this
    spec — reuse them, do not rename.
  - `templates/base.html` — make the nav reflect auth state: when
    `session` contains a logged-in user, show a **Log out** link
    (`url_for('logout')`) in place of / alongside "Sign in" and
    "Get started"; otherwise show the existing links unchanged. Use
    `url_for()` for the logout link — never hardcode.

## Files to change
- `app.py` — add `session` (and `abort` if needed) to the Flask import;
  set `app.secret_key`; extend the `login()` view to handle `POST` with
  credential verification; implement the `logout()` view to clear the
  session.
- `templates/login.html` — fix the form `action` to use `url_for`.
- `templates/base.html` — conditional auth-aware nav with a logout link.
- `CLAUDE.md` — update the route status table: `/login` → "Implemented —
  GET renders form, POST authenticates"; `/logout` → "Implemented".

## Files to create
- `tests/test_login.py` — first test file for the auth flow (see
  Definition of done). `tests/` does not exist yet; create it. Test
  tooling (`pytest`, `pytest-flask`) is already in `requirements.txt`.

## New dependencies
No new dependencies. `werkzeug` (for `check_password_hash`), `flask`,
`pytest`, and `pytest-flask` are all already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs — use `get_db()` / the existing
  `get_user_by_email` helper with parameterised queries only.
- Parameterised queries only (`?` placeholders) — never f-strings in SQL.
- Passwords verified with `werkzeug.security.check_password_hash`
  against the stored `password_hash` — never compare plaintext, never
  re-hash and string-compare.
- No new DB logic inside route functions — reuse `get_user_by_email`
  from `database/db.py`.
- Use CSS variables — never hardcode hex values. Login errors reuse the
  existing `.auth-error` class (backed by `--danger` / `--danger-light`).
- All templates extend `base.html`.
- Every internal link uses `url_for()` — including the login form
  `action` and the new logout nav link.
- Set `app.secret_key` on the app (a module-level constant is acceptable
  for this local project); do not introduce a new config framework or
  pip package to manage it.
- Keep each view single-responsibility; use the same error-message
  pattern as Step 02 (generic "Invalid email or password" — do not
  reveal whether the email exists).
- App stays on port 5001.

## Definition of done
- [ ] `app.secret_key` is set; the app starts with `python app.py` on
      port 5001 without error.
- [ ] Submitting the login form at `/login` with the seed account
      (`demo@spendly.com` / `demo123`) redirects to `/profile` and a
      logged-in session is established.
- [ ] Submitting wrong credentials (bad password OR unknown email)
      re-renders `login.html` showing the `.auth-error` message and does
      **not** create a session.
- [ ] With no session, visiting `/login` still renders the form (GET
      path unchanged).
- [ ] When logged in, `base.html` nav shows a working **Log out** link;
      when logged out it shows "Sign in" / "Get started".
- [ ] `GET /logout` clears the session and redirects to `/login`;
      afterwards the nav shows the logged-out links again.
- [ ] The login form `action` and the logout nav link both render via
      `url_for()` (no hardcoded paths in the templates).
- [ ] `pytest tests/test_login.py` passes: covers successful login,
      failed login (no session, error shown), and logout clearing the
      session.
