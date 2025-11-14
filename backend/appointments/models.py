import uuid

from django.conf import settings
from django.db import models


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
        blank=True,
    )
    title = models.CharField(max_length=200, default="Cita medica")
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="SCHEDULED"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CalendarOption(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=7, default="#2563eb")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="calendar_options_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PatientActivity(models.Model):
    RECURRENCE_CHOICES = [
        ("NONE", "Una vez"),
        ("DAILY", "Diaria"),
        ("WEEKLY", "Semanal"),
        ("MONTHLY", "Mensual"),
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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activities_assigned",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activities_created",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    calendar_option = models.ForeignKey(
        CalendarOption,
        related_name="activities",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    activity_type = models.CharField(max_length=40)
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
    is_personal = models.BooleanField(default=False)
    completed_at = models.DateTimeField(blank=True, null=True)
    reminder_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]


class PatientActivityCompletion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    activity = models.ForeignKey(
        PatientActivity,
        related_name="completions",
        on_delete=models.CASCADE,
    )
    occurrence_date = models.DateField()
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="activity_completions",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-occurrence_date", "-completed_at"]
        unique_together = ("activity", "occurrence_date")

    def __str__(self) -> str:
        return f"{self.activity.title} - {self.occurrence_date}"


class ReminderSetting(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    minutes_before = models.PositiveIntegerField(default=10)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="reminder_settings_updated",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Reminder setting"
        verbose_name_plural = "Reminder settings"

    def __str__(self) -> str:
        return f"Recordatorio {self.minutes_before} min"

    @classmethod
    def get_solo(cls):
        setting, _created = cls.objects.get_or_create(id=1, defaults={"minutes_before": 10})
        return setting

    @classmethod
    def get_minutes_before(cls) -> int:
        return cls.get_solo().minutes_before
