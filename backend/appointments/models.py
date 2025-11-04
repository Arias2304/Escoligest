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
