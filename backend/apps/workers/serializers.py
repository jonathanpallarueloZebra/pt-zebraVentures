import os
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.crypto import get_random_string
from rest_framework import serializers

from apps.authentication.models import PasswordToken
from apps.dynamic_fields.mixins import DynamicFieldsMixin
from apps.email_service.service import EmailService, worker_invites_enabled
from .models import Worker, WorkerPreference

User = get_user_model()
email_service = EmailService()


class WorkerPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkerPreference
        fields = ['shift_type']


class WorkerSerializer(DynamicFieldsMixin, serializers.ModelSerializer):
    _entity_type = 'worker'
    preferredShifts = WorkerPreferenceSerializer(
        source='preferences', many=True, read_only=True,
    )
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Worker
        fields = [
            'id', 'name', 'active', 'preferredShifts', 'user', 'email', 'custom_data',
        ]
        extra_kwargs = {'user': {'required': False}}

    def validate(self, attrs):
        """Impide guardar una rotación que no puede rotar.

        Si el trabajador cumple la condición de una regla de alternancia (p.ej.
        rotacion == 'semanal') pero deja vacío el turno alternativo, el generador
        lo dejaría en su turno base para siempre sin avisar: la ficha diría que
        rota y en la práctica sería un turno fijo. Se corta aquí.
        """
        from apps.assignments.models import AssignmentRule
        from apps.planning.schedule_generator import _rule_condition_matches

        # super() = DynamicFieldsMixin.validate, que exige los campos marcados
        # como obligatorios en la configuracion al crear. Sin esta llamada la
        # validacion del mixin no se ejecutaria nunca para Worker.
        attrs = super().validate(attrs)

        cd = attrs.get('custom_data')
        if cd is None:
            return attrs
        # En un PATCH parcial, custom_data puede venir incompleto: se valida el
        # resultado final (lo guardado + lo que llega).
        merged = {**((self.instance.custom_data if self.instance else {}) or {}), **cd}

        errors = {}
        rules = AssignmentRule.objects.filter(active=True)
        for rule in rules:
            config = rule.config or {}
            if config.get('pattern') not in ('alternate_weekly', 'alternate_daily'):
                continue
            override_field = config.get('overrideField', '')
            if not override_field:
                continue
            if not _rule_condition_matches(merged, config):
                continue
            if str(merged.get(override_field, '') or ''):
                continue
            cond_field = config.get('conditionField', '')
            cond_value = config.get('conditionValue', '')
            errors[override_field] = (
                f'Obligatorio cuando "{cond_field}" es "{cond_value}": sin turno '
                f'alternativo la rotación no se aplica y el turno queda fijo.'
            )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def create(self, validated_data):
        email = validated_data.pop('email', None)
        preferences_data = self.context['request'].data.get('preferredShifts', [])
        # Apply dynamic field defaults
        cd = validated_data.get('custom_data') or {}
        validated_data['custom_data'] = self._apply_defaults(cd)

        # Si se indica email, se crea la cuenta y se le invita a establecer su
        # contraseña. Se puede desactivar con WORKER_INVITE_EMAIL=0 (ver
        # `worker_invites_enabled`): en Cabrero los empleados no acceden a la
        # aplicación, así que no se crea cuenta ni se envía nada.
        # TODO: revisar maquetación email y probar funcionamiento
        if email and worker_invites_enabled():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': email,
                    'is_active': False,
                },
            )
            validated_data['user'] = user
            if created:
                user.set_unusable_password()
                user.save()
                # Create invite token and send email
                token = PasswordToken.objects.create(
                    user=user,
                    purpose='invite',
                    expires_at=timezone.now() + timedelta(days=7),
                )
                frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:4200').rstrip('/')
                setup_link = f'{frontend_url}/set-password?token={token.token}'
                email_service.send_plain(
                    to_email=email,
                    subject='Configura tu cuenta',
                    body=f'Hola {validated_data.get("name", "")},\n\n'
                         f'Se ha creado tu cuenta en el planificador de turnos.\n'
                         f'Usa este enlace para establecer tu contraseña:\n{setup_link}\n\n'
                         f'El enlace expira en 7 días.',
                )

        worker = Worker.objects.create(**validated_data)
        for shift_type in preferences_data:
            WorkerPreference.objects.create(worker=worker, shift_type=shift_type)
        return worker

    def update(self, instance, validated_data):
        validated_data.pop('email', None)  # Ignore email on update
        instance.name = validated_data.get('name', instance.name)
        instance.active = validated_data.get('active', instance.active)
        instance.user = validated_data.get('user', instance.user)
        # Merge custom_data
        if 'custom_data' in validated_data:
            existing = instance.custom_data or {}
            incoming = validated_data['custom_data'] or {}
            instance.custom_data = self._apply_defaults({**existing, **incoming})
        instance.save()
        preferences_data = self.context['request'].data.get('preferredShifts', [])
        if preferences_data is not None:
            instance.preferences.all().delete()
            for shift_type in preferences_data:
                WorkerPreference.objects.create(worker=instance, shift_type=shift_type)
        return instance
