from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .serializers import AgentMessageSerializer
from .agent import Agent


# El Agent se construye la primera vez que se usa, no al importar el modulo.
# Antes era `agent = Agent()` a nivel de modulo y, como Agent.__init__ lanza
# ValueError si falta AGENT_MODEL, el import de apps.agent.urls reventaba. Django
# carga el URLconf de forma diferida (en la primera peticion), asi que el
# contenedor arrancaba sin errores pero TODA la API respondia 500 -- incluido
# /api/branding/ -- en cualquier despliegue sin AGENT_MODEL, como el de
# docker-compose. Con la construccion diferida el fallo queda confinado a este
# endpoint, que es el unico que necesita el agente.
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


@api_view(['POST'])
@permission_classes([AllowAny])
def chat(request):
    """Send a message to the agent and get a response."""
    serializer = AgentMessageSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        agent = _get_agent()
    except ValueError as exc:
        # Falta configuracion (AGENT_MODEL). 503 en vez de 500: no es un bug,
        # es que el agente no esta habilitado en este despliegue.
        return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    response = agent.chat(serializer.validated_data['message'])
    return Response({'response': response}, status=status.HTTP_200_OK)
