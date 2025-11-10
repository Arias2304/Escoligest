import json

from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from oauth2_provider.models import AccessToken
from oauth2_provider.views import TokenView
from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PatientAssignment, User
from .permissions import IsAdminUserRole
from .serializers import (
    AdminUserSerializer,
    AssignmentActionSerializer,
    AssignmentSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
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


class UserAwareTokenView(TokenView):
    """
    Extends the default token endpoint to include serialized user info
    so the SPA can bootstrap the session without making an extra call.
    """

    def post(self, request, *args, **kwargs):
        uri, headers, body, status_code = self.create_token_response(request)
        data = {}
        if body:
            try:
                data = json.loads(body)
            except ValueError:
                data = {}

        access_token_value = data.get("access_token")
        if status_code == 200 and access_token_value:
            try:
                access_token = AccessToken.objects.select_related("user").get(
                    token=access_token_value
                )
                data["user"] = UserSerializer(access_token.user).data
            except AccessToken.DoesNotExist:
                pass

        json_response = JsonResponse(data, status=status_code)
        for k, v in headers.items():
            json_response[k] = v
        return json_response


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        user = User.objects.filter(email=email).first()

        if user:
            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = (
                f"{settings.FRONTEND_URL}/password-reset/confirm?uid={uid}&token={token}"
            )
            message = (
                "Hola,\n\n"
                "Recibimos una solicitud para restablecer tu contraseña en Escoligest.\n"
                f"Visita el siguiente enlace para continuar: {reset_url}\n\n"
                "Si no solicitaste este cambio, puedes ignorar este mensaje."
            )
            send_mail(
                subject="Recupera tu contraseña",
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )

        return Response(
            {
                "detail": (
                    "Si el correo está registrado, enviaremos instrucciones "
                    "para restablecer la contraseña."
                )
            }
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response(
                {"detail": "El enlace de recuperación no es válido."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response(
                {"detail": "El enlace de recuperación no es válido o expiró."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "La contraseña se actualizó correctamente."})


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
