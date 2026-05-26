from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class RegistrationAndAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.register_url = '/api/auth/register/'
        self.login_url = '/api/auth/login/'

    def test_registration_success(self):
        """Happy-path: валидные данные → 201, пользователь создан"""
        payload = {
            'username': 'valid_user',
            'email': 'valid@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!'
        }
        response = self.client.post(self.register_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='valid_user').exists())

    def test_read_only_fields_rejected(self):
        """Security: попытка передать is_subscribed → 400, защита от mass-assignment"""
        payload = {
            'username': 'attacker',
            'email': 'atk@test.com',
            'password': 'StrongPass123!',
            'password_confirm': 'StrongPass123!',
            'is_subscribed': True  # Попытка обхода
        }
        response = self.client.post(self.register_url, payload, format='json')
        # Ваш to_internal_value явно кидает ValidationError → DRF возвращает 400
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('is_subscribed', response.data)
        self.assertFalse(User.objects.filter(username='attacker').exists())

    def test_jwt_issued_on_login(self):
        """Login smoke-test: проверка, что SIMPLE_JWT настроен и отдаёт токены"""
        User.objects.create_user(username='login_user', password='Login1234!')
        response = self.client.post(self.login_url, {
            'username': 'login_user', 'password': 'Login1234!'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
