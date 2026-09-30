from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import User
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.exceptions import AuthenticationFailed
import re
from .phone_validation import validate_international_phone


class RegisterSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.SerializerMethodField(read_only=True)

    def get_profile_photo_url(self, obj):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "role",
            "phone",
            "bio",
            "profile_photo",
            "profile_photo_url",
            "doctor_status",
            "doctor_approved",
            "doctor_verified",
        ]
        read_only_fields = ["doctor_status", "doctor_approved", "doctor_verified"]
        extra_kwargs = {'password': {'write_only': True}}

    def validate_role(self, value):
        if value == "admin":
            raise serializers.ValidationError("Admin accounts cannot be self-registered.")
        return value

    def validate_phone(self, value):
        normalized = validate_international_phone(value)
        if normalized.startswith("+91") and not re.fullmatch(r"\+91[6-9]\d{9}", normalized):
            raise serializers.ValidationError(
                "Indian phone numbers must contain 10 digits and start with 6, 7, 8, or 9."
            )
        return normalized

    def create(self, validated_data):
        role = validated_data.get("role")
        if role == "doctor":
            validated_data["doctor_status"] = "pending"
            validated_data["doctor_approved"] = False
            validated_data["doctor_verified"] = False
        else:
            validated_data["doctor_status"] = "approved"
            validated_data["doctor_approved"] = True
            validated_data["doctor_verified"] = True
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    profile_photo_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "phone",
            "bio",
            "profile_photo",
            "profile_photo_url",
        ]
        extra_kwargs = {
            "username": {"required": False},
            "email": {"required": False},
            "phone": {"required": False},
            "bio": {"required": False},
            "profile_photo": {"required": False},
        }

    def get_profile_photo_url(self, obj):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        return request.build_absolute_uri(url) if request else url

    def validate_username(self, value):
        if not value:
            return value
        # If the username is unchanged, allow the update even if duplicates exist in DB
        if self.instance and value == getattr(self.instance, "username", None):
            return value
        qs = User.objects.filter(username__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Username already in use.")
        return value

    def validate_email(self, value):
        if not value:
            return value
        # Allow keeping the same email even if other accounts share it (legacy data)
        if self.instance and value.lower() == (getattr(self.instance, "email", "") or "").lower():
            return value
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Email already in use.")
        return value


class CreateAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email", "password", "phone", "bio", "profile_photo"]
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        return User.objects.create_user(
            **validated_data,
            role="admin",
            is_staff=True,
            is_superuser=True,
            doctor_status="approved",
            doctor_approved=True,
            doctor_verified=True,
        )


class LoginSerializer(TokenObtainPairSerializer):
    # Allow clients to send either "username" or "email" as identifier.
    email = serializers.EmailField(required=False)

    def to_internal_value(self, data):
        mutable = data.copy()
        identifier = (mutable.get("username") or mutable.get("email") or "").strip()
        if identifier and not mutable.get("username"):
            mutable["username"] = identifier
        return super().to_internal_value(mutable)

    def validate(self, attrs):
        identifier = (attrs.get("username") or "").strip()
        password = attrs.get("password")

        if not identifier or not password:
            raise AuthenticationFailed("No active account found with the given credentials")

        user_model = get_user_model()
        user = user_model.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        ).first()

        if not user or not user.check_password(password) or not user.is_active:
            raise AuthenticationFailed("No active account found with the given credentials")

        refresh = self.get_token(user)
        self.user = user
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }
