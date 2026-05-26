from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from core.models import User, VpnConfig, TargetApp, Subscription
import datetime


class ApiContractTests(TestCase):
    """Интеграционные тесты API: проверяют контракты, изоляцию и бизнес-правила"""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='contract_user', password='Secure123!')
        self.client.force_authenticate(user=self.user)

    def test_health_check_public(self):
        """Health check доступен без авторизации и возвращает статус ok"""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/health/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')

    def test_create_and_list_config(self):
        """Создание конфига привязывается к пользователю, список возвращает только свои"""
        resp_create = self.client.post('/api/configs/', {'config_text': 'wg0...', 'priority': 1}, format='json')
        self.assertEqual(resp_create.status_code, status.HTTP_201_CREATED)

        resp_list = self.client.get('/api/configs/')
        self.assertEqual(len(resp_list.data), 1)
        self.assertEqual(resp_list.data[0]['config_text'], 'wg0...')

    def test_user_data_isolation(self):
        """Пользователь А не видит конфиги пользователя Б"""
        other_user = User.objects.create_user(username='other_user', password='pass')
        VpnConfig.objects.create(user=other_user, config_text='secret_wg', priority=1)

        response = self.client.get('/api/configs/')
        self.assertEqual(len(response.data), 0)  # Строгая изоляция

    def test_free_tier_config_limit(self):
        """Без подписки можно создать только 1 конфиг. Второй → 400"""
        # Первый конфиг (успешно)
        self.client.post('/api/configs/', {'config_text': 'free1', 'priority': 1}, format='json')

        # Второй конфиг (должен упасть из-за валидации в сериализаторе)
        response = self.client.post('/api/configs/', {'config_text': 'free2', 'priority': 2}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_target_app_crud(self):
        """CRUD целевых приложений работает и изолирован"""
        resp = self.client.post('/api/target-apps/', {'package_name': 'com.test.app'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        resp_get = self.client.get('/api/target-apps/')
        self.assertEqual(len(resp_get.data), 1)
        self.assertEqual(resp_get.data[0]['package_name'], 'com.test.app')

    def test_me_get_returns_profile(self):
        """GET /users/me/ возвращает профиль с computed is_subscribed=False"""
        response = self.client.get('/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'contract_user')
        self.assertFalse(response.data['is_subscribed'])

    def test_me_delete_wrong_password(self):
        """Удаление аккаунта требует корректного пароля"""
        response = self.client.delete('/api/users/me/', {'password': 'wrong_pass'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_me_delete_correct_password(self):
        """Удаление аккаунта с верным паролем → 204, запись удалена"""
        response = self.client.delete('/api/users/me/', {'password': 'Secure123!'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(username='contract_user').exists())

    def test_billing_initiate_success(self):
        """POST /billing/ возвращает URL оплаты и session_id"""
        response = self.client.post('/api/billing/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('payment_url', response.data)
        self.assertIn('session_id', response.data)
        self.assertEqual(response.data['amount'], 299)
        self.assertTrue(response.data['payment_url'].startswith('http'))

    def test_billing_initiate_already_active(self):
        """Нельзя инициировать оплату, если подписка уже active"""
        Subscription.objects.create(user=self.user, status='active', current_period_end=timezone.now() + datetime.timedelta(days=30))
        response = self.client.post('/api/billing/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_billing_cancel_requires_active(self):
        """PATCH /billing/ на inactive подписке → 404"""
        response = self.client.patch('/api/billing/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_billing_cancel_active(self):
        """PATCH /billing/ на active подписке → 204, статус меняется на inactive"""
        sub = Subscription.objects.create(user=self.user, status='active')
        response = self.client.patch('/api/billing/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'inactive')

    def test_webhook_payment_succeeded(self):
        """Успешный вебхук активирует подписку и сдвигает expires_at"""
        sub = Subscription.objects.create(user=self.user, status='inactive')
        session_id = f"sess_{self.user.id}_999"

        response = self.client.post('/api/billing/webhook/', {
            'session_id': session_id, 'type': 'payment.succeeded'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'processed')

        sub.refresh_from_db()
        self.assertEqual(sub.status, 'active')
        self.assertEqual(sub.renewal_count, 1)
        self.assertGreater(sub.current_period_end, timezone.now())

    def test_webhook_idempotency(self):
        """Повторный вебхук не дублирует продление (already_processed)"""
        sub = Subscription.objects.create(user=self.user, status='active', renewal_count=1)
        session_id = f"sess_{self.user.id}_999"

        # Имитация ретрая шлюза
        response = self.client.post('/api/billing/webhook/', {
            'session_id': session_id, 'type': 'payment.succeeded'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'already_processed')
        sub.refresh_from_db()
        self.assertEqual(sub.renewal_count, 1)  # Счётчик НЕ увеличился

    def test_webhook_payment_failed(self):
        """Вебхук с failed event переводит подписку в inactive"""
        sub = Subscription.objects.create(user=self.user, status='active')
        session_id = f"sess_{self.user.id}_999"

        response = self.client.post('/api/billing/webhook/', {
            'session_id': session_id, 'type': 'payment.failed'
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sub.refresh_from_db()
        self.assertEqual(sub.status, 'inactive')

    def test_webhook_invalid_payload(self):
        """Отсутствие session_id или type → 400"""
        response = self.client.post('/api/billing/webhook/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
