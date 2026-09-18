from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AbsenceTypeViewSet, AbsenceRequestViewSet

router = DefaultRouter()
router.register(r'types', AbsenceTypeViewSet, basename='absencetype')
router.register(r'requests', AbsenceRequestViewSet, basename='absencerequest')

urlpatterns = [
    path('', include(router.urls)),
]
