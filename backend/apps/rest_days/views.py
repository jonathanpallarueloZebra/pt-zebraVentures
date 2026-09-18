from datetime import datetime, timedelta

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import RestDay
from .serializers import RestDaySerializer


class RestDayViewSet(viewsets.ModelViewSet):
    queryset = RestDay.objects.select_related('worker').all()
    serializer_class = RestDaySerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def all(self, request):
        rest_days = self.get_queryset()
        serializer = self.get_serializer(rest_days, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def weekly(self, request):
        start_date = request.query_params.get('start')
        if not start_date:
            return Response({'error': 'start parameter required'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = start + timedelta(days=6)
            rest_days = RestDay.objects.filter(
                date__range=[start, end],
            ).select_related('worker')
            serializer = self.get_serializer(rest_days, many=True)
            return Response(serializer.data)
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST,
            )
