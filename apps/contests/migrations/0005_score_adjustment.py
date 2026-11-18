from django.db import migrations, models
from django.db.models import Sum


def preserve_overrides(apps, schema_editor):
    Participant = apps.get_model("contests", "ContestParticipant")
    alias = schema_editor.connection.alias
    for participant in Participant.objects.using(alias).annotate(
        solved_points=Sum("problem_stats__score_awarded", filter=models.Q(problem_stats__is_solved=True))
    ).iterator():
        adjustment = participant.final_score - (participant.solved_points or 0)
        if adjustment:
            Participant.objects.using(alias).filter(pk=participant.pk).update(
                score_adjustment=adjustment, adjustment_reason="Preserved previous score override"
            )


class Migration(migrations.Migration):
    dependencies = [("contests", "0004_contest_lifecycle")]
    operations = [
        migrations.AddField(model_name="contestparticipant", name="adjustment_reason", field=models.CharField(blank=True, max_length=200)),
        migrations.AddField(model_name="contestparticipant", name="score_adjustment", field=models.IntegerField(default=0)),
        migrations.RunPython(preserve_overrides, migrations.RunPython.noop),
    ]
