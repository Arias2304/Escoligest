from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0002_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="appointment",
            name="title",
            field=models.CharField(max_length=200, default="Cita médica"),
        ),
    ]
