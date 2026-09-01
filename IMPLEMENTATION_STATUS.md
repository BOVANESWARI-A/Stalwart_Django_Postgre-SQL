# Stalwart HR Application — Implementation Status

## Project goal

The supplied visual design is retained. The application is connected to Django + PostgreSQL so it can be used as a real HR/recruitment workflow rather than a front-end-only prototype.

## Completed backend flow

### 1. Authentication
- Django authentication is used for login/logout.
- Email-based login is supported.
- Candidate registration creates a Candidate account.
- Candidate self-registration cannot create HR, Agent or Administration privileges.
- Safe `next` redirects are used for invitation flows.

### 2. Four application roles
- Candidate
- Agent
- HR
- Administration

Role access is checked on the server, not only in the sidebar.

### 3. Candidate invitation
- HR/Admin creates a JobApplication.
- A unique UUID Invitation is created.
- The invitation link is emailed.
- The candidate must authenticate before opening the application.
- The invitation is bound to the intended candidate record.
- After final submission, the invitation becomes inactive.

### 4. Candidate application persistence
The following sections now persist in PostgreSQL:

- Personal Information
- IQ Test
- Consent
- Document Submission
- Employment Expectations
- Reference Details
- Applicant Declaration

The existing application form remains visually intact; broken/missing HTML form names were corrected so the browser actually sends the values to Django.

### 5. Documents
- File uploads are stored through `ApplicationFile`.
- Maximum file size: 1 MB.
- Allowed types: PDF, DOC, DOCX, JPG, JPEG, PNG and WEBP.
- The application stores the uploaded file record and field name.

### 6. Final submission
The declaration success page is no longer treated as proof of submission by itself.

Django now performs the actual final transaction:

1. Save submitted data.
2. Validate required application sections.
3. Set `JobApplication.status = submitted`.
4. Set `submitted_at`.
5. Complete/deactivate the invitation.
6. Create an HR notification.
7. Optionally send an HR notification email.
8. Show the submitted confirmation page.

### 7. Candidate submitted applications
Candidate sees only their own submitted applications.

### 8. Agent
- Agent dashboard counts assigned clients.
- Agent dashboard counts submitted applications for assigned candidates.
- Agent candidate/application access is restricted to assigned candidates.
- Agent-client assignment is stored in PostgreSQL.
- Assignment can be managed through Django Admin.

### 9. HR
- HR can create InsiteMy and Macro Kiosk applications.
- HR can send candidate invitations.
- Invitation status/timestamps are stored.
- Email success/failure is logged.
- HR can view received applications.

### 10. Administration
Administration can manage:

- Users
- Groups/roles
- Candidates
- Applications
- Subscriptions
- Agent-client assignments
- Feedback
- Invitations
- Application files
- Notifications
- Email logs

### 11. Dashboard
Dashboard values are calculated from PostgreSQL rather than hard-coded numbers.

Candidate:
- Account Type
- Valid Till
- Remaining Days
- Application Submitted

Agent:
- Number of Clients
- Applications Submitted

HR:
- Applications Received
- Invitations Sent

Administration:
- Total Candidates
- Paid Subscriptions
- Applications Received
- Received Feedback

### 12. Live dashboard endpoint

Protected endpoint:

`/dashboard/data/`

It returns role-specific database metrics for JavaScript polling.

### 13. PostgreSQL
The application uses PostgreSQL as the production database.

Both styles are supported:

- Individual `POSTGRES_*` environment variables for local Windows development.
- `DATABASE_URL` for hosted PostgreSQL services.

### 14. Production settings
When `DEBUG=0`:

- HTTPS redirect can be enabled.
- Secure session cookies are enabled.
- Secure CSRF cookies are enabled.
- HSTS is enabled.
- Content type sniffing is disabled.
- Referrer policy is restricted.
- Production secret-key validation is enabled.

### 15. Static/media
- Existing static assets are retained.
- WhiteNoise is configured for static files.
- Django media storage is configured for application uploads.

For a production server with ephemeral storage, move media storage to durable object storage before launch.

## Design preservation

No intentional redesign of the supplied pages was made.

The important changes are functional:

- Missing HTML `name` attributes were added.
- IQ answer controls now submit values.
- Document inputs now submit file names.
- Save buttons identify their application section.
- Saved radio/checkbox/select values can be restored.
- Same-as-residential address copying works server-side.

## Local run commands

```powershell
cd D:\Valiant\Stalwart_Django_PostgreSQL
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py setup_roles
python manage.py check
python manage.py runserver
```

Open:

`http://127.0.0.1:8000/login/`

## Production verification commands

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
gunicorn stalwart_project.wsgi:application
```

## End-to-end acceptance test

### Candidate

- [ ] Open invitation.
- [ ] Register/login using invitation email.
- [ ] Personal Information saves.
- [ ] IQ Test saves.
- [ ] Consent saves.
- [ ] Document upload saves.
- [ ] Employment Expectations saves.
- [ ] Reference saves.
- [ ] Declaration saves.
- [ ] Final Submit changes application status to `submitted`.
- [ ] Submitted Applications displays the record.
- [ ] Logout/login does not lose saved data.

### HR

- [ ] Send invitation.
- [ ] Email is delivered through SMTP or appears in console during local testing.
- [ ] Received application appears after candidate submits.
- [ ] Application detail opens.

### Agent

- [ ] Candidate is assigned to Agent.
- [ ] Agent sees assigned candidate only.
- [ ] Agent cannot open an unassigned candidate.

### Administration

- [ ] Total Candidates is database-driven.
- [ ] Paid Subscriptions is database-driven.
- [ ] Applications Received is database-driven.
- [ ] Received Feedback is database-driven.

## Credentials/security note

The package intentionally contains no real email password or production database password.

If an SMTP app password was previously placed in a local `.env` or shared during development, revoke that credential and generate a new one before production use.
