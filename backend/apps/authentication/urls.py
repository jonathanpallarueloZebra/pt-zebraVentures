from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    RegisterView, ProfileView, ChangePasswordView,
    ForgotPasswordView, ResetPasswordView, SetPasswordView,
    ValidateTokenView, InviteWorkerView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', TokenObtainPairView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
    path('set-password/', SetPasswordView.as_view(), name='set-password'),
    path('validate-token/', ValidateTokenView.as_view(), name='validate-token'),
    path('invite/', InviteWorkerView.as_view(), name='invite-worker'),
]
