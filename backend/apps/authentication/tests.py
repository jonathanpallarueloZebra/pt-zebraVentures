from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

User = get_user_model()


class RegisterViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/register/'

    def test_register_success(self):
        data = {
            'email': 'nuevo@test.com',
            'username': 'nuevo',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
        }
        resp = self.client.post(self.url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='nuevo@test.com').exists())

    def test_register_password_mismatch(self):
        data = {
            'email': 'fail@test.com',
            'username': 'fail',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass!',
        }
        resp = self.client.post(self.url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email(self):
        User.objects.create_user(email='dup@test.com', username='dup', password='Pass12345!')
        data = {
            'email': 'dup@test.com',
            'username': 'dup2',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
        }
        resp = self.client.post(self.url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_short_password(self):
        data = {
            'email': 'short@test.com',
            'username': 'shortpw',
            'password': 'abc',
            'password_confirm': 'abc',
        }
        resp = self.client.post(self.url, data, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LoginViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = '/api/auth/login/'
        self.user = User.objects.create_user(
            email='login@test.com', username='loginuser', password='SecurePass123!'
        )

    def test_login_success(self):
        resp = self.client.post(self.url, {'email': 'login@test.com', 'password': 'SecurePass123!'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', resp.data)
        self.assertIn('refresh', resp.data)

    def test_login_wrong_password(self):
        resp = self.client.post(self.url, {'email': 'login@test.com', 'password': 'wrong'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        resp = self.client.post(self.url, {'email': 'nope@test.com', 'password': 'anything'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='profile@test.com', username='profileuser', password='SecurePass123!'
        )

    def test_profile_unauthenticated(self):
        resp = self.client.get('/api/auth/profile/')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_authenticated(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.get('/api/auth/profile/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['email'], 'profile@test.com')

    def test_profile_update(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.put('/api/auth/profile/', {
            'email': 'profile@test.com',
            'username': 'profileuser',
            'first_name': 'Juan',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Juan')

    def test_profile_cannot_change_staff(self):
        """is_staff and is_superuser are read-only."""
        self.client.force_authenticate(user=self.user)
        resp = self.client.put('/api/auth/profile/', {
            'email': 'profile@test.com',
            'username': 'profileuser',
            'is_staff': True,
            'is_superuser': True,
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
