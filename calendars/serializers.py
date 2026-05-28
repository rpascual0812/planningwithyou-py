from rest_framework import serializers

from bookings.scope import bookings_for_user
from contacts.scope import contacts_for_user

from .models import Calendar, CalendarStatus
from .scope import calendar_statuses_for_user


class CalendarStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalendarStatus
        fields = [
            'id',
            'title',
            'description',
            'text_color',
            'background_color',
            'sort_order',
            'created_by',
            'created_at',
            'deleted_at',
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'deleted_at']


class CalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calendar
        fields = [
            'id',
            'title',
            'location',
            'start',
            'end',
            'repeat_type',
            'repeat_end',
            'status',
            'contact',
            'booking',
            'company',
            'created_by',
            'created_at',
            'deleted_at',
        ]
        read_only_fields = ['id', 'company', 'created_by', 'created_at', 'deleted_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            self.fields['status'].queryset = calendar_statuses_for_user(request.user)
            self.fields['contact'].queryset = contacts_for_user(request.user)
            self.fields['booking'].queryset = bookings_for_user(request.user)

    def validate(self, attrs):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return attrs
        aid = request.user.account_id
        company_id = request.user.company_id

        start = attrs.get('start') or (self.instance.start if self.instance else None)
        end = attrs.get('end') or (self.instance.end if self.instance else None)
        if start and end and end < start:
            raise serializers.ValidationError({'end': ['End must be on or after start.']})

        status = attrs.get('status') or (self.instance.status if self.instance else None)
        if status is not None and status.account_id != aid:
            raise serializers.ValidationError({'status': ['Invalid status for this account.']})

        contact = attrs.get('contact')
        if contact is None and self.instance is not None:
            contact = self.instance.contact
        if contact is not None:
            if contact.account_id != aid:
                raise serializers.ValidationError({'contact': ['Invalid contact for this account.']})
            if contact.company_org_id != company_id:
                raise serializers.ValidationError({'contact': ['Invalid contact for this company.']})

        booking = attrs.get('booking')
        if booking is None and self.instance is not None:
            booking = self.instance.booking
        if booking is not None:
            if booking.account_id != aid:
                raise serializers.ValidationError({'booking': ['Invalid booking for this account.']})
            if booking.company_id != company_id:
                raise serializers.ValidationError({'booking': ['Invalid booking for this company.']})

        return attrs
