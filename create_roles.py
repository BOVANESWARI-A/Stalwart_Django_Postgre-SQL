"""Backward-compatible helper for creating the application role groups."""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stalwart_project.settings")
django.setup()

from django.core.management import call_command

call_command("setup_roles")
