import phonenumbers
from rest_framework import serializers


def validate_international_phone(value):
    try:
        parsed = phonenumbers.parse(value, None)
    except phonenumbers.NumberParseException as exc:
        raise serializers.ValidationError("Enter a valid phone number for the selected country.") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise serializers.ValidationError("Enter a valid phone number for the selected country.")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)