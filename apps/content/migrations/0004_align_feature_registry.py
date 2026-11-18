from django.db import migrations


def align(apps, schema_editor):
    Flag = apps.get_model("content", "FeatureFlag")
    Settings = apps.get_model("admin_panel", "PlatformSettings")
    Log = apps.get_model("admin_panel", "AdminLog")
    alias = schema_editor.connection.alias
    mapping = {"ai_hints_enabled": "ai_hints", "contests_enabled": "contests"}
    old_keys = [*mapping, "ai_chat_enabled", "show_complexity_before_solve", "maintenance_mode"]
    previous = list(Flag.objects.using(alias).filter(key__in=old_keys).values("key", "value", "description"))
    for row in previous:
        if row["key"] in mapping:
            Flag.objects.using(alias).get_or_create(key=mapping[row["key"]], defaults={"value": row["value"], "description": row["description"]})
        if row["key"] == "maintenance_mode":
            Settings.objects.using(alias).get_or_create(pk=1, defaults={"maintenance_mode": row["value"]})
    if previous:
        Log.objects.using(alias).create(
            action="UPDATE", object_type="feature", object_id="registry", source="system",
            description="Aligned legacy feature flags with the runtime registry.", changes={"legacy_flags": previous},
        )
        Flag.objects.using(alias).filter(key__in=old_keys).delete()


class Migration(migrations.Migration):
    dependencies = [("content", "0003_featureflag_adcreative_end_at_adcreative_start_at_and_more"), ("admin_panel", "0004_admin_runtime")]
    operations = [migrations.RunPython(align, migrations.RunPython.noop)]
