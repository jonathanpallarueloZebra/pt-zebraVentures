from django.contrib import admin
from .models import EntityField


@admin.register(EntityField)
class EntityFieldAdmin(admin.ModelAdmin):
    list_display = ['entity_type', 'key', 'label', 'field_type', 'required', 'show_in_list', 'order', 'active']
    list_filter = ['entity_type', 'field_type', 'active']
    search_fields = ['key', 'label']
    ordering = ['entity_type', 'order']
