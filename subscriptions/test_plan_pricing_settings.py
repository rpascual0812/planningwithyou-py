from decimal import Decimal

from django.test import TestCase

from subscriptions.models import Subscription
from subscriptions.plan_pricing_settings import (
    ADMIN_BASE_PRICE_KEY,
    AI_BASE_PRICE_KEY,
    PRO_BASE_PRICE_KEY,
    plan_pricing_settings_payload,
    sync_subscription_plan_prices_from_system,
    update_plan_pricing_settings,
)
from system_settings.models import SystemSetting


class SubscriptionPlanPricingSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pro_monthly = Subscription.objects.filter(
            plan='pro',
            billing_cycle='monthly',
        ).first()
        cls.ai_monthly = Subscription.objects.filter(
            plan='ai',
            billing_cycle='monthly',
        ).first()
        cls.admin_monthly = Subscription.objects.filter(
            plan='admin',
            billing_cycle='monthly',
        ).first()
        if (
            cls.pro_monthly is None
            or cls.ai_monthly is None
            or cls.admin_monthly is None
        ):
            cls.skip_setup = True
            return
        cls.skip_setup = False

    def setUp(self):
        if getattr(self, 'skip_setup', True):
            self.skipTest('Subscription seed data missing')

    def test_update_plan_pricing_writes_system_table_and_syncs_subscriptions(self):
        payload = update_plan_pricing_settings(
            pro_base_price=Decimal('1095.00'),
            pro_price_per_user=Decimal('110.00'),
            ai_base_price=Decimal('1595.00'),
            ai_price_per_user=Decimal('160.00'),
            admin_base_price=Decimal('250.00'),
            admin_price_per_user=Decimal('25.00'),
        )

        self.assertEqual(payload['pro']['base_price'], '1095.00')
        self.assertEqual(payload['admin']['base_price'], '250.00')
        self.assertEqual(SystemSetting.objects.get(name=PRO_BASE_PRICE_KEY).value, '1095.00')
        self.assertEqual(SystemSetting.objects.get(name=AI_BASE_PRICE_KEY).value, '1595.00')
        self.assertEqual(SystemSetting.objects.get(name=ADMIN_BASE_PRICE_KEY).value, '250.00')

        self.pro_monthly.refresh_from_db()
        self.ai_monthly.refresh_from_db()
        self.admin_monthly.refresh_from_db()
        self.assertEqual(self.pro_monthly.base_price, Decimal('1095.00'))
        self.assertEqual(self.pro_monthly.price_per_user, Decimal('110.00'))
        self.assertEqual(self.ai_monthly.base_price, Decimal('1595.00'))
        self.assertEqual(self.ai_monthly.price_per_user, Decimal('160.00'))
        self.assertEqual(self.admin_monthly.base_price, Decimal('250.00'))
        self.assertEqual(self.admin_monthly.price_per_user, Decimal('25.00'))

    def test_sync_is_idempotent_when_values_unchanged(self):
        update_plan_pricing_settings(
            pro_base_price=Decimal('995.00'),
            pro_price_per_user=Decimal('100.00'),
            ai_base_price=Decimal('1495.00'),
            ai_price_per_user=Decimal('150.00'),
            admin_base_price=Decimal('0.00'),
            admin_price_per_user=Decimal('0.00'),
        )
        self.assertFalse(sync_subscription_plan_prices_from_system())
        self.assertEqual(
            plan_pricing_settings_payload()['pro']['base_price'],
            '995.00',
        )
