from rest_framework import serializers

from coreusers.models import User
from .models import Appointment, CalendarOption, PatientActivity


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "full_name"]


class CalendarOptionSerializer(serializers.ModelSerializer):
    created_by = SimpleUserSerializer(read_only=True)

    class Meta:
        model = CalendarOption
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "color",
            "is_active",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "created_by", "created_at", "updated_at")

    def validate_slug(self, value):
        if not value:
            raise serializers.ValidationError("El slug no puede estar vacio.")
        return value.strip().upper()

    def validate_name(self, value):
        return value.strip()


class PatientActivitySerializer(serializers.ModelSerializer):
    patient = SimpleUserSerializer(read_only=True)
    medic = SimpleUserSerializer(read_only=True)
    assigned_by = SimpleUserSerializer(read_only=True)
    created_by = SimpleUserSerializer(read_only=True)
    calendar_option = CalendarOptionSerializer(read_only=True)
    completed_dates = serializers.SerializerMethodField()

    patient_id = serializers.UUIDField(write_only=True, required=False)
    medic_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )
    calendar_option_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = PatientActivity
        fields = [
            "id",
            "patient",
            "patient_id",
            "medic",
            "medic_id",
            "assigned_by",
            "created_by",
            "calendar_option",
            "calendar_option_id",
            "title",
            "description",
            "activity_type",
            "start_time",
            "end_time",
            "recurrence",
            "repeat_until",
            "color",
            "status",
            "is_personal",
            "completed_dates",
            "completed_at",
            "created_at",
        ]
        read_only_fields = (
            "id",
            "patient",
            "medic",
            "assigned_by",
            "created_by",
            "calendar_option",
            "status",
            "is_personal",
            "completed_dates",
            "completed_at",
            "created_at",
        )

    def validate(self, attrs):
        recurrence = attrs.get("recurrence", "NONE")
        repeat_until = attrs.get("repeat_until")
        start_time = attrs.get("start_time") or getattr(self.instance, "start_time", None)

        if recurrence == "NONE":
            attrs["repeat_until"] = None
        else:
            existing_repeat = getattr(self.instance, "repeat_until", None)
            if not repeat_until and not existing_repeat:
                raise serializers.ValidationError(
                    {
                        "repeat_until": "Debes indicar hasta quÃ© fecha se repite la actividad."
                    }
                )
            if start_time and repeat_until and repeat_until < start_time.date():
                raise serializers.ValidationError(
                    {"repeat_until": "La fecha final debe ser posterior al inicio."}
                )

        request = self.context["request"]
        user = request.user

        if user.role == "PATIENT":
            attrs["patient_id"] = str(user.id)
            if attrs.get("medic_id"):
                raise serializers.ValidationError(
                    {"medic_id": "No puedes asignar un medico en un recordatorio personal."}
                )

        calendar_option_id = attrs.get("calendar_option_id")
        if calendar_option_id:
            try:
                option = CalendarOption.objects.get(
                    id=calendar_option_id, is_active=True
                )
            except CalendarOption.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {
                        "calendar_option_id": "La opcion de calendario no existe o esta inactiva."
                    }
                ) from exc
            attrs["_calendar_option_instance"] = option
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = request.user

        patient_id = validated_data.pop("patient_id", None)
        medic_id = validated_data.pop("medic_id", None)
        calendar_option_instance = validated_data.pop("_calendar_option_instance", None)
        calendar_option_id = validated_data.pop("calendar_option_id", None)

        if calendar_option_instance is None and calendar_option_id:
            try:
                calendar_option_instance = CalendarOption.objects.get(
                    id=calendar_option_id, is_active=True
                )
            except CalendarOption.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {
                        "calendar_option_id": "La opcion de calendario no existe o esta inactiva."
                    }
                ) from exc

        if user.role == "PATIENT":
            patient = user
            medic = None
            assigned_by = None
            is_personal = True
            if not validated_data.get("activity_type"):
                validated_data["activity_type"] = (
                    calendar_option_instance.slug if calendar_option_instance else "REMINDER"
                )
        else:
            if not patient_id:
                raise serializers.ValidationError(
                    {"patient_id": "Debes indicar el paciente asociado."}
                )
            try:
                patient = User.objects.get(id=patient_id)
            except User.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"patient_id": "Paciente no encontrado."}
                ) from exc

            medic = None
            if medic_id:
                try:
                    medic = User.objects.get(id=medic_id)
                except User.DoesNotExist as exc:
                    raise serializers.ValidationError(
                        {"medic_id": "Medico no encontrado."}
                    ) from exc
            elif user.role == "MEDIC":
                medic = user

            if medic is None:
                raise serializers.ValidationError(
                    {"medic_id": "Debes indicar el medico responsable de la actividad."}
                )

            assigned_by = user
            is_personal = False

        validated_data["patient"] = patient
        validated_data["medic"] = medic
        validated_data["assigned_by"] = assigned_by
        validated_data["created_by"] = user
        validated_data["is_personal"] = is_personal
        if calendar_option_instance:
            validated_data["calendar_option"] = calendar_option_instance
            if not validated_data.get("activity_type"):
                validated_data["activity_type"] = calendar_option_instance.slug
            if not validated_data.get("color"):
                validated_data["color"] = calendar_option_instance.color

        if not validated_data.get("color"):
            validated_data["color"] = ""

        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("patient_id", None)
        validated_data.pop("medic_id", None)
        calendar_option_instance = validated_data.pop("_calendar_option_instance", None)
        validated_data.pop("calendar_option_id", None)

        if calendar_option_instance:
            validated_data["calendar_option"] = calendar_option_instance
            if not validated_data.get("activity_type"):
                validated_data["activity_type"] = calendar_option_instance.slug
            if not validated_data.get("color"):
                validated_data["color"] = calendar_option_instance.color

        return super().update(instance, validated_data)

    def get_completed_dates(self, obj):
        return [
            occurrence.strftime("%Y-%m-%d")
            for occurrence in obj.completions.values_list("occurrence_date", flat=True)
        ]


class PatientReminderSerializer(serializers.ModelSerializer):
    medic_name = serializers.SerializerMethodField()
    calendar_label = serializers.SerializerMethodField()
    calendar_color = serializers.SerializerMethodField()

    class Meta:
        model = PatientActivity
        fields = [
            "id",
            "title",
            "description",
            "start_time",
            "medic_name",
            "calendar_label",
            "calendar_color",
        ]

    def get_medic_name(self, obj):
        if obj.medic:
            return obj.medic.full_name or obj.medic.username
        return None

    def get_calendar_label(self, obj):
        if obj.calendar_option:
            return obj.calendar_option.name
        return None

    def get_calendar_color(self, obj):
        if obj.calendar_option:
            return obj.calendar_option.color
        return None
