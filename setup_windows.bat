@echo off
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy /Y .env.example .env
python manage.py migrate
python manage.py setup_roles
echo Setup complete. Create an admin with:
echo venv\Scripts\activate
echo python manage.py createsuperuser
pause
