from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ClosedDayViewSet,
    WeeklyPlanViewSet,
    OvertimeView,
    WeekStatusView,
    PlanDiagnosticsView,
    ScheduleGenerationView,
    BulkScheduleGenerationView,
    ScheduleDiagnoseView,
)

router = DefaultRouter()
router.register(r'weekly-plan', WeeklyPlanViewSet, basename='weeklyplan')
router.register(r'closed-days', ClosedDayViewSet, basename='closedday')

urlpatterns = [
    path('overtime/', OvertimeView.as_view(), name='planning-overtime'),
    path('week-status/', WeekStatusView.as_view(), name='planning-week-status'),
    path('diagnostics/', PlanDiagnosticsView.as_view(), name='planning-diagnostics'),
    path('schedule/generate/', ScheduleGenerationView.as_view(), name='schedule-generate'),
    path('schedule/generate-bulk/', BulkScheduleGenerationView.as_view(), name='schedule-generate-bulk'),
    path('schedule/diagnose/', ScheduleDiagnoseView.as_view(), name='schedule-diagnose'),
    path('', include(router.urls)),
]
