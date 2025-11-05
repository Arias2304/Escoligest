from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation, ConversationAdminAccess, Message
from .serializers import (
    ConversationCreateSerializer,
    ConversationSerializer,
    GrantAdminAccessSerializer,
    MessageSerializer,
)


class ConversationViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Conversation.objects.select_related("patient", "medic").prefetch_related(
            "admin_accesses__admin"
        )
        if user.role == "PATIENT":
            return queryset.filter(patient=user)
        if user.role == "MEDIC":
            return queryset.filter(medic=user)
        if user.role == "ADMIN":
            return queryset.filter(admin_accesses__admin=user)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        serializer = ConversationCreateSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)

        conversation, created = Conversation.objects.get_or_create(
            patient=serializer.validated_data["patient"],
            medic=serializer.validated_data["medic"],
        )

        output_serializer = ConversationSerializer(
            conversation, context=self.get_serializer_context()
        )
        status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(output_serializer.data, status=status_code)

    @action(detail=True, methods=["post"], url_path="grant-admin-access")
    def grant_admin_access(self, request, pk=None):
        conversation = self.get_object()
        if request.user != conversation.medic:
            raise PermissionDenied(
                "Solo el medico asignado puede otorgar acceso a los administradores."
            )

        serializer = GrantAdminAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin = serializer.validated_data["admin"]

        access, created = ConversationAdminAccess.objects.get_or_create(
            conversation=conversation,
            admin=admin,
            defaults={"granted_by": request.user},
        )
        if not created and access.granted_by != request.user:
            access.granted_by = request.user
            access.save(update_fields=["granted_by"])

        return Response(
            {
                "conversation": str(conversation.id),
                "admin": {
                    "id": str(admin.id),
                    "username": admin.username,
                    "full_name": admin.full_name or admin.username,
                },
                "granted": True,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="revoke-admin-access")
    def revoke_admin_access(self, request, pk=None):
        conversation = self.get_object()
        if request.user != conversation.medic:
            raise PermissionDenied(
                "Solo el medico asignado puede revocar el acceso de administradores."
            )

        serializer = GrantAdminAccessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin = serializer.validated_data["admin"]

        deleted, _ = ConversationAdminAccess.objects.filter(
            conversation=conversation, admin=admin
        ).delete()
        if not deleted:
            raise ValidationError("Ese administrador no tiene acceso concedido.")

        return Response(status=status.HTTP_204_NO_CONTENT)


class MessageViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_queryset(self):
        conversation_id = self.request.query_params.get("conversation")
        if not conversation_id:
            raise ValidationError(
                {"conversation": "Debe indicar la conversacion que desea consultar."}
            )
        conversation = get_object_or_404(
            Conversation.objects.select_related("patient", "medic").prefetch_related(
                "admin_accesses__admin"
            ),
            id=conversation_id,
        )
        if not self._user_can_access(self.request.user, conversation, allow_admin=True):
            raise PermissionDenied("No tiene permiso para ver los mensajes.")

        return (
            Message.objects.filter(conversation=conversation)
            .select_related("sender", "conversation")
            .order_by("created_at")
        )

    def perform_create(self, serializer):
        conversation = serializer.validated_data["conversation"]
        if not self._user_can_access(self.request.user, conversation, allow_admin=False):
            raise PermissionDenied(
                "No tiene permiso para enviar mensajes en esta conversacion."
            )
        serializer.save(sender=self.request.user)

    def _user_can_access(self, user, conversation: Conversation, allow_admin: bool) -> bool:
        if user.role == "ADMIN":
            if not allow_admin:
                return False
            return conversation.admin_accesses.filter(admin=user).exists()
        return user.id in (conversation.patient_id, conversation.medic_id)
