from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("coreusers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="full_name",
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("PATIENT", "Paciente"),
                    ("MEDIC", "Médico"),
                    ("ADMIN", "Administrador"),
                ],
                default="PATIENT",
                max_length=10,
            ),
        ),
    ]
