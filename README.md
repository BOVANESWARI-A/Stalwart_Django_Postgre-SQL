# Stalwart HR Application — Production-Ready Flow

This project keeps the supplied Stalwart visual design and page content while connecting the application to a real Django + PostgreSQL backend.

## Technology

- Frontend: existing HTML, CSS, Bootstrap and JavaScript
- Backend: Django 5.2
- Database: PostgreSQL
- Authentication: Django authentication
- Roles: Candidate, Agent, HR, Administration
- File uploads: Django media storage
- Email: SMTP or local console backend
- Static files: WhiteNoise
- Production server: Gunicorn

## What has been completed

### Candidate

- Invitation link is token-based and one-time after final submission.
- Candidate must log in/register before opening the application.
- Invitation is bound to the invited candidate email/account.
- Candidate cannot access another candidate's application.
- Candidate registration always creates the Candidate role; users cannot self-assign HR, Agent or Administration privileges.
- Personal Information is saved to PostgreSQL.
- IQ Test answers are saved to PostgreSQL.
- Consent data is saved to PostgreSQL.
- Documents are saved as ApplicationFile records and validated for type/size.
- Employment Expectations are saved to PostgreSQL.
- Reference Details are saved to PostgreSQL.
- Declaration is saved to PostgreSQL.
- Final Submit changes the application status to `submitted` and records `submitted_at`.
- Submitted applications are visible through the Submitted Applications page.
- Existing saved fields are restored after each save/login.
- Same-as-residential address copying is handled server-side.

### Agent

- Agent sees only assigned candidates.
- Agent dashboard counts clients and submitted applications from PostgreSQL.
- Agent application access is restricted to assigned candidates.
- Agent assignment is managed safely through Django Admin using AgentClient records.

### HR

- HR sees submitted applications received from candidates.
- HR can create/send InsiteMy and Macro Kiosk invitations.
- Invitation status and timestamps are stored.
- Email success/failure is logged.
- HR can view application details.

### Administration

- Administration sees total candidates, paid subscriptions, applications received and feedback.
- Administration can manage users, groups, candidates, applications, subscriptions and agent-client assignments through Django Admin.

### Live dashboard

- `/dashboard/data/` is protected by Django authentication.
- Dashboard counters are calculated from PostgreSQL.
- Existing dashboard JavaScript can poll the endpoint without redesigning the UI.

## Important security corrections

- Candidate application URLs now require an authenticated Candidate account.
- Candidate access is restricted to the invited candidate record.
- Role access is enforced server-side.
- `next` redirects are validated to prevent unsafe external redirects.
- Final submission is performed by Django, not merely by a front-end success message.
- Uploaded files are limited to 1 MB and approved document/image types.
- Production HTTPS/security settings activate when `DEBUG=0`.
- Real credentials are not included in this package.

## Windows local setup

### 1. Open the project

Open:

`D:\Valiant\Stalwart_Django_PostgreSQL`

### 2. Create/activate virtual environment

If the existing `venv` is broken or belongs to another machine, recreate it:

```powershell
cd D:\Valiant\Stalwart_Django_PostgreSQL
py -3.10 -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install packages

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a PostgreSQL database, for example:

- Database: `stalwart_db`
- User: `postgres`
- Password: your PostgreSQL password
- Host: `127.0.0.1`
- Port: `5432`

Edit `.env` with those values.

### 5. Configure email

For initial testing, use:

```text
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
```

The invitation email will appear in the Django terminal.

For real email, use SMTP and configure:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=1
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-address@gmail.com
HR_NOTIFICATION_EMAIL=hr-address@example.com
```

Do not commit an SMTP password to Git.

### 6. Run migrations

```powershell
python manage.py migrate
```

### 7. Create the four role groups

```powershell
python manage.py setup_roles
```

### 8. Create an administration account

```powershell
python manage.py createsuperuser
```

A superuser is automatically treated as Administration by the application.

### Optional: local demo users

Only for local testing:

```powershell
python manage.py create_demo_users
```

The command prints the demo credentials. Do not use these credentials in production.

### 9. Check the project

```powershell
python manage.py check
```

For a deployment-style check:

```powershell
python manage.py check --deploy
```

### 10. Run the server

```powershell
python manage.py runserver
```

Open:

`http://127.0.0.1:8000/login/`

## Correct end-to-end production flow

### HR/Admin

1. Login.
2. Open Job Application.
3. Select InsiteMy or Macro Kiosk.
4. Enter candidate email/name.
5. Send invitation.
6. Confirm the email is sent and logged.
7. Candidate receives the secure invitation.

### Candidate

