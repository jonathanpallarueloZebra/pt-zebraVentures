from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import KindViewSet, KindValueViewSet, KindAttributeViewSet, KindValueAttributeViewSet

router = DefaultRouter()
router.register(r'kinds', KindViewSet, basename='kind')
router.register(r'values', KindValueViewSet, basename='kindvalue')
router.register(r'attributes', KindAttributeViewSet, basename='kindattribute')
router.register(r'value-attributes', KindValueAttributeViewSet, basename='kindvalueattribute')

urlpatterns = [
    path('', include(router.urls)),
]
