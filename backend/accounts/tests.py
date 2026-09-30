from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch
from datetime import timedelta


class AuthAndRoleTests(APITestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "Pass12345!"
        self.owner = self.user_model.objects.create_user(
            username="owner1",
            email="owner1@example.com",
            password=self.password,
            role="owner",
            phone="9000000001",
        )
        self.doctor = self.user_model.objects.create_user(
            username="doctor1",
            email="doctor1@example.com",
            password=self.password,
            role="doctor",
            phone="9000000002",
            doctor_status="approved",
            doctor_approved=True,
            doctor_verified=True,
        )
        self.admin = self.user_model.objects.create_user(
            username="mainadmin",
            email="mainadmin@example.com",
            password=self.password,
            role="admin",
            phone="9999999999",
            is_staff=True,
            is_superuser=True,
        )
        self.login_url = "/api/accounts/login/"
        self.all_users_url = "/api/accounts/all/"
        self.admin_otp_url = "/api/accounts/admin/email-otp/"
        self.admin_otp_verify_url = "/api/accounts/admin/email-otp/verify/"

    def login(self, identifier, role=None):
        payload = {"password": self.password}
        if "@" in identifier:
            payload["email"] = identifier
        else:
            payload["username"] = identifier
        if role:
            payload["role"] = role
        return self.client.post(self.login_url, payload, format="json")

    def test_owner_can_login(self):
        response = self.login(self.owner.username, role="owner")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "owner")
        self.assertIn("access", response.data)

    def test_doctor_can_login(self):
        response = self.login(self.doctor.username, role="doctor")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["role"], "doctor")
        self.assertIn("access", response.data)

    def test_admin_can_login_with_username(self):
        response = self.login(self.admin.username, role="admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["role"], "admin")

    def test_admin_can_login_with_email(self):
        response = self.login(self.admin.email, role="admin")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["role"], "admin")

    @patch("accounts.views.send_admin_otp")
    def test_admin_can_request_email_otp(self, send_otp):
        response = self.client.post(self.admin_otp_url, {"email": self.admin.email}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.admin_login_otp)
        self.assertIsNotNone(self.admin.admin_login_otp_expires_at)
        send_otp.assert_called_once()

    @patch("accounts.views.send_admin_otp", side_effect=RuntimeError("mail transport unavailable"))
    def test_admin_otp_delivery_failure_clears_otp_and_returns_safe_error(self, send_otp):
        response = self.client.post(self.admin_otp_url, {"email": self.admin.email}, format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertNotIn("mail transport unavailable", response.data["message"])
        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.admin_login_otp)
        self.assertIsNone(self.admin.admin_login_otp_expires_at)
        send_otp.assert_called_once()

    def test_admin_can_login_with_valid_email_otp(self):
        self.admin.admin_login_otp = make_password("123456")
        self.admin.admin_login_otp_expires_at = timezone.now() + timedelta(minutes=10)
        self.admin.save(update_fields=["admin_login_otp", "admin_login_otp_expires_at"])

        response = self.client.post(
            self.admin_otp_verify_url,
            {"email": self.admin.email, "otp": "123456"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertEqual(response.data["role"], "admin")
        self.admin.refresh_from_db()
        self.assertIsNone(self.admin.admin_login_otp)

    def test_admin_can_reset_password_with_valid_email_otp(self):
        self.admin.admin_password_reset_otp = make_password("123456")
        self.admin.admin_password_reset_otp_expires_at = timezone.now() + timedelta(minutes=2)
        self.admin.save(update_fields=["admin_password_reset_otp", "admin_password_reset_otp_expires_at"])

        response = self.client.post(
            "/api/accounts/admin/password-reset/email-otp/confirm/",
            {"email": self.admin.email, "otp": "123456", "new_password": "NewPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.check_password("NewPass123!"))
        self.assertIsNone(self.admin.admin_password_reset_otp)

    def test_role_mismatch_returns_403(self):
        response = self.login(self.admin.email, role="owner")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_all_users_requires_admin(self):
        owner_login = self.login(self.owner.username, role="owner")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_login.data['access']}")
        response = self.client.get(self.all_users_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        admin_login = self.login(self.admin.username, role="admin")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {admin_login.data['access']}")
        response = self.client.get(self.all_users_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
