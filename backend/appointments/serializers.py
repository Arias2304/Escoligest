from rest_framework import serializers

from coreusers.models import User
from .models import Appointment, PatientActivity


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class SimpleUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "full_name"]


class PatientActivitySerializer(serializers.ModelSerializer):
    patient = SimpleUserSerializer(read_only=True)
    medic = SimpleUserSerializer(read_only=True)
    assigned_by = SimpleUserSerializer(read_only=True)
    patient_id = serializers.UUIDField(write_only=True)
    medic_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = PatientActivity
        fields = [
            "id",
            "patient",
            "patient_id",
            "medic",
            "medic_id",
            "assigned_by",
            "title",
            "description",
            "activity_type",
            "start_time",
            "end_time",
            "recurrence",
            "repeat_until",
            "color",
            "status",
            "completed_at",
            "created_at",
        ]
        read_only_fields = (
            "id",
            "patient",
            "medic",
            "assigned_by",
            "status",
            "completed_at",
            "created_at",
        )

    def validate(self, attrs):
        recurrence = attrs.get("recurrence", "NONE")
        repeat_until = attrs.get("repeat_until")
        if recurrence == "DAILY" and not repeat_until:
            raise serializers.ValidationError(
                {"repeat_until": "Debes indicar hasta qué fecha se repite la actividad."}
            )
        return super().validate(attrs)

    def create(self, validated_data):
        patient_id = validated_data.pop("patient_id")
        medic_id = validated_data.pop("medic_id", None)
        try:
            patient = User.objects.get(id=patient_id)
        except User.DoesNotExist as exc:  # pragma: no cover - defensive
            raise serializers.ValidationError({"patient_id": "Paciente no encontrado."}) from exc

        if medic_id:
            try:
                medic = User.objects.get(id=medic_id)
            except User.DoesNotExist as exc:  # pragma: no cover
                raise serializers.ValidationError({"medic_id": "Médico no encontrado."}) from exc
        else:
            medic = self.context["request"].user
        validated_data["patient"] = patient
        validated_data["medic"] = medic
        validated_data["assigned_by"] = self.context["request"].user
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("patient_id", None)
        validated_data.pop("medic_id", None)
        return super().update(instance, validated_data)
