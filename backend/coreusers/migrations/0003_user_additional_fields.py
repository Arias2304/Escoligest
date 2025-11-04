from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("coreusers", "0002_user_full_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="phone_number",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="user",
            name="sex",
            field=models.CharField(
                blank=True,
                choices=[
                    ("MALE", "Masculino"),
                    ("FEMALE", "Femenino"),
                    ("OTHER", "Otro"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="scoliosis_condition",
            field=models.CharField(
                blank=True,
                choices=[
                    ("IDIOPATHIC", "Escoliosis idiopática"),
                    ("DEGENERATIVE", "Escoliosis degenerativa"),
                    ("CONGENITAL", "Escoliosis congénita"),
                    ("NEUROMUSCULAR", "Escoliosis neuromuscular"),
                    ("OTHER", "Otra condición relacionada"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="specialty",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.CreateModel(
            name="PatientAssignment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "assigned_by",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="assignments_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "medic",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="assigned_patients",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="assigned_medics",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="patientassignment",
            unique_together={("patient", "medic")},
        ),
    ]
