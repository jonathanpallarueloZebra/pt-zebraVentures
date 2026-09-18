
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import ShiftDay, WEEKDAY_CHOICES
from .serializers import ShiftDaySerializer


class ShiftDayViewSet(viewsets.ModelViewSet):
    queryset = ShiftDay.objects.select_related('shift').all()
    serializer_class = ShiftDaySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        shift_id = self.request.query_params.get('shift')
        if shift_id:
            qs = qs.filter(shift_id=shift_id)
        return qs

    @action(detail=False, methods=['get'])
    def weekdays(self, request):
        """Return the 7 weekday choices (constant)."""
        return Response([{'value': v, 'label': l} for v, l in WEEKDAY_CHOICES])
