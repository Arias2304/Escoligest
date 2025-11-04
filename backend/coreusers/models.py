from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class User(AbstractUser):
    SEX_CHOICES = (
        ("MALE", "Masculino"),
        ("FEMALE", "Femenino"),
        ("OTHER", "Otro"),
    )

    SCOLIOSIS_CONDITIONS = (
        ("IDIOPATHIC", "Escoliosis idiopática"),
        ("DEGENERATIVE", "Escoliosis degenerativa"),
        ("CONGENITAL", "Escoliosis congénita"),
        ("NEUROMUSCULAR", "Escoliosis neuromuscular"),
        ("OTHER", "Otra condición relacionada"),
    )

    ROLE_CHOICES = (
        ("PATIENT", "Paciente"),
        ("MEDIC", "Médico"),
        ("ADMIN", "Administrador"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, blank=True)
    scoliosis_condition = models.CharField(
        max_length=20, choices=SCOLIOSIS_CONDITIONS, blank=True
    )
    specialty = models.CharField(max_length=150, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="PATIENT")


class PatientAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        User, related_name="assigned_medics", on_delete=models.CASCADE
    )
    medic = models.ForeignKey(
        User, related_name="assigned_patients", on_delete=models.CASCADE
    )
    assigned_by = models.ForeignKey(
        User, related_name="assignments_made", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("patient", "medic")
