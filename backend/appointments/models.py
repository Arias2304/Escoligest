from django.conf import settings
from django.db import models
import uuid


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("SCHEDULED", "Scheduled"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="appointments_patient",
        on_delete=models.CASCADE,
    )
    professional = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="appointments_professional",
        on_delete=models.SET_NULL,
        null=True,
    )
    title = models.CharField(max_length=200, default="Cita médica")
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SCHEDULED")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PatientActivity(models.Model):
    ACTIVITY_TYPES = [
        ("APPOINTMENT", "Cita médica"),
        ("MEDICATION", "Medicamento"),
        ("THERAPY", "Terapia"),
    ]

    RECURRENCE_CHOICES = [
        ("NONE", "Una vez"),
        ("DAILY", "Diaria"),
    ]

    STATUS_CHOICES = [
        ("PENDING", "Pendiente"),
        ("COMPLETED", "Completada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activities_patient",
        on_delete=models.CASCADE,
    )
    medic = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activities_medic",
        on_delete=models.CASCADE,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activities_assigned",
        on_delete=models.CASCADE,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(blank=True, null=True)
    recurrence = models.CharField(
        max_length=10, choices=RECURRENCE_CHOICES, default="NONE"
    )
    repeat_until = models.DateField(blank=True, null=True)
    color = models.CharField(max_length=7, blank=True)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="PENDING"
    )
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]
