from rest_framework import serializers

from .models import SupplierType


class SupplierTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierType
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields
