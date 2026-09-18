from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EntityFieldViewSet, EntityTypeViewSet, EntityRecordViewSet

router = DefaultRouter()
router.register(r'', EntityFieldViewSet, basename='entity-field')

types_router = DefaultRouter()
types_router.register(r'', EntityTypeViewSet, basename='entity-type')

records_router = DefaultRouter()
records_router.register(r'', EntityRecordViewSet, basename='entity-record')

urlpatterns = [
    path('', include(router.urls)),
]

entity_type_urlpatterns = [path('', include(types_router.urls))]
entity_record_urlpatterns = [path('', include(records_router.urls))]
