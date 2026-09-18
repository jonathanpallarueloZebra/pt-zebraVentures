
from django.contrib import admin
from .models import ShiftDay


@admin.register(ShiftDay)
class ShiftDayAdmin(admin.ModelAdmin):
    list_display = ['shift', 'weekday', 'get_weekday_display']
    list_filter = ['shift', 'weekday']
    ordering = ['shift', 'weekday']

    def get_weekday_display(self, obj):
        return obj.get_weekday_display()
    get_weekday_display.short_description = 'Día'
