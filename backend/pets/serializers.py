from rest_framework import serializers
from .models import Pet, DoctorSummary
from accounts.phone_validation import validate_international_phone


class PetSerializer(serializers.ModelSerializer):
    owner_phone = serializers.CharField(source="owner.phone", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    profile_photo_url = serializers.SerializerMethodField()

    def get_profile_photo_url(self, obj):
        if not obj.profile_photo:
            return None
        request = self.context.get("request")
        url = obj.profile_photo.url
        return request.build_absolute_uri(url) if request else url

    class Meta:
        model = Pet
        fields = [
            "id",
            "owner",
            "name",
            "age",
            "breed",
            "vaccination_date",
            "profile_photo",
            "profile_photo_url",
            "owner_phone",
            "owner_username",
        ]


class SummarySerializer(serializers.ModelSerializer):
    doctor_username = serializers.CharField(source="doctor.username", read_only=True)
    next_vaccination_at = serializers.DateTimeField()

    class Meta:
        model = DoctorSummary
        fields = "__all__"
        read_only_fields = ["reminder_sent", "reminder_sent_at", "created_at", "doctor"]


class PetProfileSerializer(PetSerializer):
    summaries = SummarySerializer(many=True, read_only=True)

    class Meta(PetSerializer.Meta):
        fields = PetSerializer.Meta.fields + ["summaries"]


class DoctorCreateOwnerPetSerializer(serializers.Serializer):
    owner_username = serializers.CharField(max_length=150)
    owner_email = serializers.EmailField()
    owner_phone = serializers.CharField(max_length=16)
    owner_password = serializers.CharField(required=False, allow_blank=True, write_only=True)
    pet_name = serializers.CharField(max_length=100)
    pet_age = serializers.DecimalField(max_digits=5, decimal_places=2)
    pet_breed = serializers.CharField(max_length=100)
    pet_vaccination_date = serializers.DateField()

    def validate_owner_phone(self, value):
        normalized = validate_international_phone(value)
        if normalized.startswith("+91") and normalized[3:4] not in "6789":
            raise serializers.ValidationError(
                "Indian phone numbers must contain 10 digits and start with 6, 7, 8, or 9."
            )
        return normalized
