from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Branding
from .serializers import BrandingSerializer


class BrandingView(APIView):
    """
    GET  /api/branding/  → public, returns current branding config
    PATCH /api/branding/ → admin only, updates branding (supports multipart for image upload)
    """
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAdminUser()]

    def get(self, request):
        branding = Branding.get()
        serializer = BrandingSerializer(branding, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        branding = Branding.get()
        serializer = BrandingSerializer(
            branding, data=request.data,
            partial=True, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
