from django.contrib import admin
from .models import RestDay


@admin.register(RestDay)
class RestDayAdmin(admin.ModelAdmin):
    list_display = ['worker', 'date', 'reason']
    list_filter = ['date']
    search_fields = ['worker__name']
