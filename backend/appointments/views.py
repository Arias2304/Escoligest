from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from coreusers.models import PatientAssignment, User
from .models import Appointment, PatientActivity
from .serializers import AppointmentSerializer, PatientActivitySerializer

class IsOwnerOrMedical(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == "ADMIN":
            return True
        if user.role == "PATIENT" and obj.patient == user:
            return True
        if user.role == "MEDIC" and obj.professional == user:
            return True
        return False

class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().order_by("start")
    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrMedical]

    def get_queryset(self):
        user = self.request.user
        if user.role == "ADMIN":
            return Appointment.objects.all().order_by("start")
        if user.role == "MEDIC":
            return Appointment.objects.filter(professional=user).order_by("start")
        return Appointment.objects.filter(patient=user).order_by("start")


class PatientActivityViewSet(viewsets.ModelViewSet):
    queryset = PatientActivity.objects.select_related(
        "patient", "medic", "assigned_by"
    ).order_by("start_time")
    serializer_class = PatientActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    DEFAULT_COLORS = {
        "APPOINTMENT": "#2563eb",
        "MEDICATION": "#10b981",
        "THERAPY": "#f97316",
    }

    def get_queryset(self):
        user = self.request.user
        base = (
            PatientActivity.objects.select_related("patient", "medic", "assigned_by")
            .order_by("start_time")
        )
        if user.role == "ADMIN":
            return base
        if user.role == "MEDIC":
            return base.filter(medic=user)
        if user.role == "PATIENT":
            return base.filter(patient=user)
        return base.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role not in ("MEDIC", "ADMIN"):
            raise PermissionDenied(
                "Solo médicos o administradores pueden crear actividades."
            )

        patient_id = serializer.validated_data.get("patient_id")
        medic_id = serializer.validated_data.get("medic_id")

        if user.role == "MEDIC":
            if medic_id and str(medic_id) != str(user.id):
                raise PermissionDenied(
                    "No puedes asignar actividades en nombre de otro médico."
                )
            medic = user
        else:
            if not medic_id:
                raise ValidationError(
                    "Debes indicar el médico responsable de la actividad."
                )
            try:
                medic = User.objects.get(id=medic_id)
            except User.DoesNotExist as exc:
                raise NotFound("El médico indicado no existe.") from exc

        try:
            patient = User.objects.get(id=patient_id)
        except User.DoesNotExist as exc:
            raise NotFound("El paciente indicado no existe.") from exc
        if medic.role != "MEDIC":
            raise PermissionDenied("El usuario indicado no es un médico.")

        if user.role == "MEDIC":
            if not PatientAssignment.objects.filter(
                patient=patient, medic=medic
            ).exists():
                raise PermissionDenied(
                    "Solo puedes asignar actividades a tus pacientes."
                )

        color = serializer.validated_data.get("color")
        if not color:
            serializer.validated_data["color"] = self.DEFAULT_COLORS.get(
                serializer.validated_data.get("activity_type"), "#6b7280"
            )

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if user.role == "PATIENT" or (
            user.role == "MEDIC" and instance.medic != user and user.role != "ADMIN"
        ):
            raise PermissionDenied(
                "No tienes permisos para actualizar esta actividad."
            )

        color = serializer.validated_data.get("color")
        if not color and "activity_type" in serializer.validated_data:
            serializer.validated_data["color"] = self.DEFAULT_COLORS.get(
                serializer.validated_data["activity_type"], instance.color
            )
        serializer.save()

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        activity = self.get_object()
        user = request.user
        if user != activity.patient and user.role != "ADMIN":
            raise permissions.PermissionDenied(
                "Solo el paciente puede completar la actividad."
            )
        if activity.status == "COMPLETED":
            return Response(
                {"detail": "La actividad ya fue marcada como completada."},
                status=status.HTTP_200_OK,
            )
        activity.status = "COMPLETED"
        activity.completed_at = timezone.now()
        activity.save(update_fields=["status", "completed_at"])
        serializer = self.get_serializer(activity)
        return Response(serializer.data)
