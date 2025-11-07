from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import PatientAssignment, User


class UserSerializer(serializers.ModelSerializer):
    assigned_medics = serializers.SerializerMethodField()
    assigned_patients = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "full_name",
            "email",
            "role",
            "phone_number",
            "sex",
            "scoliosis_condition",
            "specialty",
            "assigned_medics",
            "assigned_patients",
        ]
        read_only_fields = ("id", "username", "role")

    def get_assigned_medics(self, obj):
        if obj.role != "PATIENT":
            return []
        assignments = obj.assigned_medics.select_related("medic")
        return [
            {
                "id": str(assignment.medic.id),
                "username": assignment.medic.username,
                "full_name": assignment.medic.full_name or assignment.medic.username,
            }
            for assignment in assignments
        ]

    def get_assigned_patients(self, obj):
        if obj.role != "MEDIC":
            return []
        assignments = obj.assigned_patients.select_related("patient")
        return [
            {
                "id": str(assignment.patient.id),
                "username": assignment.patient.username,
                "full_name": assignment.patient.full_name
                or assignment.patient.username,
            }
            for assignment in assignments
        ]


class AdminUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        read_only_fields = ("id",)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )
    full_name = serializers.CharField(required=True, max_length=150)
    phone_number = serializers.CharField(required=False, allow_blank=True, max_length=20)
    sex = serializers.ChoiceField(
        required=False, choices=User.SEX_CHOICES, allow_blank=True
    )
    scoliosis_condition = serializers.ChoiceField(
        required=False, choices=User.SCOLIOSIS_CONDITIONS, allow_blank=True
    )
    specialty = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="Ya existe una cuenta registrada con este correo electronico.",
            )
        ],
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "email",
            "full_name",
            "role",
            "phone_number",
            "sex",
            "scoliosis_condition",
            "specialty",
        )

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class AssignmentSerializer(serializers.ModelSerializer):
    patient = serializers.SerializerMethodField()
    medic = serializers.SerializerMethodField()
    assigned_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = PatientAssignment
        fields = ["id", "patient", "medic", "assigned_by", "created_at"]

    def get_patient(self, obj):
        patient = obj.patient
        return {
            "id": str(patient.id),
            "username": patient.username,
            "full_name": patient.full_name or patient.username,
        }

    def get_medic(self, obj):
        medic = obj.medic
        return {
            "id": str(medic.id),
            "username": medic.username,
            "full_name": medic.full_name or medic.username,
        }


class AssignmentActionSerializer(serializers.Serializer):
    patient_id = serializers.UUIDField()
    medic_id = serializers.UUIDField()

    def validate(self, attrs):
        if attrs["patient_id"] == attrs["medic_id"]:
            raise serializers.ValidationError(
                "El paciente y el médico no pueden ser el mismo usuario."
            )
        return attrs
