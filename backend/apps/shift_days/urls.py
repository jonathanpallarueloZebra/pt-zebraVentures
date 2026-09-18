
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShiftDayViewSet

router = DefaultRouter()
router.register(r'', ShiftDayViewSet, basename='shift_days')

urlpatterns = [
    path('', include(router.urls)),
]
