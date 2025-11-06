from rest_framework import serializers

from django.utils.translation import gettext_lazy as _

from coreusers.models import User
from .models import Article


def _build_file_url(request, file_field):
    if not file_field:
        return None
    url = file_field.url
    if request is None:
        return url
    return request.build_absolute_uri(url)


def _validate_article_payload(attrs, instance=None):
    content = attrs.get("content", getattr(instance, "content", ""))
    external_url = attrs.get("external_url", getattr(instance, "external_url", ""))
    pdf = attrs.get("pdf", getattr(instance, "pdf", None))
    if not content and not external_url and not pdf:
        raise serializers.ValidationError(
            "Debes proporcionar contenido, un enlace externo o un archivo PDF."
        )
    return attrs


def _validate_pdf(file_obj):
    if not file_obj:
        return file_obj
    content_type = getattr(file_obj, "content_type", "")
    filename = getattr(file_obj, "name", "")
    if content_type and content_type != "application/pdf":
        raise serializers.ValidationError(_("El archivo debe ser un PDF valido."))
    if filename and not filename.lower().endswith(".pdf"):
        raise serializers.ValidationError(_("El archivo debe tener extension .pdf."))
    return file_obj


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "full_name", "role")
        read_only_fields = fields


class ArticlePublicSerializer(serializers.ModelSerializer):
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = (
            "id",
            "title",
            "summary",
            "content",
            "external_url",
            "pdf_url",
            "published_at",
        )
        read_only_fields = fields

    def get_pdf_url(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        return _build_file_url(request, obj.pdf)


class ArticleDetailSerializer(serializers.ModelSerializer):
    created_by = UserSummarySerializer(read_only=True)
    approved_by = UserSummarySerializer(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Article
        fields = (
            "id",
            "title",
            "summary",
            "content",
            "external_url",
            "pdf",
            "pdf_url",
            "status",
            "status_display",
            "review_notes",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
            "published_at",
        )
        read_only_fields = (
            "id",
            "status",
            "status_display",
            "created_by",
            "approved_by",
            "created_at",
            "updated_at",
            "published_at",
        )
        extra_kwargs = {
            "pdf": {
                "write_only": True,
                "required": False,
                "allow_null": True,
            }
        }

    def get_pdf_url(self, obj):
        request = self.context.get("request") if hasattr(self, "context") else None
        return _build_file_url(request, obj.pdf)

    def validate(self, attrs):
        _validate_article_payload(attrs, self.instance)
        return attrs

    def validate_pdf(self, value):
        return _validate_pdf(value)


class ArticleSubmitSerializer(serializers.ModelSerializer):
    pdf = serializers.FileField(
        required=False,
        allow_empty_file=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = Article
        fields = ("title", "summary", "content", "external_url", "pdf")

    def validate(self, attrs):
        _validate_article_payload(attrs)
        return attrs

    def validate_pdf(self, value):
        return _validate_pdf(value)
