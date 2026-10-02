from django.urls import path

from .views import ResetearDemoView

urlpatterns = [
    path('resetear-demo/', ResetearDemoView.as_view(), name='resetear-demo'),
]
