import random
import smtplib
import secrets
import logging
from datetime import timedelta
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.permissions import AllowAny
from rest_framework import status
from .serializers import (
    RegisterSerializer,
    CreateAdminSerializer,
    LoginSerializer,
    UserProfileSerializer,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()
logger = logging.getLogger(__name__)


def send_admin_otp(email, otp, purpose):
    """Send an admin OTP by email without exposing the code in an API response."""
    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        logger.error("Admin OTP email delivery is not configured (missing SMTP credentials).")
        raise RuntimeError("Email OTP is not configured.")
    admin = User.objects.get(email__iexact=email, role="admin")
    try:
        sent_count = send_mail(
            subject=f"Pet Vaccination System Admin {purpose.title()} OTP",
            message=(
                f"Hello {admin.username},\n\n"
                f"Username: {admin.username}\n"
                "Role: Admin\n\n"
                f"Your admin {purpose} OTP is {otp}. It expires in 2 minutes."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            recipient_list=[email],
            fail_silently=False,
        )
        if sent_count != 1:
            raise RuntimeError("SMTP backend did not confirm delivery.")
    except Exception as exc:
        # Never log SMTP server text or credentials; the exception class and
        # numeric response code are enough to guide local troubleshooting.
        smtp_code = getattr(exc, "smtp_code", None)
        logger.error(
            "Admin OTP email delivery failed (%s, SMTP code %s). Check the "
            "SMTP host/port/TLS settings and credentials; Gmail requires an App Password.",
            type(exc).__name__,
            smtp_code if smtp_code is not None else "n/a",
        )
        raise RuntimeError(
            "Email delivery failed. Check the SMTP settings in backend/.env; "
            "Gmail requires an App Password, not your account password."
        ) from None


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Registered Successfully"})
        return Response(serializer.errors)


class AllUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "admin":
            return Response({"message": "Only admin can view users."}, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.all().values(
            "id",
            "username",
            "email",
            "role",
            "phone",
            "bio",
            "profile_photo",
            "doctor_status",
            "doctor_approved",
            "doctor_verified",
            "is_active",
        )
        return Response(users)


class ApprovedDoctorsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        doctors = User.objects.filter(
            role="doctor",
            doctor_status="approved",
            doctor_approved=True,
            doctor_verified=True,
            is_active=True,
        )
        data = [
            {
                "id": doctor.id,
                "username": doctor.username,
                "bio": doctor.bio,
                "profile_photo_url": request.build_absolute_uri(doctor.profile_photo.url)
                if doctor.profile_photo
                else None,
            }
            for doctor in doctors
        ]
        return Response(data)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        data = serializer.data
        data.update(
            {
                "id": request.user.id,
                "role": request.user.role,
                "doctor_status": request.user.doctor_status,
                "doctor_approved": request.user.doctor_approved,
                "doctor_verified": request.user.doctor_verified,
                "is_active": request.user.is_active,
                "force_password_reset": request.user.force_password_reset,
            }
        )
        return Response(data)


class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DeleteUser(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if request.user.role != "admin":
            return Response({"message": "Only admin can delete users."}, status=status.HTTP_403_FORBIDDEN)
        if request.user.id == pk:
            return Response({"message": "You cannot delete your own account."}, status=status.HTTP_400_BAD_REQUEST)
        user = get_object_or_404(User, id=pk)
        user.delete()
        return Response({"message": "User Deleted Successfully"})


class DoctorVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role != "admin":
            return Response({"message": "Only admin can verify doctors."}, status=status.HTTP_403_FORBIDDEN)

        doctor = User.objects.filter(id=pk, role="doctor").first()
        if not doctor:
            return Response({"message": "Doctor not found."}, status=status.HTTP_404_NOT_FOUND)

        approved = bool(request.data.get("approved", True))
        doctor.doctor_approved = approved
        doctor.doctor_verified = approved
        doctor.doctor_status = "approved" if approved else "pending"
        doctor.is_active = True
        doctor.save(update_fields=["doctor_approved", "doctor_verified", "doctor_status", "is_active"])

        state = "approved and verified" if approved else "marked as pending"
        return Response({"message": f"Doctor {state}."})


class ToggleUserActiveView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if request.user.role != "admin":
            return Response({"message": "Only admin can manage user status."}, status=status.HTTP_403_FORBIDDEN)
        if request.user.id == pk:
            return Response({"message": "You cannot disable your own account."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(id=pk).first()
        if not user:
            return Response({"message": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        is_active = request.data.get("is_active")
        if is_active is None:
            return Response({"message": "is_active is required."}, status=status.HTTP_400_BAD_REQUEST)

        if user.role == "doctor":
            if bool(is_active):
                user.doctor_status = "pending"
                user.doctor_approved = False
                user.doctor_verified = False
                user.is_active = True
                user.save(
                    update_fields=[
                        "doctor_status",
                        "doctor_approved",
                        "doctor_verified",
                        "is_active",
                    ]
                )
                return Response({"message": "Doctor moved to pending."})

            user.doctor_status = "discarded"
            user.doctor_approved = False
            user.doctor_verified = False
            user.is_active = True
            user.save(
                update_fields=[
                    "doctor_status",
                    "doctor_approved",
                    "doctor_verified",
                    "is_active",
                ]
            )
            return Response({"message": "Doctor discarded."})

        user.is_active = bool(is_active)
        user.save(update_fields=["is_active"])
        return Response({"message": "User status updated."})


class CreateAdminView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "admin":
            return Response({"message": "Only admin can create admin users."}, status=status.HTTP_403_FORBIDDEN)

        serializer = CreateAdminSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Admin account created successfully."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        selected_role = request.data.get("role")
        if selected_role and selected_role not in ["owner", "doctor", "admin"]:
            return Response({"detail": "Invalid role selected."}, status=status.HTTP_400_BAD_REQUEST)

        response = super().post(request, *args, **kwargs)
        identifier = (request.data.get("username") or request.data.get("email") or "").strip()
        user = User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier)).first()
        if not user:
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
        if selected_role and user.role != selected_role:
            return Response(
                {"detail": f"This account is not registered as {selected_role}."},
                status=status.HTTP_403_FORBIDDEN,
            )
        response.data["role"] = user.role
        response.data["user_id"] = user.id
        response.data["doctor_status"] = user.doctor_status
        response.data["force_password_reset"] = user.force_password_reset
        return response


class AdminEmailOtpRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response({"message": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        admins = User.objects.filter(email__iexact=email, role="admin", is_active=True)
        # Do not disclose whether an email belongs to an administrator.
        if admins.count() != 1:
            return Response({"message": "If this is a registered admin email, an OTP will be sent."})

        otp = f"{secrets.randbelow(1_000_000):06d}"
        admin = admins.first()
        admin.admin_login_otp = make_password(otp)
        # Saving a fresh hash replaces (and therefore invalidates) every prior OTP.
        admin.admin_login_otp_expires_at = timezone.now() + timedelta(minutes=2)
        admin.save(update_fields=["admin_login_otp", "admin_login_otp_expires_at"])

        try:
            send_admin_otp(email, otp, "login")
        except RuntimeError:
            admin.admin_login_otp = None
            admin.admin_login_otp_expires_at = None
            admin.save(update_fields=["admin_login_otp", "admin_login_otp_expires_at"])
            return Response(
                {
                    "message": (
                        "Email service is unavailable. Check the SMTP settings in "
                        "backend/.env; Gmail requires an App Password."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"message": "If this is a registered admin email, an OTP will be sent."})


class AdminEmailOtpVerifyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        otp = (request.data.get("otp") or "").strip()
        if not email or not otp:
            return Response({"message": "Email and OTP are required."}, status=status.HTTP_400_BAD_REQUEST)

        admin = User.objects.filter(email__iexact=email, role="admin", is_active=True).first()
        if (
            not admin
            or not admin.admin_login_otp
            or not admin.admin_login_otp_expires_at
            or admin.admin_login_otp_expires_at < timezone.now()
            or not check_password(otp, admin.admin_login_otp)
        ):
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_401_UNAUTHORIZED)

        admin.admin_login_otp = None
        admin.admin_login_otp_expires_at = None
        admin.save(update_fields=["admin_login_otp", "admin_login_otp_expires_at"])
        refresh = RefreshToken.for_user(admin)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "role": admin.role,
            "user_id": admin.id,
            "doctor_status": admin.doctor_status,
            "force_password_reset": admin.force_password_reset,
        })


class AdminPasswordResetEmailOtpRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        if not email:
            return Response({"message": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        admins = User.objects.filter(email__iexact=email, role="admin", is_active=True)
        if admins.count() != 1:
            return Response({"message": "If this is a registered admin email, an OTP will be sent."})

        otp = f"{secrets.randbelow(1_000_000):06d}"
        admin = admins.first()
        admin.admin_password_reset_otp = make_password(otp)
        admin.admin_password_reset_otp_expires_at = timezone.now() + timedelta(minutes=2)
        admin.save(update_fields=["admin_password_reset_otp", "admin_password_reset_otp_expires_at"])

        try:
            send_admin_otp(email, otp, "password reset")
        except RuntimeError:
            admin.admin_password_reset_otp = None
            admin.admin_password_reset_otp_expires_at = None
            admin.save(update_fields=["admin_password_reset_otp", "admin_password_reset_otp_expires_at"])
            return Response(
                {
                    "message": (
                        "Email service is unavailable. Check the SMTP settings in "
                        "backend/.env; Gmail requires an App Password."
                    )
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({"message": "If this is a registered admin email, an OTP will be sent."})


class AdminPasswordResetEmailOtpConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = (request.data.get("email") or "").strip()
        otp = (request.data.get("otp") or "").strip()
        new_password = request.data.get("new_password") or ""
        if not email or not otp or not new_password:
            return Response(
                {"message": "Email, OTP and new password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 8:
            return Response({"message": "New password must be at least 8 characters."}, status=status.HTTP_400_BAD_REQUEST)

        admin = User.objects.filter(email__iexact=email, role="admin", is_active=True).first()
        if (
            not admin
            or not admin.admin_password_reset_otp
            or not admin.admin_password_reset_otp_expires_at
            or admin.admin_password_reset_otp_expires_at < timezone.now()
            or not check_password(otp, admin.admin_password_reset_otp)
        ):
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_401_UNAUTHORIZED)

        admin.set_password(new_password)
        admin.admin_password_reset_otp = None
        admin.admin_password_reset_otp_expires_at = None
        admin.save(update_fields=["password", "admin_password_reset_otp", "admin_password_reset_otp_expires_at"])
        return Response({"message": "Password reset successful. You can now sign in."})


class ForgotPasswordView(APIView):
    def post(self, request):
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            return Response(
                {"message": "Email backend is not configured. Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD."},
                status=500,
            )

        email = request.data.get("email")
        role = request.data.get("role")
        if not email or not role:
            return Response({"message": "Email and role are required"}, status=400)
        if role not in ["owner", "doctor"]:
            return Response({"message": "Role must be owner or doctor"}, status=400)

        user = User.objects.filter(email=email, role=role).first()
        if not user:
            return Response({"message": "No account found for this email and role"}, status=404)

        otp = f"{random.randint(0, 999999):06d}"
        user.reset_otp = otp
        user.reset_otp_expires_at = timezone.now() + timedelta(minutes=10)
        user.save(update_fields=["reset_otp", "reset_otp_expires_at"])

        try:
            send_mail(
                subject="Pet Vaccination System Password Reset OTP",
                message=(
                    f"Hello {user.username},\n\n"
                    f"Username: {user.username}\n"
                    f"Role: {user.role.title()}\n\n"
                    f"Your OTP is {otp}. It is valid for 10 minutes."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
                recipient_list=[email],
                fail_silently=False,
            )
        except smtplib.SMTPAuthenticationError:
            return Response(
                {
                    "message": "Email authentication failed. Check EMAIL_HOST_USER and App Password."
                },
                status=502,
            )
        except smtplib.SMTPSenderRefused:
            return Response(
                {
                    "message": "Sender email rejected by SMTP server. Set DEFAULT_FROM_EMAIL to your authenticated email."
                },
                status=502,
            )
        return Response({"message": "OTP sent to your email"})


class ResetPasswordView(APIView):
    def post(self, request):
        email = request.data.get("email")
        role = request.data.get("role")
        otp = request.data.get("otp")
        new_password = request.data.get("new_password")

        if not email or not role or not otp or not new_password:
            return Response(
                {"message": "Email, role, OTP and new password are required"},
                status=400,
            )
        if role not in ["owner", "doctor"]:
            return Response({"message": "Role must be owner or doctor"}, status=400)

        user = User.objects.filter(email=email, role=role).first()
        if not user:
            return Response({"message": "No account found for this email and role"}, status=404)

        if user.reset_otp != otp:
            return Response({"message": "Invalid OTP"}, status=400)

        if not user.reset_otp_expires_at or user.reset_otp_expires_at < timezone.now():
            return Response({"message": "OTP expired. Request a new one."}, status=400)

        user.set_password(new_password)
        user.reset_otp = None
        user.reset_otp_expires_at = None
        user.force_password_reset = False
        user.save()
        return Response({"message": "Password reset successful"})


class FirstLoginPasswordResetView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        current_password = request.data.get("current_password")
        new_password = request.data.get("new_password")

        if not current_password or not new_password:
            return Response(
                {"message": "current_password and new_password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not request.user.check_password(current_password):
            return Response({"message": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        request.user.set_password(new_password)
        request.user.force_password_reset = False
        request.user.dashboard_password = None
        request.user.save(update_fields=["password", "force_password_reset", "dashboard_password"])
        return Response({"message": "Password updated successfully. You can continue now."})
