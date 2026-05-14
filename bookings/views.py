from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import FormTemplate
from .serializers import FormTemplateSerializer


class FormTemplateViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = FormTemplateSerializer
    queryset = FormTemplate.objects.prefetch_related('fields__options').all()
