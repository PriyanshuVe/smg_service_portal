# portal/management/commands/create_default_superuser.py
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = (
        "Create a default superuser from environment variables if it does not exist.\n"
        "Requires env vars: DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_EMAIL, DJANGO_ADMIN_PASSWORD"
    )

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_ADMIN_USERNAME')
        email = os.environ.get('DJANGO_ADMIN_EMAIL')
        password = os.environ.get('DJANGO_ADMIN_PASSWORD')

        if not (username and email and password):
            self.stdout.write(self.style.WARNING(
                "DJANGO_ADMIN_USERNAME, DJANGO_ADMIN_EMAIL or DJANGO_ADMIN_PASSWORD not set. Skipping superuser creation."
            ))
            return

        User = get_user_model()

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.NOTICE if hasattr(self.style, 'NOTICE') else self.style.WARNING(
                f'Superuser "{username}" already exists — skipping.'
            ))
            return

        try:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created successfully.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create superuser: {e}'))
