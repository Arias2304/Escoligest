from django.db import migrations


def dedupe_emails(apps, schema_editor):
    User = apps.get_model("coreusers", "User")
    seen = set()
    duplicates = []

    # iterate consistently so the earliest user keeps the original email
    for user in User.objects.exclude(email="").order_by("date_joined", "pk"):
        key = user.email.lower()
        if key in seen:
            duplicates.append(user)
        else:
            seen.add(key)

    for user in duplicates:
        base_email = user.email or "user@example.com"
        if "@" in base_email:
            local, domain = base_email.split("@", 1)
        else:
            local, domain = base_email, ""

        suffix = 1
        new_email = base_email
        while new_email.lower() in seen:
            suffix += 1
            if domain:
                new_email = f"{local}+dup{suffix}@{domain}"
            else:
                new_email = f"{local}+dup{suffix}"

        user.email = new_email
        user.save(update_fields=["email"])
        seen.add(new_email.lower())


class Migration(migrations.Migration):

    dependencies = [
        ("coreusers", "0003_user_additional_fields"),
    ]

    operations = [
        migrations.RunPython(dedupe_emails, migrations.RunPython.noop),
    ]
