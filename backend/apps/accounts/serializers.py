from django.contrib.auth import authenticate
from rest_framework import serializers

from apps.accounts.models import APIKey, GSTINProfile, Organization, OrgMembership, Role, User


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        user = authenticate(
            self.context["request"], username=attrs["email"], password=attrs["password"]
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        attrs["user"] = user
        return attrs


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "full_name"]


class MembershipSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = OrgMembership
        fields = ["id", "email", "full_name", "role", "created_at"]


class MeSerializer(serializers.Serializer):
    user = UserSerializer()
    org = serializers.SerializerMethodField()
    role = serializers.CharField(allow_null=True)
    orgs = serializers.ListField(child=serializers.DictField())

    def get_org(self, obj):  # type: ignore[no-untyped-def]
        org = obj["org"]
        return OrganizationSerializer(org).data if org else None


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "legal_name",
            "pan",
            "aato_bracket",
            "brand_display_name",
            "settings",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class GSTINProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSTINProfile
        fields = [
            "id",
            "gstin",
            "state_code",
            "trade_name",
            "registration_type",
            "is_default",
            "valid_from",
            "valid_to",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):  # type: ignore[no-untyped-def]
        gstin = attrs.get("gstin")
        if gstin:
            from apps.gst.domain.gstin import validate as validate_gstin

            result = validate_gstin(gstin)
            if not result.is_valid:
                raise serializers.ValidationError({"gstin": result.errors})
            attrs["state_code"] = result.state_code
        return attrs


class MemberWriteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Role.choices)


SETTINGS_KEYS = {
    "auto_confirm": bool,
    "extraction_enabled": bool,
    "send_page_images_for_scans": bool,
}


class SettingsSerializer(serializers.Serializer):
    auto_confirm = serializers.BooleanField(required=False)
    extraction_enabled = serializers.BooleanField(required=False)
    send_page_images_for_scans = serializers.BooleanField(required=False)


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = ["id", "name", "prefix", "created_by", "last_used_at", "revoked_at", "created_at"]
        read_only_fields = [
            "id",
            "prefix",
            "created_by",
            "last_used_at",
            "revoked_at",
            "created_at",
        ]
