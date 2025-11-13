from django.contrib.auth.hashers import make_password
from django.db import migrations

ADMIN_USERNAME = "admin"
ADMIN_EMAIL = "admin@escoligest.local"
ADMIN_PASSWORD = "EscoliGest#Admin2024"


def create_admin_user(apps, schema_editor):
    User = apps.get_model("coreusers", "User")
    user, created = User.objects.get_or_create(
        username=ADMIN_USERNAME,
        defaults={
            "email": ADMIN_EMAIL,
            "full_name": "Administrador EscoliGest",
            "role": "ADMIN",
            "is_staff": True,
            "is_superuser": True,
            "password": make_password(ADMIN_PASSWORD),
        },
    )
    if not created:
        fields_to_update = []
        if user.role != "ADMIN":
            user.role = "ADMIN"
            fields_to_update.append("role")
        if not user.is_staff:
            user.is_staff = True
            fields_to_update.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            fields_to_update.append("is_superuser")
        # Garantizamos que las credenciales conocidas sigan vigentes
        user.password = make_password(ADMIN_PASSWORD)
        fields_to_update.append("password")
        if fields_to_update:
            user.save(update_fields=fields_to_update)


def remove_admin_user(apps, schema_editor):
    User = apps.get_model("coreusers", "User")
    User.objects.filter(username=ADMIN_USERNAME, email=ADMIN_EMAIL).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coreusers", "0006_create_default_oauth_application"),
    ]

    operations = [
        migrations.RunPython(create_admin_user, remove_admin_user),
    ]
