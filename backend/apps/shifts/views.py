
from datetime import date as _date, datetime

from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Shift
from .serializers import ShiftSerializer


def _parse_date(value):
    """Parse 'YYYY-MM-DD' → date, or None if empty/invalid."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _apply_validity_filters(qs, request):
    """Filtra el queryset de turnos por vigencia según query params.

    - ?date=YYYY-MM-DD → solo turnos vigentes en esa fecha (AC-2):
      valid_from <= date <= valid_to, tratando NULL como "sin límite".
    - ?active=true      → excluye turnos cuya vigencia ya terminó respecto a
      hoy (AC-5): valid_to >= hoy o NULL. Pensado para el listado de turnos
      disponibles al asignar, sin ocultar el histórico en las vistas de admin.

    Los turnos normales (valid_from/valid_to NULL) pasan siempre los filtros.
    """
    on_date = _parse_date(request.query_params.get('date'))
    if on_date is not None:
        qs = qs.filter(
            (Q(valid_from__isnull=True) | Q(valid_from__lte=on_date)) &
            (Q(valid_to__isnull=True) | Q(valid_to__gte=on_date))
        )

    active = request.query_params.get('active')
    if str(active).lower() in ('1', 'true', 'yes'):
        today = _date.today()
        qs = qs.filter(Q(valid_to__isnull=True) | Q(valid_to__gte=today))

    return qs


class ShiftViewSet(viewsets.ModelViewSet):
    queryset = Shift.objects.all()
    serializer_class = ShiftSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Shift.objects.prefetch_related('operating_days').order_by('name')
        return _apply_validity_filters(qs, self.request)

    @action(detail=False, methods=['get'])
    def all(self, request):
        """Return all shifts flat, sin filtrar por vigencia (vista admin:
        incluye turnos extra caducados como registro histórico)."""
        shifts = Shift.objects.prefetch_related('operating_days').all()
        serializer = self.get_serializer(shifts, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def flat(self, request):
        """Return all shifts flat (kept for backwards compat). Respeta los
        filtros de vigencia (?date/?active) igual que el listado por defecto."""
        qs = Shift.objects.prefetch_related('operating_days').order_by('name')
        qs = _apply_validity_filters(qs, request)
        serializer = self.get_serializer(qs, many=True)
        return Response(serializer.data)