1. Open invitation link.
2. Login if an account exists, otherwise register.
3. The account is automatically a Candidate account.
4. Complete Personal Information and Save.
5. Complete IQ Test and Save.
6. Complete Consent and Save.
7. Upload Documents and Save.
8. Complete Employment Expectations and Save.
9. Complete Reference Details and Save.
10. Complete Declaration.
11. Click Submit.
12. Django saves `status=submitted` and `submitted_at`.
13. Invitation becomes inactive.
14. Candidate sees the submitted application.

### HR/Admin after submission

1. Open Received Applications.
2. The submitted application appears.
3. Open the application detail.
4. Review candidate/application information and uploaded files.

### Agent

1. Administration assigns a Candidate to the Agent through Django Admin → AgentClient.
2. Agent logs in.
3. Agent sees only assigned candidates/applications.

## PostgreSQL verification

To verify submitted records directly:

```powershell
python manage.py shell
```

Then:

```python
from core.models import JobApplication
JobApplication.objects.values("id", "candidate__email", "company", "status", "submitted_at")
```

A completed application must show:

```text
status = submitted
```

## Production deployment

Set environment variables on the production server instead of uploading `.env`.

Required values include:

- `SECRET_KEY`
- `DEBUG=0`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- PostgreSQL `DATABASE_URL` or PostgreSQL variables
- SMTP settings if email is required

Build:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Start:

```bash
gunicorn stalwart_project.wsgi:application
```

## Before real production launch

- Use a new strong Django `SECRET_KEY`.
- Use a production PostgreSQL database with backups.
- Use a real SMTP provider.
- Configure HTTPS.
- Configure durable media storage if the server filesystem is ephemeral.
- Create real role accounts and remove demo accounts.
- Test invitation, login, registration, save, upload, final submission and role isolation on the production staging environment.
- Never commit `.env` or passwords to source control.


## eDocs company-aware HR workflow

The supplied visual design is preserved. The backend now treats the HR account itself as company-specific.

### HR / Employer accounts

During Employer registration, the user selects **Macro Kiosk** or **InsiteMy** once. That choice is stored on `UserProfile.application_type`.

After login:
- Macro Kiosk HR is sent to the Macro Kiosk invitation screen.
- InsiteMy HR is sent to the InsiteMy invitation screen.
- The HR sidebar shows only its assigned company workflow.
- The HR invitation screen has no company selector.

### Candidate invitations

The HR invitation form accepts multiple email addresses separated by newline, comma or semicolon. Each email creates its own application and secure invitation.

Each invitation records the HR user who sent it in `Invitation.invited_by`. SMTP uses `DEFAULT_FROM_EMAIL` as the authenticated sender and the HR user's email as `Reply-To`, which avoids spoofing SMTP restrictions while ensuring replies go to the HR account.

### One account per email

Registration checks both Django `User.email` and `User.username` case-insensitively. A second registration using an existing email is rejected with an **existing user / login instead** message.

An invitation does not create a second user account. If the candidate already has an account, they log in with it and are routed to the existing invitation/application.

### Existing application designs

The original Macro Kiosk and InsiteMy candidate forms remain the application UI. Their POST data is stored in `JobApplication.data`, and uploaded application files are stored as `ApplicationFile` records.

Macro Kiosk has independent section-save support for all seven visual sections, plus final submission merging.

### My Profile

The existing My Profile page continues to use its existing modal/forms. Account/profile values are persisted to Django. The profile picture upload now reaches the backend and is stored as `UserProfile.profile_photo`.

### Settings

Existing account/company/user/assignment/legal settings POST actions remain server-backed. Creating an HR user through Settings requires a company; that company is stored on the HR user's `UserProfile.application_type`.

### Database initialization

Migration `0010_hr_workflow_profile_and_inviter`:
- adds HR workflow type to `UserProfile`
- adds profile photo storage
- records the inviting HR user on invitations
- seeds the `InsiteMy` and `Macro Kiosk` company records if they do not already exist

### Windows local run

```powershell
cd D:\EDocs\edocs\Stalwart_Django_PostgreSQL
..\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
python manage.py check
python manage.py runserver 127.0.0.1:8000
```

Use the actual parent path to your virtual environment; for the package layout supplied here it is normally:

```powershell
..\venv\Scripts\Activate.ps1
```

or, from `D:\EDocs\edocs` before entering the project:

```powershell
.\venv\Scripts\Activate.ps1
cd .\Stalwart_Django_PostgreSQL\
```

Keep SMTP credentials only in `.env`. Do not commit `.env` to Git.

For a first local test without PostgreSQL, set:

```text
USE_SQLITE=1
```

in `.env`, run `python manage.py migrate`, and then switch back to PostgreSQL settings when PostgreSQL is ready.
