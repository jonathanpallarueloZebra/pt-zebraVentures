from django.contrib import admin
from .models import Worker, WorkerPreference


class WorkerPreferenceInline(admin.TabularInline):
    model = WorkerPreference
    extra = 1


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ['name', 'active', 'created_at']
    list_filter = ['active']
    search_fields = ['name']
    inlines = [WorkerPreferenceInline]
