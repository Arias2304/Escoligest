from django.db import migrations

CLIENT_ID = "escoligest-angular"


def create_default_application(apps, schema_editor):
    Application = apps.get_model("oauth2_provider", "Application")
    Application.objects.update_or_create(
        client_id=CLIENT_ID,
        defaults={
            "name": "Escoligest Angular SPA",
            "client_type": "public",
            "authorization_grant_type": "password",
            "skip_authorization": True,
            "redirect_uris": "",
            "client_secret": "",
            "user": None,
        },
    )


def remove_default_application(apps, schema_editor):
    Application = apps.get_model("oauth2_provider", "Application")
    Application.objects.filter(client_id=CLIENT_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("coreusers", "0005_alter_user_email"),
        ("oauth2_provider", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_default_application, remove_default_application),
    ]
