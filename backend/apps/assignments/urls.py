from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AssignmentRuleViewSet, AssignmentChatView

router = DefaultRouter()
router.register(r'', AssignmentRuleViewSet, basename='assignment-rule')

urlpatterns = [
    path('chat/', AssignmentChatView.as_view(), name='assignment-chat'),
    path('', include(router.urls)),
]
