from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from .models import Kind, KindAttribute, KindValue, KindValueAttribute
from .serializers import (
    KindSerializer, KindListSerializer, KindValueSerializer,
    KindAttributeSerializer, KindValueAttributeSerializer,
)


class KindViewSet(viewsets.ModelViewSet):
    queryset = Kind.objects.prefetch_related('attributes', 'values__attributes__attribute').all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action == 'list':
            return KindListSerializer
        return KindSerializer

    @action(detail=True, methods=['get'], url_path='values')
    def get_values(self, request, pk=None):
        kind = self.get_object()
        values = kind.values.filter(active=True).prefetch_related('attributes__attribute')
        serializer = KindValueSerializer(values, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='by-code/(?P<code>[^/.]+)')
    def by_code(self, request, code=None):
        try:
            kind = Kind.objects.prefetch_related(
                'attributes', 'values__attributes__attribute'
            ).get(code=code)
        except Kind.DoesNotExist:
            return Response({'error': f'Kind "{code}" not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = KindSerializer(kind)
        return Response(serializer.data)


class KindValueViewSet(viewsets.ModelViewSet):
    queryset = KindValue.objects.select_related('kind').prefetch_related('attributes__attribute').all()
    serializer_class = KindValueSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        kind_code = self.request.query_params.get('kind')
        if kind_code:
            qs = qs.filter(kind__code=kind_code)
        return qs


class KindAttributeViewSet(viewsets.ModelViewSet):
    queryset = KindAttribute.objects.select_related('kind').all()
    serializer_class = KindAttributeSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        kind_id = self.request.query_params.get('kind')
        if kind_id:
            qs = qs.filter(kind_id=kind_id)
        return qs


class KindValueAttributeViewSet(viewsets.ModelViewSet):
    queryset = KindValueAttribute.objects.select_related('kind_value', 'attribute').all()
    serializer_class = KindValueAttributeSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = super().get_queryset()
        kind_value_id = self.request.query_params.get('kind_value')
        if kind_value_id:
            qs = qs.filter(kind_value_id=kind_value_id)
        return qs
