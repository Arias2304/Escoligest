from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import PatientAssignment, User
from .permissions import IsAdminUserRole
from .serializers import (
    AdminUserSerializer,
    AssignmentActionSerializer,
    AssignmentSerializer,
    RegisterSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (permissions.AllowAny,)
    serializer_class = RegisterSerializer


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (IsAuthenticated,)

    def get_object(self):
        return self.request.user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["user_id"] = str(user.id)
        token["username"] = user.username
        token["role"] = user.role
        token["full_name"] = user.full_name
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class AdminUserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by("username")
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUserRole]
    lookup_field = "id"

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .prefetch_related("assigned_medics__medic", "assigned_patients__patient")
        )
        role = self.request.query_params.get("role")
        if role:
            queryset = queryset.filter(role=role.upper())
        return queryset

    def get_serializer_class(self):
        if self.action in ("update", "partial_update", "create"):
            return AdminUserSerializer
        return AdminUserSerializer

    @action(detail=False, methods=["get"])
    def stats(self, request):
        role_counts = {entry["role"]: entry["total"] for entry in User.objects.values("role").annotate(total=Count("id"))}
        data = {
            "patients": role_counts.get("PATIENT", 0),
            "medics": role_counts.get("MEDIC", 0),
            "admins": role_counts.get("ADMIN", 0),
            "assignments": PatientAssignment.objects.count(),
        }
        return Response(data)

    @action(detail=False, methods=["get"])
    def assignments(self, request):
        patient_id = request.query_params.get("patient_id")
        medic_id = request.query_params.get("medic_id")
        assignments = PatientAssignment.objects.select_related(
            "patient", "medic", "assigned_by"
        )
        if patient_id:
            assignments = assignments.filter(patient_id=patient_id)
        if medic_id:
            assignments = assignments.filter(medic_id=medic_id)
        serializer = AssignmentSerializer(assignments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def assign(self, request):
        serializer = AssignmentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        patient = get_object_or_404(
            User, id=serializer.validated_data["patient_id"], role="PATIENT"
        )
        medic = get_object_or_404(
            User, id=serializer.validated_data["medic_id"], role="MEDIC"
        )

        assignment, created = PatientAssignment.objects.get_or_create(
            patient=patient,
            medic=medic,
            defaults={"assigned_by": request.user},
        )
        if not created:
            return Response(
                {"detail": "El paciente ya está asignado a ese médico."},
                status=status.HTTP_200_OK,
            )
        response_serializer = AssignmentSerializer(assignment)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def unassign(self, request):
        serializer = AssignmentActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        deleted, _ = PatientAssignment.objects.filter(
            patient_id=serializer.validated_data["patient_id"],
            medic_id=serializer.validated_data["medic_id"],
        ).delete()

        if deleted:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(
            {"detail": "No existe una asignación para los identificadores dados."},
            status=status.HTTP_404_NOT_FOUND,
        )
