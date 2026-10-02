"""Vistas de uso general que no pertenecen a ningun dominio concreto."""
import os

from django.core.management import call_command
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class ResetearDemoView(APIView):
    """POST /api/core/resetear-demo/ — devuelve la demo a su estado de partida.

    Marketing ensena el planificador a clientes y durante la sesion se tocan
    datos: se mueven turnos, se dan de alta ausencias, se regeneran planes.
    Esto deja la base como al principio para que la siguiente demo empiece
    igual que la anterior.

    Lanza el mismo `seed_demo --reset` que el cron del servidor, pero con
    `--base-limpia`: la planificacion queda sin huecos ni violaciones, porque
    lo que se ensena debe ser un cuadrante resuelto.

    Pide sesion iniciada. No se restringe a superusuarios a proposito: lo usa
    quien esta haciendo la demo, no solo quien administra.

    Solo responde donde ENVIRONMENT es 'qa' o 'dev'. En produccion devuelve
    403: los datos de un cliente no se borran desde un boton.
    """

    permission_classes = [IsAuthenticated]

    ENTORNOS_PERMITIDOS = ('qa', 'dev', 'local')

    def post(self, request):
        # settings.py lee ENVIRONMENT con os.getenv pero no lo expone como
        # setting, asi que se consulta igual que alli.
        entorno = os.getenv('ENVIRONMENT', 'dev').lower()
        if entorno not in self.ENTORNOS_PERMITIDOS:
            return Response(
                {'detail': f'El reseteo no esta disponible en el entorno «{entorno}».'},
                status=403,
            )

        # El comando aplica el reseteo dentro de su propia transaccion y
        # vuelve a sembrar; tarda unos segundos porque regenera los planes de
        # dos semanas para tres tiendas.
        call_command('seed_demo', reset=True, base_limpia=True, verbosity=0)

        return Response({
            'detail': 'Demo reseteada. La planificacion vuelve a su estado de partida.',
        })
