from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WorkerViewSet

router = DefaultRouter()
router.register(r'', WorkerViewSet, basename='worker')

urlpatterns = [
    path('', include(router.urls)),
]
