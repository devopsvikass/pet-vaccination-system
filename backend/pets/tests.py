from datetime import date
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Pet


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST_USER="noreply@example.com",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class PetsRoleAccessTests(APITestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.password = "Pass12345!"

        self.owner = self.user_model.objects.create_user(
            username="owner2",
            email="owner2@example.com",
            password=self.password,
            role="owner",
            phone="9100000001",
        )
        self.admin = self.user_model.objects.create_user(
            username="admin2",
            email="admin2@example.com",
            password=self.password,
            role="admin",
            phone="9100000002",
            is_staff=True,
            is_superuser=True,
        )
        self.doctor_verified = self.user_model.objects.create_user(
            username="doctor_verified",
            email="doctorv@example.com",
            password=self.password,
            role="doctor",
            phone="9100000003",
            doctor_status="approved",
            doctor_approved=True,
            doctor_verified=True,
        )
        self.doctor_pending = self.user_model.objects.create_user(
            username="doctor_pending",
            email="doctorp@example.com",
            password=self.password,
            role="doctor",
            phone="9100000004",
            doctor_status="pending",
            doctor_approved=False,
            doctor_verified=False,
        )
        self.pet = Pet.objects.create(
            owner=self.owner,
            name="Bruno",
            age="2.00",
            breed="Beagle",
            vaccination_date=date.today(),
        )

    def login(self, username, role):
        response = self.client.post(
            "/api/accounts/login/",
            {"username": username, "password": self.password, "role": role},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")

    def test_only_owner_can_add_pet(self):
        payload = {
            "name": "Milo",
            "age": "1.50",
            "breed": "Labrador",
            "vaccination_date": str(date.today()),
        }

        self.login(self.owner.username, "owner")
        response = self.client.post("/api/pets/add/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.login(self.doctor_verified.username, "doctor")
        response = self.client.post("/api/pets/add/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.login(self.admin.username, "admin")
        response = self.client.post("/api/pets/add/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pets_all_access_by_role(self):
        self.login(self.owner.username, "owner")
        response = self.client.get("/api/pets/all/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.login(self.doctor_verified.username, "doctor")
        response = self.client.get("/api/pets/all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.login(self.admin.username, "admin")
        response = self.client.get("/api/pets/all/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pending_doctor_cannot_view_owner_pets(self):
        self.login(self.doctor_pending.username, "doctor")
        response = self.client.get(f"/api/pets/owner/{self.owner.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verified_doctor_can_create_owner_and_pet(self):
        self.login(self.doctor_verified.username, "doctor")
        payload = {
            "owner_username": "new_owner_doc",
            "owner_email": "new_owner_doc@example.com",
            "owner_phone": "+919220000001",
            "owner_password": "Owner@12345",
            "pet_name": "Rocky",
            "pet_age": "1.20",
            "pet_breed": "Pug",
            "pet_vaccination_date": str(date.today()),
        }
        response = self.client.post("/api/pets/doctor/add-owner-pet/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["message"], "Owner and pet created successfully.")
        self.assertTrue(response.data["email_sent"])
        self.assertEqual(response.data["email_recipient"], "new_owner_doc@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Created by doctor: doctor_verified", mail.outbox[0].body)
        self.assertIn("Temporary password: Owner@12345", mail.outbox[0].body)
        self.assertIn("Pet name: Rocky", mail.outbox[0].body)
        self.assertIn(f"Last vaccination date: {date.today()}", mail.outbox[0].body)
        self.assertTrue(Pet.objects.filter(name="Rocky").exists())
        self.assertTrue(self.user_model.objects.filter(username="new_owner_doc", role="owner").exists())
        owner = self.user_model.objects.get(username="new_owner_doc")
        self.assertEqual(owner.created_by_doctor_id, self.doctor_verified.id)
        self.assertTrue(owner.force_password_reset)
        self.assertIsNone(owner.dashboard_password)

        self.client.credentials()
        login_response = self.client.post(
            "/api/accounts/login/",
            {"username": "new_owner_doc", "password": "Owner@12345", "role": "owner"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertTrue(login_response.data["force_password_reset"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        my_pets = self.client.get("/api/pets/my/")
        self.assertEqual(my_pets.status_code, status.HTTP_403_FORBIDDEN)

        reset_response = self.client.post(
            "/api/accounts/first-login-reset/",
            {"current_password": "Owner@12345", "new_password": "Owner@12345New"},
            format="json",
        )
        self.assertEqual(reset_response.status_code, status.HTTP_200_OK)

        self.client.credentials()
        relogin_response = self.client.post(
            "/api/accounts/login/",
            {"username": "new_owner_doc", "password": "Owner@12345New", "role": "owner"},
            format="json",
        )
        self.assertEqual(relogin_response.status_code, status.HTTP_200_OK)
        self.assertFalse(relogin_response.data["force_password_reset"])
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {relogin_response.data['access']}")
        my_pets = self.client.get("/api/pets/my/")
        self.assertEqual(my_pets.status_code, status.HTTP_200_OK)
        self.assertEqual(len(my_pets.data), 1)
        self.assertEqual(my_pets.data[0]["name"], "Rocky")

    def test_pending_doctor_cannot_create_owner_and_pet(self):
        self.login(self.doctor_pending.username, "doctor")
        payload = {
            "owner_username": "blocked_owner",
            "owner_email": "blocked_owner@example.com",
            "owner_phone": "9220000002",
            "pet_name": "BlockedPet",
            "pet_age": "1.00",
            "pet_breed": "Mixed",
            "pet_vaccination_date": str(date.today()),
        }
        response = self.client.post("/api/pets/doctor/add-owner-pet/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_can_view_created_owners_with_passwords(self):
        self.login(self.doctor_verified.username, "doctor")
        create_payload = {
            "owner_username": "owner_list_1",
            "owner_email": "owner_list_1@example.com",
            "owner_phone": "+919220000003",
            "owner_password": "OwnerList@123",
            "pet_name": "Tiger",
            "pet_age": "3.00",
            "pet_breed": "Indie",
            "pet_vaccination_date": str(date.today()),
        }
        create_response = self.client.post("/api/pets/doctor/add-owner-pet/", create_payload, format="json")
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)

        response = self.client.get("/api/pets/doctor/created-owners/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["username"], "owner_list_1")
        self.assertTrue(response.data[0]["force_password_reset"])
        self.assertEqual(response.data[0]["pets"][0]["name"], "Tiger")
