import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from uuid import UUID

from django.http import HttpResponse
from django.utils import timezone
from django.utils.text import slugify
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response

from coreusers.models import PatientAssignment, User
from coreusers.permissions import IsAdminUserRole
from fpdf import FPDF
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

    @action(detail=False, methods=["get"], url_path="adherence-metrics")
    def adherence_metrics(self, request):
        params = self._parse_adherence_params(request)
        payload = self._build_adherence_payload(request.user, **params)
        return Response(payload)

    @action(detail=False, methods=["get"], url_path="adherence-report")
    def adherence_report(self, request):
        params = self._parse_adherence_params(request, require_patient=True)
        payload = self._build_adherence_payload(request.user, **params)
        patient_uuid = params["patient_uuid"]
        patient_id_str = str(patient_uuid) if patient_uuid else ""
        patient_metrics = next(
            (patient for patient in payload["patients"] if patient["patient_id"] == patient_id_str),
            None,
        )
        if not patient_metrics:
            raise NotFound("No se encontraron metricas para el paciente indicado.")

        pdf_bytes = self._render_adherence_pdf(
            patient_metrics,
            payload["period_start"],
            payload["period_end"],
        )
        filename = slugify(f"informe-adherencia-{patient_metrics['patient_name']}-{payload['period_end']}")
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        safe_filename = filename or "informe-adherencia"
        response["Content-Disposition"] = f'attachment; filename="{safe_filename}.pdf"'
        return response

    def _parse_adherence_params(self, request, *, require_patient: bool = False):
        user = request.user
        if user.role not in ("PATIENT", "MEDIC", "ADMIN"):
            raise PermissionDenied("No tienes permisos para consultar estas metricas.")

        period_days = self._parse_positive_int(request.query_params.get("days", 30), "days")
        trend_periods = self._parse_positive_int(
            request.query_params.get("trend_periods", 4), "trend_periods"
        )
        trend_interval = self._parse_positive_int(
            request.query_params.get("trend_interval", 7), "trend_interval"
        )

        patient_uuid = None
        patient_id_param = request.query_params.get("patient_id")
        if patient_id_param:
            try:
                patient_uuid = UUID(str(patient_id_param))
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    {"patient_id": "El identificador del paciente es invalido."}
                ) from exc
        elif require_patient:
            raise ValidationError({"patient_id": "Debes indicar el paciente que deseas consultar."})

        return {
            "period_days": period_days,
            "trend_periods": trend_periods,
            "trend_interval": trend_interval,
            "patient_uuid": patient_uuid,
        }

    def _build_adherence_payload(
        self,
        user,
        *,
        period_days: int,
        trend_periods: int,
        trend_interval: int,
        patient_uuid,
    ):
        analysis_span = max(period_days, trend_periods * trend_interval)
        period_end = timezone.localdate()
        summary_start = period_end - timedelta(days=period_days - 1)
        data_start = period_end - timedelta(days=analysis_span - 1)

        patient_scope = self._resolve_patient_scope(user, patient_uuid)
        if patient_uuid and not patient_scope:
            raise NotFound("No se encontraron pacientes para los criterios indicados.")

        patient_ids = [entry["id"] for entry in patient_scope]
        if not patient_ids:
            return {
                "period_start": summary_start.isoformat(),
                "period_end": period_end.isoformat(),
                "trend_interval_days": trend_interval,
                "trend_segments": 0,
                "patients": [],
            }

        activities_qs = (
            PatientActivity.objects.filter(
                patient_id__in=patient_ids,
                is_personal=False,
                start_time__date__lte=period_end,
            )
            .select_related("patient", "medic", "calendar_option")
            .order_by("patient_id")
        )
        completions_qs = PatientActivityCompletion.objects.filter(
            activity__patient_id__in=patient_ids,
            activity__is_personal=False,
            occurrence_date__gte=data_start,
            occurrence_date__lte=period_end,
        ).select_related("activity__patient", "activity__medic", "activity__calendar_option")

        if user.role == "MEDIC":
            activities_qs = activities_qs.filter(medic=user)
            completions_qs = completions_qs.filter(activity__medic=user)

        if patient_uuid:
            activities_qs = activities_qs.filter(patient_id=patient_uuid)
            completions_qs = completions_qs.filter(activity__patient_id=patient_uuid)

        activities = list(activities_qs)
        completions = list(completions_qs)

        daily_assigned = defaultdict(lambda: defaultdict(int))
        daily_completed = defaultdict(lambda: defaultdict(int))
        category_totals = defaultdict(dict)

        for activity in activities:
            for occurrence in self._iterate_occurrence_dates(activity, data_start, period_end):
                daily_assigned[activity.patient_id][occurrence] += 1
                if summary_start <= occurrence <= period_end:
                    bucket = self._touch_category_bucket(category_totals, activity.patient_id, activity)
                    bucket["assigned"] += 1

        for completion in completions:
            patient_id = completion.activity.patient_id
            occurrence_date = completion.occurrence_date
            daily_completed[patient_id][occurrence_date] += 1
            if summary_start <= occurrence_date <= period_end:
                bucket = self._touch_category_bucket(category_totals, patient_id, completion.activity)
                bucket["completed"] += 1

        trend_windows = self._build_trend_windows(data_start, period_end, trend_interval, trend_periods)
        patients_payload = []
        for entry in patient_scope:
            patient_id = entry["id"]
            summary_assigned = self._sum_within_window(
                daily_assigned.get(patient_id, {}),
                summary_start,
                period_end,
            )
            summary_completed = self._sum_within_window(
                daily_completed.get(patient_id, {}),
                summary_start,
                period_end,
            )
            trend_points = []
            for start, end in trend_windows:
                assigned_value = self._sum_within_window(
                    daily_assigned.get(patient_id, {}),
                    start,
                    end,
                )
                completed_value = self._sum_within_window(
                    daily_completed.get(patient_id, {}),
                    start,
                    end,
                )
                trend_points.append(
                    {
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                        "assigned": assigned_value,
                        "completed": completed_value,
                        "adherence_percentage": self._percentage(completed_value, assigned_value),
                    }
                )

            categories_payload = []
            for stats in category_totals.get(patient_id, {}).values():
                categories_payload.append(
                    {
                        "category_id": stats["category_id"],
                        "label": stats["label"],
                        "slug": stats["slug"],
                        "color": stats["color"],
                        "assigned": stats["assigned"],
                        "completed": stats["completed"],
                        "pending": max(stats["assigned"] - stats["completed"], 0),
                        "adherence_percentage": self._percentage(stats["completed"], stats["assigned"]),
                    }
                )
            categories_payload.sort(key=lambda item: item["adherence_percentage"])

            patients_payload.append(
                {
                    "patient_id": str(patient_id),
                    "patient_name": entry["name"],
                    "assigned": summary_assigned,
                    "completed": summary_completed,
                    "pending": max(summary_assigned - summary_completed, 0),
                    "adherence_percentage": self._percentage(summary_completed, summary_assigned),
                    "trend": trend_points,
                    "categories": categories_payload,
                }
            )

        return {
            "period_start": summary_start.isoformat(),
            "period_end": period_end.isoformat(),
            "trend_interval_days": trend_interval,
            "trend_segments": len(trend_windows),
            "patients": patients_payload,
        }

    def _touch_category_bucket(self, registry, patient_id, activity: PatientActivity):
        descriptor = self._describe_activity_category(activity)
        patient_categories = registry[patient_id]
        bucket = patient_categories.get(descriptor["key"])
        if not bucket:
            bucket = {
                "category_id": descriptor["category_id"],
                "label": descriptor["label"],
                "slug": descriptor["slug"],
                "color": descriptor["color"],
                "assigned": 0,
                "completed": 0,
            }
            patient_categories[descriptor["key"]] = bucket
        return bucket

    def _describe_activity_category(self, activity: PatientActivity):
        option = getattr(activity, "calendar_option", None)
        if option:
            return {
                "key": f"option:{option.id}",
                "category_id": str(option.id),
                "label": option.name,
                "slug": option.slug,
                "color": option.color or "#3b82f6",
            }
        fallback_slug = (activity.activity_type or "OTRA").upper()
        return {
            "key": f"type:{fallback_slug}",
            "category_id": None,
            "label": fallback_slug.replace("_", " ").title(),
            "slug": fallback_slug.lower(),
            "color": activity.color
            or self.DEFAULT_COLORS.get(fallback_slug, "#94a3b8"),
        }

    def _safe_pdf_text(self, value: str) -> str:
        if not value:
            return ""
        return value.encode("latin-1", "ignore").decode("latin-1")

    def _render_adherence_pdf(self, patient_metrics, period_start: str, period_end: str):
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, self._safe_pdf_text("Informe general de adherencia"), ln=1)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 8, self._safe_pdf_text(f"Paciente: {patient_metrics['patient_name']}"), ln=1)
        pdf.cell(0, 8, f"Periodo: {period_start} al {period_end}", ln=1)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Resumen general", ln=1)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(
            0,
            7,
            f"Asignadas: {patient_metrics['assigned']}  "
            f"Completadas: {patient_metrics['completed']}  "
            f"Pendientes: {patient_metrics['pending']}",
            ln=1,
        )
        pdf.cell(
            0,
            7,
            f"Adherencia global: {patient_metrics['adherence_percentage']}%",
            ln=1,
        )
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Visualizacion de cumplimiento", ln=1)
        pdf.set_font("Helvetica", "", 10)
        chart_items = [
            {
                "label": "Adherencia global",
                "percentage": patient_metrics.get("adherence_percentage", 0),
                "color": "#2563eb",
            }
        ]

        categories = patient_metrics.get("categories", [])
        for category in categories:
            chart_items.append(
                {
                    "label": category["label"],
                    "percentage": category.get("adherence_percentage", 0),
                    "color": category.get("color") or "#10b981",
                }
            )
        self._draw_bar_chart(pdf, chart_items)
        pdf.ln(2)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Detalle por categoria", ln=1)
        pdf.set_font("Helvetica", "", 11)
        if not categories:
            pdf.cell(0, 7, "Sin registros de categorias en el periodo.", ln=1)
        else:
            for category in categories:
                pdf.set_font("Helvetica", "B", 11)
                pdf.cell(0, 7, self._safe_pdf_text(category["label"]), ln=1)
                pdf.set_font("Helvetica", "", 10)
                pdf.cell(
                    0,
                    6,
                    f"Asignadas: {category['assigned']}  "
                    f"Completadas: {category['completed']}  "
                    f"Pendientes: {category['pending']}",
                    ln=1,
                )
                pdf.cell(
                    0,
                    6,
                    f"Adherencia: {category['adherence_percentage']}%",
                    ln=1,
                )
                pdf.ln(1)

        pdf_output = pdf.output(dest="S")
        if isinstance(pdf_output, str):
            return pdf_output.encode("latin-1", "ignore")
        if isinstance(pdf_output, bytearray):
            return bytes(pdf_output)
        return pdf_output

    def _draw_bar_chart(self, pdf, items, *, bar_height=8, gap=4):
        if not items:
            pdf.cell(0, 6, "Sin datos para graficar.", ln=1)
            return

        available_width = pdf.w - pdf.l_margin - pdf.r_margin
        for entry in items:
            label = self._safe_pdf_text(entry.get("label") or "Categoria")
            percentage = entry.get("percentage") or 0
            try:
                percentage_value = max(0.0, min(float(percentage), 100.0))
            except (TypeError, ValueError):
                percentage_value = 0.0

            pdf.set_x(pdf.l_margin)
            pdf.cell(0, 6, f"{label} ({percentage_value:.1f}%)", ln=1)
            x = pdf.l_margin
            y = pdf.get_y()

            pdf.set_draw_color(220, 224, 236)
            pdf.rect(x, y, available_width, bar_height)

            fill_color = self._hex_to_rgb(entry.get("color"))
            pdf.set_fill_color(*fill_color)
            pdf.rect(
                x,
                y,
                available_width * (percentage_value / 100.0),
                bar_height,
                "F",
            )
            pdf.set_y(y + bar_height + gap)

    def _hex_to_rgb(self, color_code):
        if not color_code or not isinstance(color_code, str):
            return (37, 99, 235)
        value = color_code.strip().lstrip("#")
        if len(value) not in (3, 6):
            return (37, 99, 235)
        if len(value) == 3:
            value = "".join(ch * 2 for ch in value)
        try:
            r = int(value[0:2], 16)
            g = int(value[2:4], 16)
            b = int(value[4:6], 16)
            return (r, g, b)
        except ValueError:
            return (37, 99, 235)

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

    def _resolve_patient_scope(self, user, patient_uuid):
        if user.role == "PATIENT":
            if patient_uuid and patient_uuid != user.id:
                raise PermissionDenied("No puedes consultar adherencia de otros pacientes.")
            return [
                {
                    "id": user.id,
                    "name": user.full_name or user.username or user.email,
                }
            ]

        if user.role == "MEDIC":
            assignments = PatientAssignment.objects.filter(medic=user).select_related("patient")
            if patient_uuid:
                assignments = assignments.filter(patient_id=patient_uuid)
            return [
                {
                    "id": assignment.patient_id,
                    "name": assignment.patient.full_name
                    or assignment.patient.username
                    or assignment.patient.email,
                }
                for assignment in assignments
            ]

        patients = User.objects.filter(role="PATIENT")
        if patient_uuid:
            patients = patients.filter(id=patient_uuid)
        return [
            {
                "id": patient.id,
                "name": patient.full_name or patient.username or patient.email,
            }
            for patient in patients
        ]

    def _parse_positive_int(self, raw_value, field_name):
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValidationError({field_name: "Debes proporcionar un numero entero."}) from exc
        if value < 1:
            raise ValidationError({field_name: "Debes proporcionar un entero positivo."})
        return value

    def _build_trend_windows(self, window_start: date, window_end: date, interval_days: int, segments: int):
        windows = []
        current_end = window_end
        for _ in range(segments):
            if current_end < window_start:
                break
            current_start = max(window_start, current_end - timedelta(days=interval_days - 1))
            windows.append((current_start, current_end))
            current_end = current_start - timedelta(days=1)
        return list(reversed(windows))

    def _iterate_occurrence_dates(self, activity: PatientActivity, window_start: date, window_end: date):
        start_date = activity.start_time.date()
        if start_date > window_end:
            return
        recurrence = activity.recurrence
        repeat_until = activity.repeat_until
        limit_date = repeat_until if repeat_until and repeat_until < window_end else window_end
        if recurrence == "NONE":
            if window_start <= start_date <= window_end:
                yield start_date
            return
        if limit_date < window_start:
            return
        if recurrence == "DAILY":
            current = start_date if start_date >= window_start else window_start
            if current < start_date:
                current = start_date
            while current <= limit_date:
                yield current
                current += timedelta(days=1)
            return
        if recurrence == "WEEKLY":
            current = start_date
            if current < window_start:
                days_diff = (window_start - start_date).days
                remainder = days_diff % 7
                offset = 0 if remainder == 0 else 7 - remainder
                current = window_start + timedelta(days=offset)
            if current < start_date:
                current = start_date
            while current <= limit_date:
                yield current
                current += timedelta(days=7)
            return
        if recurrence == "MONTHLY":
            current = start_date
            while current < window_start:
                current = self._add_month(current, 1, start_date.day)
                if current > limit_date:
                    return
            while current <= limit_date:
                if current >= window_start:
                    yield current
                current = self._add_month(current, 1, start_date.day)
            return

    def _add_month(self, source_date: date, months: int, anchor_day: int):
        month_index = source_date.month - 1 + months
        year = source_date.year + month_index // 12
        month = month_index % 12 + 1
        day = min(anchor_day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    def _sum_within_window(self, daily_data, start: date, end: date):
        total = 0
        for occurrence_date, count in daily_data.items():
            if start <= occurrence_date <= end:
                total += count
        return total

    def _percentage(self, completed: int, assigned: int) -> float:
        if assigned <= 0:
            return 0.0
        return round((completed / assigned) * 100, 1)


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
