import calendar
from datetime import date, datetime

from django.utils import timezone
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from coreusers.models import PatientAssignment, User
from coreusers.permissions import IsAdminUserRole
from .models import (
    Appointment,
    CalendarOption,
    PatientActivity,
    PatientActivityCompletion,
)
from .serializers import (
    AppointmentSerializer,
    CalendarOptionSerializer,
    PatientActivitySerializer,
)


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
    queryset = (
        PatientActivity.objects.select_related(
            "patient", "medic", "assigned_by", "created_by", "calendar_option"
        )
        .prefetch_related("completions")
        .order_by("start_time")
    )
    serializer_class = PatientActivitySerializer
    permission_classes = [permissions.IsAuthenticated]

    DEFAULT_COLORS = {
        "APPOINTMENT": "#2563eb",
        "MEDICATION": "#10b981",
        "THERAPY": "#f97316",
        "REMINDER": "#6366f1",
        "WEEKLY": "#6366f1",
        "MONTHLY": "#facc15",
    }

    def get_queryset(self):
        user = self.request.user
        base = (
            PatientActivity.objects.select_related(
                "patient", "medic", "assigned_by", "created_by", "calendar_option"
            )
            .prefetch_related("completions")
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
        if user.role == "PATIENT":
            if not serializer.validated_data.get("color"):
                option = serializer.validated_data.get("_calendar_option_instance")
                serializer.validated_data["color"] = (
                    option.color if option else self.DEFAULT_COLORS.get("REMINDER", "#6b7280")
                )
            serializer.save()
            return

        patient_id = serializer.validated_data.get("patient_id")
        medic_id = serializer.validated_data.get("medic_id")

        if not patient_id:
            raise ValidationError("Debes indicar el paciente asociado.")

        try:
            patient = User.objects.get(id=patient_id)
        except User.DoesNotExist as exc:
            raise NotFound("El paciente indicado no existe.") from exc

        if user.role == "MEDIC":
            if medic_id and str(medic_id) != str(user.id):
                raise PermissionDenied(
                    "No puedes asignar actividades en nombre de otro medico."
                )
            medic = user
            if not PatientAssignment.objects.filter(
                patient=patient, medic=medic
            ).exists():
                raise PermissionDenied(
                    "Solo puedes asignar actividades a tus pacientes."
                )
        else:
            if not medic_id:
                raise ValidationError(
                    "Debes indicar el medico responsable de la actividad."
                )
            try:
                medic = User.objects.get(id=medic_id)
            except User.DoesNotExist as exc:
                raise NotFound("El medico indicado no existe.") from exc

        if medic.role != "MEDIC":
            raise PermissionDenied("El usuario indicado no es un medico.")

        if not serializer.validated_data.get("color"):
            option = serializer.validated_data.get("_calendar_option_instance")
            serializer.validated_data["color"] = option.color if option else self.DEFAULT_COLORS.get(
                serializer.validated_data.get("activity_type"), "#6b7280"
            )

        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if user.role == "PATIENT":
            if instance.patient != user or not instance.is_personal:
                raise PermissionDenied(
                    "No tienes permisos para actualizar esta actividad."
                )
        elif user.role == "MEDIC":
            if instance.medic != user:
                raise PermissionDenied(
                    "Solo el medico asignado puede actualizar la actividad."
                )

        color = serializer.validated_data.get("color")
        if not color and "activity_type" in serializer.validated_data:
            option = serializer.validated_data.get("_calendar_option_instance")
            if option:
                serializer.validated_data["color"] = option.color
            else:
                serializer.validated_data["color"] = self.DEFAULT_COLORS.get(
                    serializer.validated_data["activity_type"], instance.color
                )
        serializer.save()

    def perform_destroy(self, instance):
        user = self.request.user
        if user.role == "PATIENT" and (instance.patient != user or not instance.is_personal):
            raise PermissionDenied(
                "No tienes permisos para eliminar esta actividad."
            )
        if user.role == "MEDIC" and instance.medic != user and user.role != "ADMIN":
            raise PermissionDenied(
                "Solo el medico asignado puede eliminar la actividad."
            )
        instance.delete()

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        activity = self.get_object()
        user = request.user
        date_str = request.data.get("date")

        if date_str:
            if user.role not in ("PATIENT", "ADMIN"):
                raise permissions.PermissionDenied(
                    "Solo el paciente puede completar una ocurrencia."
                )
            if user.role == "PATIENT" and activity.patient != user:
                raise permissions.PermissionDenied(
                    "Solo el paciente asignado puede completar esta actividad."
                )
            try:
                target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError as exc:
                raise ValidationError({"date": "Formato de fecha invalido (AAAA-MM-DD)."}) from exc

            if not self._occurs_on_date(activity, target_date):
                raise ValidationError(
                    {"date": "La actividad no ocurre en la fecha indicada."}
                )

            completion, created = PatientActivityCompletion.objects.get_or_create(
                activity=activity,
                occurrence_date=target_date,
                defaults={"completed_by": user},
            )
            if not created and completion.completed_by is None:
                completion.completed_by = user
                completion.save(update_fields=["completed_by"])

            serializer = self.get_serializer(self.get_object())
            return Response(serializer.data)

        # completar toda la actividad
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

    def _occurs_on_date(self, activity: PatientActivity, target_date: date) -> bool:
        start_date = activity.start_time.date()
        if target_date < start_date:
            return False

        repeat_until = activity.repeat_until
        if repeat_until and target_date > repeat_until:
            return False

        recurrence = activity.recurrence
        if recurrence == "NONE":
            return target_date == start_date
        if recurrence == "DAILY":
            return True
        if recurrence == "WEEKLY":
            delta_days = (target_date - start_date).days
            return delta_days % 7 == 0
        if recurrence == "MONTHLY":
            if target_date < start_date:
                return False
            month_diff = (target_date.year - start_date.year) * 12 + (
                target_date.month - start_date.month
            )
            if month_diff < 0:
                return False
            scheduled_day = min(
                start_date.day,
                calendar.monthrange(target_date.year, target_date.month)[1],
            )
            return target_date.day == scheduled_day
        return False


class CalendarOptionViewSet(viewsets.ModelViewSet):
    queryset = CalendarOption.objects.all().order_by("name")
    serializer_class = CalendarOptionSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated(), IsAdminUserRole()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role != "ADMIN":
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save()
