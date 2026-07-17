# Spec: Registration

## Overview
This feature turns the existing `/register` page into a working account-creation
flow. Right now `GET /register` only renders a static form; there is no way to
actually create a user. This step adds a `POST /register` handler that validates
the submitted name, email, and password, hashes the password with werkzeug, and
inserts a new row into the `users` table. On success the user is redirected to
the sign-in page; on failure the form re-renders with a clear error message. It
sits at the start of Spendly's auth journey — the data layer (Step 01) already
exists, and this is the first feature that writes real user data, unblocking
login (Step 03) and everything that requires an authenticated user.

## Depends on
- **Step 01 — Database Setup** must be complete. The registration handler calls
  `get_db()` and relies on the `users` table (`id`, `name`, `email` UNIQUE,
  `password_hash`, `created_at`) from `database/db.py`.
  - ⚠️ Note: on the `main`/`feature/registration` branch `database/db.py` is
    still the stub. The implemented version currently lives on the
    `feature/setup_db` branch and must be merged/available before this feature
    can run end-to-end.

## Routes
- `GET /register` — render the registration form (already exists; keep working) — public
- `POST /register` — validate input, create the user, redirect to `/login` on success; re-render the form with an error on failure — public

No other new routes.

## Database changes
No database changes. The `users` table defined in `database/db.py` (Step 01)
already has every column this feature needs. Verified against `database/db.py`:
`id`, `name`, `email` (UNIQUE NOT NULL), `password_hash`, `created_at`.

## Templates
- **Create:** none — `templates/register.html` already exists.
- **Modify:**
  - `templates/register.html` — no structural change required. It already
    `POST`s to `/register`, has `name` / `email` / `password` inputs, and renders
    `{{ error }}` inside `.auth-error`. Only touch it if the success/redirect UX
    needs a message (see Rules); keep sticky field values (`value="{{ name }}"`,
    `value="{{ email }}"`) so the form re-populates on validation error.

## Files to change
- `app.py` — expand the `register` view to accept `GET` and `POST`; add the
  validation + insert logic; add the needed imports (`request`, `redirect`,
  `url_for`) and `from database.db import get_db`.
- `templates/register.html` — only if adding sticky field values (recommended).

## Files to create
- None.

## New dependencies
No new dependencies. `werkzeug` (password hashing) and `flask` are already in
`requirements.txt`; `sqlite3` is standard library.

## Rules for implementation
- No SQLAlchemy or ORMs — use `sqlite3` via `get_db()` from `database/db.py`.
- Parameterised queries only — never string-format values into SQL.
- Passwords hashed with werkzeug (`generate_password_hash`); never store plaintext.
- Use CSS variables — never hardcode hex values (error styling uses `--danger` /
  `--danger-light`, already defined in `static/css/style.css`).
- All templates extend `base.html` (register.html already does).
- Validation (server-side, all cases re-render the form with a specific `error`):
  - name, email, password all required / non-empty (trim whitespace).
  - password minimum length 8 characters.
  - reject duplicate email — check before insert and/or catch the `sqlite3`
    `IntegrityError` from the UNIQUE constraint; show "An account with that email
    already exists." Do not leak a stack trace.
- Normalise email to lowercase and strip whitespace before checking/inserting.
- On success, `redirect(url_for('login'))` (PRG pattern). Do **not** auto-login —
  session handling arrives in Step 03; do not introduce `session` or a
  `secret_key` in this step.
- Close the DB connection in all paths.

## Definition of done
- [ ] `GET /register` renders the form (app starts, page loads at `/register`).
- [ ] Submitting a valid new name/email/password creates exactly one row in the
      `users` table and redirects to `/login`.
- [ ] The stored `password_hash` is a werkzeug hash, not the plaintext password
      (verifiable by inspecting the DB row).
- [ ] Submitting an email that already exists re-renders `/register` with a
      visible "already exists" error and creates no new row.
- [ ] Submitting a password shorter than 8 characters re-renders with an error
      and creates no row.
- [ ] Submitting with any field blank re-renders with an error and creates no row.
- [ ] No plaintext passwords anywhere; all SQL uses parameterised queries.
- [ ] App runs without errors: `python app.py` then exercise the flow at
      `http://127.0.0.1:5001/register`.
