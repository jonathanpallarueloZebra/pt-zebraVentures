from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RestDayViewSet

router = DefaultRouter()
router.register(r'', RestDayViewSet, basename='restday')

urlpatterns = [
    path('', include(router.urls)),
]
