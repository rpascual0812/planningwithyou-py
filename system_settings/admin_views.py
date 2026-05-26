from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from planningwithyou.permissions import FeatureAccess

from .models import SystemSetting
from .serializers import SystemSettingSerializer


class SystemLegalAdminViewSet(viewsets.ModelViewSet):
    """Admin CRUD for platform legal HTML documents stored in ``system``."""

    feature_key = 'admin_legal'
    permission_classes = [IsAuthenticated, FeatureAccess]
    serializer_class = SystemSettingSerializer
    lookup_field = 'name'
    lookup_value_regex = r'[\w_]+'
    http_method_names = ['get', 'head', 'options', 'patch', 'put']

    def get_queryset(self):
        return SystemSetting.legal_documents_queryset()
