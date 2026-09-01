# Valiant HR backend update

This version keeps the existing templates/content and focuses on server-side behavior.

Implemented:
- My Profile email changes stay synchronized with Django username/login email.
- Account Settings is available to every authenticated role; administration-only management controls remain protected.
- Settings account changes persist to the database.
- Logout works from the existing link as well as POST forms.
- Job application status can be updated by HR/Administration: Submitted, Reviewed, Shortlisted, Rejected.
- Received Applications keeps reviewed/shortlisted/rejected applications visible instead of making them disappear.
- Submitted Applications reflects the current application lifecycle status.
- Application detail pages include an HR/Admin status update control.
- Existing My Data upload/delete, Feedback submission, Security/password change, Terms, Privacy and FAQ routes are preserved.
- Existing email/reset templates and secret/reset-link behavior were not redesigned.

Run:
1. Activate your existing virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python manage.py migrate`
4. Run: `python manage.py check`
5. Run: `python manage.py runserver`

Database:
- Uses the PostgreSQL configuration already present in `.env`.
- No new database table is required for the changes above.
