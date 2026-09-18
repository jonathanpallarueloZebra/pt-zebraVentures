from django.contrib import admin
from .models import Restriction, ValidationResult, RestrictionViolation


@admin.register(Restriction)
class RestrictionAdmin(admin.ModelAdmin):
    list_display = ['name', 'engine', 'severity', 'customizable', 'active', 'created_at']
    list_filter = ['customizable', 'active', 'engine', 'severity']
    search_fields = ['name']


@admin.register(ValidationResult)
class ValidationResultAdmin(admin.ModelAdmin):
    list_display = ['weekly_plan', 'is_valid', 'created_at']


@admin.register(RestrictionViolation)
class RestrictionViolationAdmin(admin.ModelAdmin):
    list_display = ['restriction', 'severity', 'day_date', 'shift_type']
    list_filter = ['severity']
