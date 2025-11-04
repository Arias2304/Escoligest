from rest_framework import viewsets, permissions
from .models import Appointment
from .serializers import AppointmentSerializer

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
