import os
import logging
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Mail, Email, To, Content, DynamicTemplateData,
)

logger = logging.getLogger(__name__)


class EmailService:
    """Wrapper around the SendGrid API for transactional emails."""

    def __init__(self):
        self.api_key = os.getenv('SENDGRID_API_KEY', '')
        self.default_template_id = os.getenv('SENDGRID_TEMPLATE_', '')
        self.from_email = os.getenv('SENDGRID_FROM_EMAIL', 'noreply@example.com')
        self.client = SendGridAPIClient(self.api_key) if self.api_key else None

    def send_plain(self, to_email: str, subject: str, body: str) -> bool:
        """Send a simple plain-text email."""
        if not self.client:
            logger.warning('SendGrid API key not configured.')
            return False
        message = Mail(
            from_email=Email(self.from_email),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content('text/plain', body),
        )
        try:
            response = self.client.send(message)
            logger.info('Email sent to %s — status %s', to_email, response.status_code)
            return 200 <= response.status_code < 300
        except Exception as exc:
            logger.error('Failed to send email to %s: %s', to_email, exc)
            return False

    def send_template(
        self,
        to_email: str,
        template_data: dict,
        template_id: str | None = None,
    ) -> bool:
        """Send an email using a SendGrid dynamic template."""
        if not self.client:
            logger.warning('SendGrid API key not configured.')
            return False
        tid = template_id or self.default_template_id
        if not tid:
            logger.error('No template ID provided.')
            return False
        message = Mail(
            from_email=Email(self.from_email),
            to_emails=To(to_email),
        )
        message.template_id = tid
        message.dynamic_template_data = template_data
        try:
            response = self.client.send(message)
            logger.info('Template email sent to %s — status %s', to_email, response.status_code)
            return 200 <= response.status_code < 300
        except Exception as exc:
            logger.error('Failed to send template email to %s: %s', to_email, exc)
            return False


# ── Invitación por email al crear un empleado ────────────────────────────────
# DESACTIVADO por código: en Cabrero los empleados no acceden a la aplicación,
# así que al crearlos (o importarlos) NO se crea cuenta de usuario ni se envía
# ningún correo, aunque se rellene el campo Email.
#
# Para reactivarlo basta poner esta constante a True (o mover la decisión a una
# variable de entorno). El código de envío sigue intacto en:
#   - apps/workers/serializers.py  → alta individual
#   - apps/workers/views.py        → importación de Excel (bloque comentado)
#
# TODO: revisar maquetación email y probar funcionamiento
WORKER_INVITES_ENABLED = False


def worker_invites_enabled() -> bool:
    """¿Se invita por email al crear un empleado con correo?

    Ahora mismo NO: ver `WORKER_INVITES_ENABLED` arriba.
    """
    return WORKER_INVITES_ENABLED
