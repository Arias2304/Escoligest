from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0003_update_default_title"),
    ]

    operations = [
        migrations.CreateModel(
            name="PatientActivity",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "activity_type",
                    models.CharField(
                        choices=[
                            ("APPOINTMENT", "Cita médica"),
                            ("MEDICATION", "Medicamento"),
                            ("THERAPY", "Terapia"),
                        ],
                        max_length=20,
                    ),
                ),
                ("start_time", models.DateTimeField()),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                (
                    "recurrence",
                    models.CharField(
                        choices=[("NONE", "Una vez"), ("DAILY", "Diaria")],
                        default="NONE",
                        max_length=10,
                    ),
                ),
                ("repeat_until", models.DateField(blank=True, null=True)),
                ("color", models.CharField(blank=True, max_length=7)),
                (
                    "status",
                    models.CharField(
                        choices=[("PENDING", "Pendiente"), ("COMPLETED", "Completada")],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "assigned_by",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="activities_assigned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "medic",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="activities_medic",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="activities_patient",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["start_time"]},
        ),
    ]
