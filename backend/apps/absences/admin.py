from django.contrib import admin
from .models import AbsenceType, AbsenceRequest


@admin.register(AbsenceType)
class AbsenceTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'requires_approval', 'active']
    list_filter = ['active']


@admin.register(AbsenceRequest)
class AbsenceRequestAdmin(admin.ModelAdmin):
    list_display = ['worker', 'type', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['status', 'type']
    search_fields = ['worker__name']
