from django.contrib import admin
from .models import Kind, KindAttribute, KindValue, KindValueAttribute


class KindAttributeInline(admin.TabularInline):
    model = KindAttribute
    extra = 1
    fields = ['key', 'label', 'field_type', 'required', 'default_value', 'placeholder', 'order']
    verbose_name = 'Campo extra'
    verbose_name_plural = 'Campos extra de cada valor'


class KindValueInline(admin.TabularInline):
    model = KindValue
    extra = 1
    fields = ['code', 'label', 'icon', 'color', 'order', 'active']
    show_change_link = True


class KindValueAttributeInline(admin.TabularInline):
    model = KindValueAttribute
    extra = 0
    fields = ['attribute', 'value']
    verbose_name = 'Valor de campo'
    verbose_name_plural = 'Valores de campos extra'


@admin.register(Kind)
class KindAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'editable', 'active']
    list_filter = ['active', 'editable']
    search_fields = ['code', 'name']
    inlines = [KindAttributeInline, KindValueInline]


@admin.register(KindValue)
class KindValueAdmin(admin.ModelAdmin):
    list_display = ['kind', 'code', 'label', 'order', 'active']
    list_filter = ['kind', 'active']
    search_fields = ['code', 'label']
    inlines = [KindValueAttributeInline]
