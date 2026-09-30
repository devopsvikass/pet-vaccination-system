import secrets
import smtplib
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import Pet, DoctorSummary
from .serializers import (
    PetSerializer,
    SummarySerializer,
    PetProfileSerializer,
    DoctorCreateOwnerPetSerializer,
)
from accounts.models import User


def _doctor_is_verified(user):
    return (
        user.role == "doctor"
        and user.doctor_status == "approved"
        and user.doctor_approved
        and user.doctor_verified
    )


def _doctor_verification_error():
    return Response(
        {"message": "Doctor account must be admin approved and verified."},
        status=status.HTTP_403_FORBIDDEN,
    )


def _owner_must_reset_password(user):
    return user.role == "owner" and user.force_password_reset


def _owner_password_reset_required_error():
    return Response(
        {"message": "Please reset your temporary password before accessing pet features."},
        status=status.HTTP_403_FORBIDDEN,
    )


# =======================
# OWNER FEATURES
# =======================

class AddPet(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if _owner_must_reset_password(request.user):
            return _owner_password_reset_required_error()
        if request.user.role != "owner":
            return Response({"message": "Only owners can add pets."}, status=status.HTTP_403_FORBIDDEN)
        payload = request.data.copy()
        payload["owner"] = request.user.id
        serializer = PetSerializer(data=payload, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Pet Added"})
        return Response(serializer.errors)


class UpdatePet(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if _owner_must_reset_password(request.user):
            return _owner_password_reset_required_error()
        pet = get_object_or_404(Pet, id=pk)
        if request.user.role == "owner" and pet.owner_id != request.user.id:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role not in ["owner", "admin"]:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        serializer = PetSerializer(pet, data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Pet Updated"})
        return Response(serializer.errors)


class DeletePet(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if _owner_must_reset_password(request.user):
            return _owner_password_reset_required_error()
        pet = get_object_or_404(Pet, id=pk)
        if request.user.role == "owner" and pet.owner_id != request.user.id:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role not in ["owner", "admin"]:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        pet.delete()
        return Response({"message":"Pet Deleted"})


class OwnerPets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, owner_id):
        if _owner_must_reset_password(request.user):
            return _owner_password_reset_required_error()
        if request.user.role == "doctor" and not _doctor_is_verified(request.user):
            return _doctor_verification_error()
        if request.user.role == "owner" and request.user.id != owner_id:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        pets = Pet.objects.filter(owner_id=owner_id)
        serializer = PetSerializer(pets, many=True, context={"request": request})
        return Response(serializer.data)

class MyPets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if _owner_must_reset_password(request.user):
            return _owner_password_reset_required_error()
        if request.user.role != "owner":
            return Response({"message": "Only owners can view this list."}, status=status.HTTP_403_FORBIDDEN)
        pets = Pet.objects.filter(owner=request.user)
        serializer = PetSerializer(pets, many=True, context={"request": request})
        return Response(serializer.data)


class PetDetail(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if _owner_must_reset_password(request.user):
            return _owner_password_reset_required_error()
        pet = get_object_or_404(Pet, id=pk)
        if request.user.role == "doctor" and not _doctor_is_verified(request.user):
            return _doctor_verification_error()
        if request.user.role == "owner" and pet.owner_id != request.user.id:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)

        serializer = PetProfileSerializer(pet, context={"request": request})
        return Response(serializer.data)


# =======================
# DOCTOR FEATURES
# =======================

class AddSummary(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "doctor":
            return Response({"message": "Only doctors can add summaries."}, status=403)
        if not _doctor_is_verified(request.user):
            return _doctor_verification_error()

        serializer = SummarySerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            next_vaccination_at = serializer.validated_data.get("next_vaccination_at")
            if next_vaccination_at and next_vaccination_at.date() < timezone.localdate():
                return Response(
                    {"next_vaccination_at": ["Vaccination date cannot be in the past."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            serializer.save(doctor=request.user)
            return Response({"message":"Summary Added"})
        return Response(serializer.errors)


class UpdateSummary(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        summary = get_object_or_404(DoctorSummary, id=pk)
        serializer = SummarySerializer(summary, data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"message":"Summary Updated"})
        return Response(serializer.errors)


class DeleteSummary(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        summary = get_object_or_404(DoctorSummary, id=pk)
        summary.delete()
        return Response({"message":"Summary Deleted"})


class DoctorCreateOwnerPet(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if request.user.role != "doctor":
            return Response({"message": "Only doctors can create owner records."}, status=status.HTTP_403_FORBIDDEN)
        if not _doctor_is_verified(request.user):
            return _doctor_verification_error()

        serializer = DoctorCreateOwnerPetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        if User.objects.filter(username__iexact=data["owner_username"]).exists():
            return Response({"message": "Owner username already exists."}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=data["owner_email"]).exists():
            return Response({"message": "Owner email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        owner_password = data.get("owner_password") or f"Pet@{secrets.token_hex(4)}"

        try:
            with transaction.atomic():
                owner = User.objects.create_user(
                    username=data["owner_username"],
                    email=data["owner_email"],
                    password=owner_password,
                    role="owner",
                    phone=data["owner_phone"],
                    doctor_status="approved",
                    doctor_approved=True,
                    doctor_verified=True,
                    is_active=True,
                    created_by_doctor=request.user,
                    dashboard_password=None,
                    force_password_reset=True,
                )
                pet = Pet.objects.create(
                    owner=owner,
                    name=data["pet_name"],
                    age=data["pet_age"],
                    breed=data["pet_breed"],
                    vaccination_date=data["pet_vaccination_date"],
                )
                send_mail(
                    subject="Your Pet Vaccination System owner account",
                    message=(
                        f"Hello {owner.username},\n\n"
                        "A pet owner account was created for you by your doctor.\n\n"
                        f"Created by doctor: {request.user.get_full_name() or request.user.username}\n"
                        f"Username: {owner.username}\n"
                        f"Temporary password: {owner_password}\n"
                        f"Phone: {owner.phone}\n\n"
                        "Pet details\n"
                        f"Pet name: {pet.name}\n"
                        f"Breed: {pet.breed}\n"
                        f"Age: {pet.age}\n"
                        f"Last vaccination date: {pet.vaccination_date}\n\n"
                        "For security, sign in with the temporary password and reset it "
                        "immediately when prompted. Your account will require a password "
                        "reset before you can use pet features.\n\n"
                        "If you did not expect this account, contact your doctor."
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
                    recipient_list=[owner.email],
                    fail_silently=False,
                )
        except (smtplib.SMTPException, OSError, RuntimeError) as exc:
            return Response(
                {"message": "Owner was not created because the welcome email could not be sent."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "message": "Owner and pet created successfully.",
                "owner_id": owner.id,
                "pet_id": pet.id,
                "generated_password": None if data.get("owner_password") else owner_password,
                "email_sent": True,
                "email_recipient": owner.email,
            },
            status=status.HTTP_201_CREATED,
        )


class DoctorCreatedOwnersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "doctor":
            return Response({"message": "Only doctors can view created owners."}, status=status.HTTP_403_FORBIDDEN)
        if not _doctor_is_verified(request.user):
            return _doctor_verification_error()

        owners = User.objects.filter(role="owner", created_by_doctor=request.user).order_by("-id")
        data = []
        for owner in owners:
            owner_pets = Pet.objects.filter(owner=owner).values("id", "name", "breed")
            data.append(
                {
                    "id": owner.id,
                    "username": owner.username,
                    "email": owner.email,
                    "phone": owner.phone,
                    "force_password_reset": owner.force_password_reset,
                    "pets": list(owner_pets),
                }
            )
        return Response(data)


# =======================
# ADMIN FEATURES
# =======================

class AllPets(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ["doctor", "admin"]:
            return Response({"message": "Not allowed"}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role == "doctor" and not _doctor_is_verified(request.user):
            return _doctor_verification_error()
        phone = request.query_params.get("phone")
        pets = Pet.objects.select_related("owner").all()
        if phone:
            pets = pets.filter(owner__phone__icontains=phone)
        serializer = PetSerializer(pets, many=True, context={"request": request})
        return Response(serializer.data)


class ReminderLogsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != "admin":
            return Response({"message": "Only admin can view reminder logs."}, status=status.HTTP_403_FORBIDDEN)

        summaries = (
            DoctorSummary.objects.select_related("pet", "pet__owner", "doctor")
            .order_by("-created_at")
        )

        logs = [
            {
                "id": item.id,
                "pet_name": item.pet.name,
                "owner_email": item.pet.owner.email,
                "doctor_username": item.doctor.username,
                "next_vaccination_at": item.next_vaccination_at,
                "reminder_sent": item.reminder_sent,
                "reminder_sent_at": item.reminder_sent_at,
                "created_at": item.created_at,
            }
            for item in summaries
        ]
        return Response(logs)


class DeleteUser(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        user = User.objects.get(id=pk)
        user.delete()
        return Response({"message":"User Deleted"})
    

# class AllPets(APIView):
#     def get(self, request):
#         pets = Pet.objects.all()
#         serializer = PetSerializer(pets, many=True)
#         return Response(serializer.data)


from django.http import JsonResponse
from django.db import connection

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

        return JsonResponse({
            "status": "ok",
            "database": "connected"
        })

    except Exception:
        return JsonResponse({
            "status": "error",
            "database": "unavailable"
        }, status=503)
