"""
Management command to set up a new client instance from environment variables.

Usage:
    python manage.py setup_client

Reads from environment:
    CLIENT_NAME         Name of the company (default: 'Mi Empresa')
    CLIENT_TAGLINE      Tagline (optional)
    CLIENT_PRIMARY      Primary color hex (default: '#EF4444')
    CLIENT_PRIMARY_DARK Darker variant (default: '#B91C1C')
    ADMIN_EMAIL         Superuser email
    ADMIN_PASSWORD      Superuser password

This command is idempotent — safe to run multiple times.
"""
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Configure a fresh client instance (branding + superuser + base catalog).'

    def handle(self, *args, **options):
        self._setup_branding()
        self._setup_superuser()
        self._setup_catalog()
        self.stdout.write(self.style.SUCCESS('\nCliente configurado correctamente.'))

    # ──────────────────────────────────────────────────────────────
    def _setup_branding(self):
        from apps.branding.models import Branding
        self.stdout.write('\n== Branding ==')

        branding = Branding.get()
        branding.company_name = os.getenv('CLIENT_NAME', branding.company_name)
        branding.tagline = os.getenv('CLIENT_TAGLINE', branding.tagline)
        branding.primary_color = os.getenv('CLIENT_PRIMARY', branding.primary_color)
        branding.primary_dark = os.getenv('CLIENT_PRIMARY_DARK', branding.primary_dark)
        branding.save()

        self.stdout.write(f'  Empresa:  {branding.company_name}')
        self.stdout.write(f'  Color:    {branding.primary_color}')
        self.stdout.write(
            '  Logo: sube el archivo desde /admin o via PATCH /api/branding/'
        )

    # ──────────────────────────────────────────────────────────────
    def _setup_superuser(self):
        from apps.authentication.models import CustomUser
        self.stdout.write('\n== Superusuario ==')

        email = os.getenv('ADMIN_EMAIL')
        password = os.getenv('ADMIN_PASSWORD')

        if not email or not password:
            self.stdout.write('  Sin ADMIN_EMAIL/ADMIN_PASSWORD — omitido.')
            return

        if CustomUser.objects.filter(email=email).exists():
            self.stdout.write(f'  Ya existe: {email}')
            return

        CustomUser.objects.create_superuser(email=email, username=email, password=password)
        self.stdout.write(f'  Creado: {email}')

    # ──────────────────────────────────────────────────────────────
    def _setup_catalog(self):
        """Ensure the base catalog exists. Delegates to seed_data._seed_catalog()."""
        self.stdout.write('\n== Catalogo base ==')
        from django.core.management import call_command
        # seed_data is idempotent (uses get_or_create)
        call_command('seed_data', verbosity=0)
        self.stdout.write('  Catalogo base verificado.')
