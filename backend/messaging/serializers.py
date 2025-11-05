from typing import Any

from django.contrib.auth import get_user_model
from rest_framework import serializers

from coreusers.models import PatientAssignment
from .models import Conversation, Message

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "full_name", "role")


class ConversationSerializer(serializers.ModelSerializer):
    patient = UserSummarySerializer(read_only=True)
    medic = UserSummarySerializer(read_only=True)
    authorized_admins = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ("id", "patient", "medic", "created_at", "authorized_admins")
        read_only_fields = ("id", "patient", "medic", "created_at", "authorized_admins")

    def get_authorized_admins(self, obj: Conversation) -> list[dict[str, Any]]:
        admins = obj.admin_accesses.select_related("admin")
        return [
            {
                "id": str(access.admin.id),
                "username": access.admin.username,
                "full_name": access.admin.full_name or access.admin.username,
                "granted_at": access.granted_at.isoformat(),
            }
            for access in admins
        ]


class ConversationCreateSerializer(serializers.Serializer):
    """
    Handles validating the participants when a conversation is created.
    """

    patient_id = serializers.UUIDField(required=False)
    medic_id = serializers.UUIDField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        request = self.context["request"]
        user = request.user
        patient_id = attrs.get("patient_id")
        medic_id = attrs.get("medic_id")

        if user.role == "PATIENT":
            patient = user
            if not medic_id:
                raise serializers.ValidationError(
                    {"medic_id": "Debe indicar el medico con quien desea conversar."}
                )
            medic = self._get_user_by_id(medic_id, expected_role="MEDIC")
        elif user.role == "MEDIC":
            medic = user
            if not patient_id:
                raise serializers.ValidationError(
                    {"patient_id": "Debe indicar el paciente con quien desea conversar."}
                )
            patient = self._get_user_by_id(patient_id, expected_role="PATIENT")
        else:
            raise serializers.ValidationError(
                "Solo pacientes y medicos pueden iniciar conversaciones."
            )

        assignment_exists = PatientAssignment.objects.filter(
            patient=patient, medic=medic
        ).exists()
        if not assignment_exists:
            raise serializers.ValidationError(
                "El paciente y el medico no estan asignados entre si."
            )

        attrs["patient"] = patient
        attrs["medic"] = medic
        return attrs

    def _get_user_by_id(self, user_id, expected_role: str) -> User:
        try:
            user = User.objects.get(id=user_id, role=expected_role)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError(
                f"No se encontro un usuario con rol {expected_role.lower()} para el identificador dado."
            ) from exc
        return user


class MessageSerializer(serializers.ModelSerializer):
    conversation = serializers.PrimaryKeyRelatedField(
        queryset=Conversation.objects.all(), write_only=True
    )
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)
    sender = UserSummarySerializer(read_only=True)
    attachment = serializers.FileField(required=False, allow_null=True)
    attachment_url = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            "id",
            "conversation",
            "conversation_id",
            "sender",
            "content",
            "attachment",
            "attachment_url",
            "attachment_name",
            "attachment_content_type",
            "created_at",
        )
        read_only_fields = (
            "id",
            "sender",
            "conversation_id",
            "attachment_url",
            "attachment_name",
            "attachment_content_type",
            "created_at",
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        content = attrs.get("content", "")
        attachment = attrs.get("attachment")
        if not content and not attachment:
            raise serializers.ValidationError(
                "Debe enviar al menos texto o un archivo adjunto."
            )

        conversation = attrs.get("conversation")
        user = self.context["request"].user
        if conversation and user.id not in (
            conversation.patient_id,
            conversation.medic_id,
        ):
            raise serializers.ValidationError(
                "Solo el paciente o el medico asignado pueden enviar mensajes."
            )
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Message:
        request = self.context["request"]
        attachment = validated_data.get("attachment")
        if attachment is not None:
            validated_data["attachment_name"] = getattr(attachment, "name", "")
            content_type = getattr(attachment, "content_type", "")
            if not content_type and hasattr(attachment, "file"):
                content_type = getattr(attachment.file, "content_type", "") or ""
            validated_data["attachment_content_type"] = content_type
        sender = validated_data.pop("sender", None) or self.context["request"].user
        message = Message.objects.create(sender=sender, **validated_data)
        return message

    def get_attachment_url(self, obj: Message) -> str | None:
        request = self.context.get("request")
        if obj.attachment and request:
            return request.build_absolute_uri(obj.attachment.url)
        if obj.attachment:
            return obj.attachment.url
        return None


class GrantAdminAccessSerializer(serializers.Serializer):
    admin_id = serializers.UUIDField()

    def validate_admin_id(self, value):
        try:
            admin = User.objects.get(id=value, role="ADMIN")
        except User.DoesNotExist as exc:
            raise serializers.ValidationError(
                "Debe seleccionar un usuario con rol administrador."
            ) from exc
        return admin

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs["admin"] = attrs["admin_id"]
        return attrs
