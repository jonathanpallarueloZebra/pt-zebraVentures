from django.contrib import admin
from .models import ClosedDay, WeeklyPlan


@admin.register(WeeklyPlan)
class WeeklyPlanAdmin(admin.ModelAdmin):
    list_display = ['start_date', 'created_at', 'updated_at']
    search_fields = ['start_date']


@admin.register(ClosedDay)
class ClosedDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'scope_entity_id', 'reason']
    list_filter = ['scope_entity_id']
    search_fields = ['reason']
