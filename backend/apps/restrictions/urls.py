from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RestrictionViewSet, ValidationView, ConstraintsView, WorkerFieldsView, RestrictionChatView

router = DefaultRouter()
router.register(r'', RestrictionViewSet, basename='restriction')

urlpatterns = [
    path('validate/', ValidationView.as_view(), name='validate'),
    path('constraints/', ConstraintsView.as_view(), name='constraints'),
    path('worker-fields/', WorkerFieldsView.as_view(), name='worker-fields'),
    path('chat/', RestrictionChatView.as_view(), name='restriction-chat'),
    path('', include(router.urls)),
]
