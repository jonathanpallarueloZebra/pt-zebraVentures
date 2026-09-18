import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    """Custom user model for authentication."""

    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.email


class PasswordToken(models.Model):
    """One-time token for password setup (invite) and password reset."""

    PURPOSE_CHOICES = [
        ('invite', 'Primera configuracion'),
        ('reset', 'Restablecer contraseña'),
    ]

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='password_tokens')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField(max_length=10, choices=PURPOSE_CHOICES)
    used = models.BooleanField(default=False)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.purpose} token for {self.user.email}'

    @property
    def is_valid(self):
        return not self.used and self.expires_at > timezone.now()
