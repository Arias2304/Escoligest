from django.db import migrations


def create_default_calendar_options(apps, schema_editor):
    CalendarOption = apps.get_model("appointments", "CalendarOption")
    defaults = [
        ("APPOINTMENT", "Cita medica", "#2563eb"),
        ("MEDICATION", "Medicamento", "#10b981"),
        ("THERAPY", "Terapia", "#f97316"),
        ("REMINDER", "Recordatorio personal", "#6366f1"),
    ]
    for slug, name, color in defaults:
        CalendarOption.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "color": color,
                "is_active": True,
            },
        )


def remove_default_calendar_options(apps, schema_editor):
    CalendarOption = apps.get_model("appointments", "CalendarOption")
    CalendarOption.objects.filter(
        slug__in=["APPOINTMENT", "MEDICATION", "THERAPY", "REMINDER"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("appointments", "0005_patientactivity_created_by_and_more"),
    ]

    operations = [
        migrations.RunPython(
            create_default_calendar_options, remove_default_calendar_options
        ),
    ]
