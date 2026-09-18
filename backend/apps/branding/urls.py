from django.urls import path
from .views import BrandingView

urlpatterns = [
    path('', BrandingView.as_view(), name='branding'),
]
