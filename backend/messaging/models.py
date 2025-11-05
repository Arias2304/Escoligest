import mimetypes
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


def message_attachment_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    if not ext:
        guessed_ext = mimetypes.guess_extension(
            getattr(instance, "attachment_content_type", "") or ""
        )
        ext = guessed_ext or ".bin"
    return f"conversations/{instance.conversation_id}/{uuid.uuid4().hex}{ext}"


class Conversation(models.Model):
    """
    Represents a secure channel between an assigned patient and medic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="conversations_as_patient",
        on_delete=models.CASCADE,
    )
    medic = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="conversations_as_medic",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "medic"], name="unique_conversation_pair"
            )
        ]

    def __str__(self):
        return f"Conversation {self.patient_id} - {self.medic_id}"


class ConversationAdminAccess(models.Model):
    """
    Tracks which administrators have been authorized by the medic
    to review a specific conversation.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        related_name="admin_accesses",
        on_delete=models.CASCADE,
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="conversation_admin_access",
        on_delete=models.CASCADE,
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="conversation_admin_grants",
        on_delete=models.CASCADE,
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "admin"],
                name="unique_conversation_admin_access",
            )
        ]

    def clean(self):
        if self.admin.role != "ADMIN":
            raise ValidationError("Solo un usuario administrador puede recibir acceso.")
        if self.granted_by != self.conversation.medic:
            raise ValidationError(
                "Solo el medico asignado puede otorgar acceso a administradores."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Message(models.Model):
    """
    Message exchanged between a patient and their assigned medic.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, related_name="messages", on_delete=models.CASCADE
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="messages_sent",
        on_delete=models.CASCADE,
    )
    content = models.TextField(blank=True)
    attachment = models.FileField(
        upload_to=message_attachment_upload_to, blank=True, null=True
    )
    attachment_name = models.CharField(max_length=255, blank=True)
    attachment_content_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        if not self.content and not self.attachment:
            raise ValidationError(
                "El mensaje debe contener texto, un adjunto o ambos."
            )
        if self.sender_id not in (
            self.conversation.patient_id,
            self.conversation.medic_id,
        ):
            raise ValidationError(
                "Solo el paciente o el medico asignado pueden enviar mensajes."
            )

    def save(self, *args, **kwargs):
        if self.attachment and not self.attachment_name:
            original_name = getattr(self.attachment, "name", "")
            if hasattr(self.attachment, "file"):
                original_name = getattr(self.attachment.file, "name", original_name)
            self.attachment_name = os.path.basename(original_name)
        if self.attachment and not self.attachment_content_type:
            content_type = ""
            if hasattr(self.attachment, "file"):
                content_type = getattr(self.attachment.file, "content_type", "") or ""
            self.attachment_content_type = content_type
        self.full_clean()
        return super().save(*args, **kwargs)
