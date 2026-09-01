# eDocs / Stalwart Django — Windows local run

From `D:\EDocs\edocs`:

```powershell
.\venv\Scripts\Activate.ps1
cd .\Stalwart_Django_PostgreSQL\
```

Confirm:

```powershell
python --version
python -m pip --version
```

Install:

```powershell
python -m pip install -r requirements.txt
```

Check:

```powershell
python manage.py check
```

Database:

```powershell
python manage.py migrate
python manage.py setup_roles
```

Start:

```powershell
python manage.py runserver 127.0.0.1:8000
```

Open:

`http://127.0.0.1:8000/login/`

## HR flow

Employer registration -> choose Macro Kiosk or InsiteMy -> create account -> login.

The HR account remembers the company. The invitation page does not ask HR to select a company.

Paste candidate emails such as:

```text
candidate1@example.com
candidate2@example.com, candidate3@example.com
candidate4@example.com
```

Each candidate gets an individual invitation.

## Existing user behavior

Registering an email that already belongs to a user returns an existing-user message. It does not create a second account.

For an already-registered candidate, use Login from the invitation and the application opens after authentication.

## Email configuration

The supplied `.env` contains the existing mail configuration. Keep the SMTP password private.

For terminal-only testing:

```text
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

For actual SMTP delivery, configure the existing Gmail SMTP values in `.env`.

The authenticated SMTP account is the actual From address. The HR user's email is used as Reply-To.

## PostgreSQL

Set:

```text
USE_SQLITE=0
POSTGRES_DB=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
```

Then:

```powershell
python manage.py migrate
```

## Temporary SQLite

For a quick machine-local check without PostgreSQL:

```text
USE_SQLITE=1
```

Then:

```powershell
python manage.py migrate
python manage.py setup_roles
python manage.py runserver
```

Switch back to `USE_SQLITE=0` before using your PostgreSQL database.
