import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def consolidate(apps, schema_editor):
    Settings = apps.get_model("admin_panel", "PlatformSettings")
    Log = apps.get_model("admin_panel", "AdminLog")
    alias = schema_editor.connection.alias
    rows = list(Settings.objects.using(alias).order_by("id").values())
    # Preserve the previously effective (oldest) row, with all original records
    # archived in the audit trail before dropping unused fields/duplicate rows.
    if rows:
        archived = [{**row, "updated_at": row["updated_at"].isoformat()} for row in rows]
        Log.objects.using(alias).create(
            action="UPDATE", object_type="platform_settings", object_id="1", source="system",
            description="Consolidated platform settings; original rows archived before schema cleanup.",
            changes={"legacy_rows": archived},
        )
        first = rows[0]
        Settings.objects.using(alias).exclude(pk=first["id"]).delete()
        if first["id"] != 1:
            Settings.objects.using(alias).filter(pk=first["id"]).update(id=1)
        # This old model default was never enforced; keep using the environment
        # until an admin explicitly overrides the daily limit.
        if first["ai_hints_free_daily"] == 20:
            Settings.objects.using(alias).filter(pk=1).update(ai_hints_free_daily=None)
    Log.objects.using(alias).filter(admin__isnull=True).update(source="system")


class Migration(migrations.Migration):
    dependencies = [
        ("admin_panel", "0003_contest_lifecycle"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.AlterModelOptions(name="adminlog", options={"ordering": ["-created_at", "-id"]}),
        migrations.AlterModelOptions(name="platformsettings", options={"verbose_name": "platform settings", "verbose_name_plural": "platform settings"}),
        migrations.AddField(model_name="adminlog", name="changes", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="adminlog", name="object_repr", field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name="adminlog", name="source", field=models.CharField(choices=[("api", "Admin dashboard"), ("django", "Django admin"), ("system", "System")], default="api", max_length=10)),
        migrations.AlterField(model_name="adminlog", name="admin", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="admin_logs", to=settings.AUTH_USER_MODEL)),
        migrations.AlterField(model_name="adminlog", name="object_id", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="platformsettings", name="ai_hints_pro_daily", field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(10000)], help_text="Hints per day on the Pro plan. Leave blank for the server default.")),
        migrations.AddField(model_name="platformsettings", name="announcement_level", field=models.CharField(choices=[("info", "Info"), ("warning", "Warning"), ("success", "Success")], default="info", max_length=10)),
        migrations.AddField(model_name="platformsettings", name="announcement_text", field=models.CharField(blank=True, max_length=300, help_text="Shown in a banner on every page while set.")),
        migrations.AlterField(model_name="platformsettings", name="ai_hints_free_daily", field=models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MaxValueValidator(10000)], help_text="Hints per day on the Free plan. Leave blank for the server default.")),
        migrations.AlterField(model_name="platformsettings", name="maintenance_mode", field=models.BooleanField(default=False, help_text="Shows the maintenance banner and pauses Run/Submit for everyone except admins.")),
        migrations.RunPython(consolidate, migrations.RunPython.noop),
        migrations.RemoveField(model_name="platformsettings", name="ai_chat_free_daily"),
        migrations.RemoveField(model_name="platformsettings", name="max_problem_limit"),
        migrations.RemoveField(model_name="platformsettings", name="max_submission_size_kb"),
        migrations.AddIndex(model_name="adminlog", index=models.Index(fields=["object_type", "object_id"], name="admin_logs_object__ee4ba4_idx")),
        migrations.AddConstraint(model_name="platformsettings", constraint=models.CheckConstraint(check=models.Q(pk=1), name="platform_settings_singleton")),
    ]
