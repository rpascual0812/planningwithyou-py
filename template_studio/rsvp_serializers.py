from rest_framework import serializers


class PublicRsvpSubmitSerializer(serializers.Serializer):
    element_id = serializers.CharField(max_length=64)
    fields = serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=2000),
        allow_empty=True,
    )


class PublicRsvpRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    element_id = serializers.CharField()
    fields_data = serializers.DictField(child=serializers.CharField())
    created_at = serializers.DateTimeField()


class PublicRsvpListSerializer(serializers.Serializer):
    title = serializers.CharField()
    slug = serializers.CharField()
    field_columns = serializers.ListField(child=serializers.DictField())
    results = PublicRsvpRecordSerializer(many=True)
