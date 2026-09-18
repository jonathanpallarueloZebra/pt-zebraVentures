from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.dynamic_fields.urls import entity_type_urlpatterns, entity_record_urlpatterns

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.authentication.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/agent/', include('apps.agent.urls')),
    path('api/email/', include('apps.email_service.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/catalog/', include('apps.catalog.urls')),
    path('api/workers/', include('apps.workers.urls')),
    path('api/rest-days/', include('apps.rest_days.urls')),
    path('api/restrictions/', include('apps.restrictions.urls')),
    path('api/planning/', include('apps.planning.urls')),
    path('api/absences/', include('apps.absences.urls')),
    path('api/branding/', include('apps.branding.urls')),
    path('api/entity-fields/', include('apps.dynamic_fields.urls')),
    path('api/entity-types/', include(entity_type_urlpatterns)),
    path('api/entity-records/', include(entity_record_urlpatterns)),
    path('api/shifts/', include('apps.shifts.urls')),
    path('api/shift_days/', include('apps.shift_days.urls')),
    path('api/assignments/', include('apps.assignments.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
