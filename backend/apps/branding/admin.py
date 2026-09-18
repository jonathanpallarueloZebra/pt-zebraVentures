from django.contrib import admin
from .models import Branding


@admin.register(Branding)
class BrandingAdmin(admin.ModelAdmin):
    fieldsets = [
        ('Empresa', {'fields': ['company_name', 'tagline']}),
        ('Imagenes', {'fields': ['logo', 'favicon']}),
        ('Colores', {'fields': ['primary_color', 'primary_dark']}),
    ]
    readonly_fields = ['updated_at']

    def has_add_permission(self, request):
        # Only one record allowed
        return not Branding.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
