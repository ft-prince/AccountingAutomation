from rest_framework import serializers

from apps.documents.models import Document


class DocumentSerializer(serializers.ModelSerializer):
    duplicate_of = serializers.UUIDField(read_only=True, required=False)

    class Meta:
        model = Document
        fields = [
            "id",
            "original_filename",
            "mime",
            "size_bytes",
            "page_count",
            "sha256",
            "source",
            "status",
            "error",
            "attempts",
            "uploaded_by",
            "created_at",
            "updated_at",
            "duplicate_of",
        ]
        read_only_fields = fields


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class BulkUploadSerializer(serializers.Serializer):
    files = serializers.ListField(child=serializers.FileField(), allow_empty=False)
