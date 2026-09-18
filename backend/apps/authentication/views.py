import os
import logging
from datetime import timedelta

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import PasswordToken
from .serializers import (
    RegisterSerializer, UserSerializer,
    ForgotPasswordSerializer, ResetPasswordSerializer,
    SetPasswordSerializer, ChangePasswordSerializer,
)
from apps.email_service.service import EmailService

User = get_user_model()
logger = logging.getLogger(__name__)
email_service = EmailService()


class RegisterView(generics.CreateAPIView):
    """Register a new user."""
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Usuario creado correctamente.'},
            status=status.HTTP_201_CREATED,
        )


class ProfileView(generics.RetrieveUpdateAPIView):
    """Get or update the authenticated user's profile."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(APIView):
    """Change password for authenticated user."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Contraseña actual incorrecta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return Response({'message': 'Contraseña actualizada correctamente.'})


class ForgotPasswordView(APIView):
    """Send a password reset email."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        # Always return success to avoid email enumeration
        try:
            user = User.objects.get(email=email)
            # Invalidate previous tokens
            PasswordToken.objects.filter(user=user, purpose='reset', used=False).update(used=True)
            token = PasswordToken.objects.create(
                user=user,
                purpose='reset',
                expires_at=timezone.now() + timedelta(hours=24),
            )
            frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:4200').rstrip('/')
            reset_link = f'{frontend_url}/reset-password?token={token.token}'
            email_service.send_plain(
                to_email=email,
                subject='Restablecer contraseña',
                body=f'Hola {user.first_name or user.username},\n\n'
                     f'Usa este enlace para restablecer tu contraseña:\n{reset_link}\n\n'
                     f'El enlace expira en 24 horas.',
            )
            logger.info('Password reset email sent to %s (token %s)', email, token.token)
        except User.DoesNotExist:
            logger.info('Password reset requested for non-existent email: %s', email)
        return Response({'message': 'Si el email existe, recibirás un enlace para restablecer tu contraseña.'})


class ResetPasswordView(APIView):
    """Reset password using a token."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token_obj = PasswordToken.objects.get(
                token=serializer.validated_data['token'],
                purpose='reset',
            )
        except PasswordToken.DoesNotExist:
            return Response({'error': 'Token no válido.'}, status=status.HTTP_400_BAD_REQUEST)
        if not token_obj.is_valid:
            return Response({'error': 'Token expirado o ya utilizado.'}, status=status.HTTP_400_BAD_REQUEST)
        user = token_obj.user
        user.set_password(serializer.validated_data['password'])
        user.is_active = True
        user.save()
        token_obj.used = True
        token_obj.save()
        return Response({'message': 'Contraseña restablecida correctamente.'})


class SetPasswordView(APIView):
    """Set password for first-time setup via invite link."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            token_obj = PasswordToken.objects.get(
                token=serializer.validated_data['token'],
                purpose='invite',
            )
        except PasswordToken.DoesNotExist:
            return Response({'error': 'Token no válido.'}, status=status.HTTP_400_BAD_REQUEST)
        if not token_obj.is_valid:
            return Response({'error': 'Token expirado o ya utilizado.'}, status=status.HTTP_400_BAD_REQUEST)
        user = token_obj.user
        user.set_password(serializer.validated_data['password'])
        user.is_active = True
        user.save()
        token_obj.used = True
        token_obj.save()
        return Response({'message': 'Contraseña configurada correctamente.'})


class ValidateTokenView(APIView):
    """Check if a password token is still valid."""
    permission_classes = [AllowAny]

    def get(self, request):
        token_str = request.query_params.get('token')
        if not token_str:
            return Response({'valid': False})
        try:
            token_obj = PasswordToken.objects.select_related('user').get(token=token_str)
            return Response({
                'valid': token_obj.is_valid,
                'purpose': token_obj.purpose,
                'email': token_obj.user.email,
            })
        except PasswordToken.DoesNotExist:
            return Response({'valid': False})


class InviteWorkerView(APIView):
    """Send invite email to a worker so they can set their password."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id es requerido.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        # Invalidate previous invite tokens
        PasswordToken.objects.filter(user=user, purpose='invite', used=False).update(used=True)
        token = PasswordToken.objects.create(
            user=user,
            purpose='invite',
            expires_at=timezone.now() + timedelta(days=7),
        )
        frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:4200').rstrip('/')
        setup_link = f'{frontend_url}/set-password?token={token.token}'
        email_service.send_plain(
            to_email=user.email,
            subject='Configura tu contraseña',
            body=f'Hola {user.first_name or user.username},\n\n'
                 f'Se ha creado tu cuenta. Usa este enlace para configurar tu contraseña:\n{setup_link}\n\n'
                 f'El enlace expira en 7 días.',
        )
        logger.info('Invite email sent to %s (token %s)', user.email, token.token)
        return Response({'message': f'Email de invitación enviado a {user.email}.'})
