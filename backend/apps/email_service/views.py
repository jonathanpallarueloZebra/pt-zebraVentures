from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .service import EmailService


@api_view(['POST'])
def send_email(request):
    """Send a test email (protected by auth if configured)."""
    to = request.data.get('to')
    subject = request.data.get('subject', 'Test email')
    body = request.data.get('body', '')
    template_id = request.data.get('template_id')
    template_data = request.data.get('template_data', {})

    if not to:
        return Response({'error': 'El campo "to" es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

    svc = EmailService()

    if template_id or template_data:
        ok = svc.send_template(to, template_data, template_id)
    else:
        ok = svc.send_plain(to, subject, body)

    if ok:
        return Response({'message': 'Email enviado correctamente.'})
    return Response({'error': 'No se pudo enviar el email.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
