"""
Management command to create (or reset) a test user for the client panel.

Usage:
    python manage.py create_test_user
    python manage.py create_test_user --email otro@zebraventures.eu --password otra123
    python manage.py create_test_user --no-staff

Creates a user that can log in at the CLIENT panel (/login) but NOT at
/adminzebra, which requires is_superuser.

Defaults:
    username  testZebra
    email     testzebra@zebraventures.eu   (el login se hace con EMAIL)
    password  test123

This command is idempotent — safe to run multiple times; it resets the
password and flags of an existing user with the same email or username.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

DEFAULT_USERNAME = 'testZebra'
DEFAULT_EMAIL = 'testzebra@zebraventures.eu'
DEFAULT_PASSWORD = 'test123'


class Command(BaseCommand):
    help = 'Create or reset a test user for the client panel (/login), never a superuser.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default=DEFAULT_USERNAME)
        parser.add_argument('--email', default=DEFAULT_EMAIL)
        parser.add_argument('--password', default=DEFAULT_PASSWORD)
        parser.add_argument(
            '--no-staff',
            action='store_true',
            help='Crear el usuario sin is_staff (solo lectura del panel, sin pantallas de admin).',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']
        is_staff = not options['no_staff']

        user = (
            User.objects.filter(email__iexact=email).first()
            or User.objects.filter(username__iexact=username).first()
        )

        if user:
            action = 'actualizado'
        else:
            user = User(username=username)
            action = 'creado'

        user.username = username
        user.email = email
        user.first_name = user.first_name or 'Test'
        user.last_name = user.last_name or 'Zebra'
        user.is_active = True
        user.is_staff = is_staff
        user.is_superuser = False
        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f'\nUsuario {action} correctamente.'))
        self.stdout.write(f'  email     : {user.email}   <-- usar este para el login')
        self.stdout.write(f'  username  : {user.username}')
        self.stdout.write(f'  password  : {password}')
        self.stdout.write(f'  is_staff  : {user.is_staff}')
        self.stdout.write(f'  is_superuser: {user.is_superuser} (no puede entrar en /adminzebra)')
