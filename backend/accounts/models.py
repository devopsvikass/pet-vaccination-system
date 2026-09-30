from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    ROLE_CHOICES = (
        ("owner", "Owner"),
        ("doctor", "Doctor"),
        ("admin", "Admin"),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=16)
    bio = models.TextField(blank=True, null=True)
    profile_photo = models.FileField(upload_to="doctor_profiles/", blank=True, null=True)
    DOCTOR_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("discarded", "Discarded"),
    )
    doctor_status = models.CharField(
        max_length=10,
        choices=DOCTOR_STATUS_CHOICES,
        default="approved",
    )
    doctor_approved = models.BooleanField(default=True)
    doctor_verified = models.BooleanField(default=True)
    reset_otp = models.CharField(max_length=6, blank=True, null=True)
    reset_otp_expires_at = models.DateTimeField(blank=True, null=True)
    admin_login_otp = models.CharField(max_length=128, blank=True, null=True)
    admin_login_otp_expires_at = models.DateTimeField(blank=True, null=True)
    admin_password_reset_otp = models.CharField(max_length=128, blank=True, null=True)
    admin_password_reset_otp_expires_at = models.DateTimeField(blank=True, null=True)
    created_by_doctor = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_owners",
    )
    dashboard_password = models.CharField(max_length=128, blank=True, null=True)
    force_password_reset = models.BooleanField(default=False)
