"""
Management command: scaffold_entity

Usage:
    python manage.py scaffold_entity <name>

Creates a complete Django app under apps/<name>/ with:
  models.py, serializers.py, views.py, urls.py, admin.py, apps.py, migrations/__init__.py

Then registers the app in config/settings.py INSTALLED_APPS and adds its URL
include to config/urls.py so it is immediately accessible at /api/<name>/.

AI AGENT INSTRUCTIONS:
  - Call this command to add a new entity to the project without manual boilerplate.
  - After running, add your fields to apps/<name>/models.py and run makemigrations.
"""
import re
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError


MODELS_TEMPLATE = '''
from django.db import models


class {class_name}(models.Model):
    # TODO: define your fields here
    # nombre = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '{class_name}'
        verbose_name_plural = '{class_name}s'

    def __str__(self):
        return f'{class_name} {{self.pk}}'
'''

SERIALIZERS_TEMPLATE = '''
from rest_framework import serializers
from .models import {class_name}


class {class_name}Serializer(serializers.ModelSerializer):
    class Meta:
        model = {class_name}
        fields = '__all__'
'''

VIEWS_TEMPLATE = '''
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from .models import {class_name}
from .serializers import {class_name}Serializer


class {class_name}ViewSet(viewsets.ModelViewSet):
    queryset = {class_name}.objects.all()
    serializer_class = {class_name}Serializer
    permission_classes = [AllowAny]
'''

URLS_TEMPLATE = '''
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import {class_name}ViewSet

router = DefaultRouter()
router.register(r'{name}', {class_name}ViewSet, basename='{name}')

urlpatterns = [
    path('', include(router.urls)),
]
'''

ADMIN_TEMPLATE = '''
from django.contrib import admin
from .models import {class_name}


@admin.register({class_name})
class {class_name}Admin(admin.ModelAdmin):
    list_display = ['__str__', 'created_at', 'updated_at']
    search_fields = ['pk']
    ordering = ['-created_at']
'''

APPS_TEMPLATE = '''
from django.apps import AppConfig


class {class_name}Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.{name}'
    verbose_name = '{class_name}'
'''


class Command(BaseCommand):
    help = 'Scaffold a new entity app with models, serializers, views, urls and admin.'

    def add_arguments(self, parser):
        parser.add_argument('name', type=str, help='Entity name (singular, lowercase)')

    def handle(self, *args, **options):
        raw = options['name'].strip().lower()
        name = re.sub(r'[^a-z0-9_]', '_', raw).strip('_')
        if not name:
            raise CommandError('Invalid entity name.')
        class_name = ''.join(w.capitalize() for w in name.split('_'))

        base = Path('apps') / name
        if base.exists():
            raise CommandError(f'App apps/{name} already exists.')

        # Create directory structure
        (base / 'migrations').mkdir(parents=True)
        (base / '__init__.py').touch()
        (base / 'migrations' / '__init__.py').touch()

        ctx = {'name': name, 'class_name': class_name}

        for filename, template in [
            ('models.py', MODELS_TEMPLATE),
            ('serializers.py', SERIALIZERS_TEMPLATE),
            ('views.py', VIEWS_TEMPLATE),
            ('urls.py', URLS_TEMPLATE),
            ('admin.py', ADMIN_TEMPLATE),
            ('apps.py', APPS_TEMPLATE),
        ]:
            (base / filename).write_text(template.format(**ctx))

        # Register in settings.py INSTALLED_APPS
        settings_path = Path('config') / 'settings.py'
        if settings_path.exists():
            content = settings_path.read_text()
            app_entry = f"    'apps.{name}',\n"
            if f"'apps.{name}'" not in content:
                content = re.sub(
                    r'(INSTALLED_APPS\s*=\s*\[.*?)(\])',
                    lambda m: m.group(1) + app_entry + m.group(2),
                    content, flags=re.DOTALL
                )
                settings_path.write_text(content)

        # Register URL include in config/urls.py
        urls_path = Path('config') / 'urls.py'
        if urls_path.exists():
            content = urls_path.read_text()
            url_entry = f"    path('api/{name}/', include('apps.{name}.urls')),\n"
            if f"'apps.{name}.urls'" not in content:
                content = re.sub(
                    r'(urlpatterns\s*=\s*\[)(.*?)(\])',
                    lambda m: m.group(1) + m.group(2) + url_entry + m.group(3),
                    content, flags=re.DOTALL
                )
                urls_path.write_text(content)

        self.stdout.write(self.style.SUCCESS(
            f'✔ Entity "{name}" created at apps/{name}/. '
            f'Run: python manage.py makemigrations {name} && python manage.py migrate'
        ))
