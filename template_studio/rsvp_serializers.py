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


class PublicRsvpBreakdownSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    percent = serializers.IntegerField()


class PublicRsvpAnalyticsSerializer(serializers.Serializer):
    total_views = serializers.IntegerField()
    expected_visitors = serializers.IntegerField()
    days_remaining = serializers.IntegerField(allow_null=True)
    will_go = serializers.IntegerField()
    will_not_go = serializers.IntegerField()
    awaiting_reply = serializers.IntegerField()
    total_guests = serializers.IntegerField()
    breakdown = PublicRsvpBreakdownSerializer(many=True)


class PublicRsvpListSerializer(serializers.Serializer):
    title = serializers.CharField()
    slug = serializers.CharField()
    field_columns = serializers.ListField(child=serializers.DictField())
    analytics = PublicRsvpAnalyticsSerializer()
    results = PublicRsvpRecordSerializer(many=True)
