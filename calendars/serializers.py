from rest_framework import serializers

from bookings.scope import bookings_for_user
from contacts.scope import contacts_for_user

from .models import Calendar, CalendarStatus, AppointmentReminder, ScheduledAppointmentReminder
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
            'quotation',
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
            self.fields['quotation'].queryset = bookings_for_user(request.user)

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

        booking = attrs.get('quotation')
        if booking is None and self.instance is not None:
            booking = self.instance.quotation
        if booking is not None:
            if booking.account_id != aid:
                raise serializers.ValidationError({'quotation': ['Invalid booking for this account.']})
            if booking.company_id != company_id:
                raise serializers.ValidationError({'quotation': ['Invalid booking for this company.']})

        return attrs


class AppointmentReminderSerializer(serializers.ModelSerializer):
    calendar_statuses = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CalendarStatus.objects.none(),
        required=False,
    )
    company = serializers.IntegerField(source='company_id', read_only=True)
    type = serializers.ChoiceField(
        source='reminder_type',
        choices=AppointmentReminder.ReminderType.choices,
    )

    class Meta:
        model = AppointmentReminder
        fields = [
            'id',
            'company',
            'calendar_statuses',
            'calendar',
            'frequency',
            'unit',
            'type',
            'is_active',
            'created_by',
            'created_at',
            'updated_at',
            'deleted_at',
        ]
        read_only_fields = ['id', 'company', 'created_by', 'created_at', 'updated_at', 'deleted_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            status_qs = calendar_statuses_for_user(request.user)
            self.fields['calendar_statuses'].queryset = status_qs
            child = getattr(self.fields['calendar_statuses'], 'child_relation', None)
            if child is not None:
                child.queryset = status_qs

    def validate_frequency(self, value):
        if value < 1:
            raise serializers.ValidationError('Frequency must be at least 1.')
        return value

    def validate_calendar_statuses(self, statuses):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return statuses
        aid = request.user.account_id
        for status in statuses:
            if status.account_id != aid:
                raise serializers.ValidationError('Invalid calendar status for this account.')
        return statuses

    def create(self, validated_data):
        statuses = validated_data.pop('calendar_statuses', [])
        reminder = super().create(validated_data)
        if statuses:
            reminder.calendar_statuses.set(statuses)
        return reminder

    def update(self, instance, validated_data):
        statuses = validated_data.pop('calendar_statuses', None)
        reminder = super().update(instance, validated_data)
        if statuses is not None:
            reminder.calendar_statuses.set(statuses)
        return reminder


class ScheduledAppointmentReminderSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source='calendar_event.title', read_only=True)
    event_start = serializers.DateTimeField(source='calendar_event.start', read_only=True)
    event_end = serializers.DateTimeField(source='calendar_event.end', read_only=True)
    calendar_event_id = serializers.IntegerField(read_only=True)
    company_id = serializers.IntegerField(read_only=True)
    reminder_frequency = serializers.IntegerField(
        source='appointment_reminder.frequency',
        read_only=True,
        allow_null=True,
    )
    reminder_unit = serializers.CharField(
        source='appointment_reminder.unit',
        read_only=True,
        allow_null=True,
    )
    reminder_calendar = serializers.CharField(
        source='appointment_reminder.calendar',
        read_only=True,
        allow_null=True,
    )
    email_log_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = ScheduledAppointmentReminder
        fields = [
            'id',
            'company_id',
            'calendar_event_id',
            'event_title',
            'event_start',
            'event_end',
            'appointment_reminder',
            'reminder_frequency',
            'reminder_unit',
            'reminder_calendar',
            'recipient_role',
            'recipient_email',
            'recipient_name',
            'send_at',
            'status',
            'email_log_id',
            'error',
            'sent_at',
            'created_at',
            'updated_at',
            'deleted_at',
        ]
        read_only_fields = fields
