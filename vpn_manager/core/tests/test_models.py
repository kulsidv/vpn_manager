from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError
from datetime import timedelta
from core.models import User, VpnConfig, TargetApp, Subscription


class UserModelTests(TestCase):
    """Тестирование вычисляемого свойства is_subscribed"""

    def setUp(self):
        self.user = User.objects.create_user(username='test_user', password='SecurePass123!')

    def test_is_subscribed_false_when_no_subscription(self):
        """У пользователя нет записи Subscription → False"""
        self.assertFalse(self.user.is_subscribed)

    def test_is_subscribed_true_when_active_and_valid(self):
        """Статус active + дата в будущем → True"""
        Subscription.objects.create(
            user=self.user,
            status='active',
            current_period_end=timezone.now() + timedelta(days=30)
        )
        self.assertTrue(self.user.is_subscribed)

    def test_is_subscribed_false_when_expired(self):
        """Статус active + дата в прошлом → False"""
        Subscription.objects.create(
            user=self.user,
            status='active',
            current_period_end=timezone.now() - timedelta(days=1)
        )
        self.assertFalse(self.user.is_subscribed)

    def test_is_subscribed_false_when_inactive(self):
        """Статус inactive + дата в будущем → False"""
        Subscription.objects.create(
            user=self.user,
            status='inactive',
            current_period_end=timezone.now() + timedelta(days=30)
        )
        self.assertFalse(self.user.is_subscribed)

    def test_is_subscribed_false_when_date_is_none(self):
        """Проверка безопасности short-circuit: None > datetime не вызывает ошибку"""
        Subscription.objects.create(
            user=self.user,
            status='active',
            current_period_end=None
        )
        self.assertFalse(self.user.is_subscribed)


class SubscriptionModelTests(TestCase):
    """Тестирование автоматической генерации gateway_id"""

    def test_gateway_ids_auto_generated_on_create(self):
        user = User.objects.create_user(username='sub_user', password='pass')
        sub = Subscription.objects.create(user=user)

        self.assertTrue(sub.gateway_customer_id.startswith('cust_'))
        self.assertTrue(sub.gateway_subscription_id.startswith('sub_'))
        self.assertEqual(len(sub.gateway_customer_id.split('_')[1]), 8)

    def test_gateway_ids_not_overwritten_on_update(self):
        user = User.objects.create_user(username='sub_user2', password='pass')
        sub = Subscription.objects.create(user=user)

        original_cust = sub.gateway_customer_id
        original_sub = sub.gateway_subscription_id

        # Обновляем другие поля (триггерит .save())
        sub.status = 'active'
        sub.save()
        sub.refresh_from_db()

        self.assertEqual(sub.gateway_customer_id, original_cust)
        self.assertEqual(sub.gateway_subscription_id, original_sub)


class TargetAppModelTests(TestCase):
    """Тестирование UniqueConstraint (user + package_name)"""

    def setUp(self):
        self.user1 = User.objects.create_user(username='user1', password='pass')
        self.user2 = User.objects.create_user(username='user2', password='pass')

    def test_unique_constraint_same_user(self):
        """Один пользователь не может добавить один пакет дважды"""
        TargetApp.objects.create(user=self.user1, package_name='com.example.app')
        with self.assertRaises(IntegrityError):
            TargetApp.objects.create(user=self.user1, package_name='com.example.app')

    def test_same_package_different_users_allowed(self):
        """Разные пользователи могут добавить один пакет"""
        TargetApp.objects.create(user=self.user1, package_name='com.example.app')
        TargetApp.objects.create(user=self.user2, package_name='com.example.app')
        self.assertEqual(TargetApp.objects.filter(package_name='com.example.app').count(), 2)