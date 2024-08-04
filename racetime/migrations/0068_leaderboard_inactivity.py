from django.db import migrations, models


def populate_last_raced(apps, schema_editor):
    UserRanking = apps.get_model('racetime', 'UserRanking')
    Race = apps.get_model('racetime', 'Race')
    for ranking in UserRanking.objects.all():
        last_race = Race.objects.filter(
            goal_id=ranking.goal_id,
            entrant__user_id=ranking.user_id,
            recorded=True,
        ).order_by('-opened_at').first()
        if last_race:
            ranking.last_raced = last_race.opened_at
            ranking.save()


class Migration(migrations.Migration):
    dependencies = [
        ('racetime', '0067_alter_team_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='goal',
            name='leaderboard_hide_after',
            field=models.DurationField(null=True),
        ),
        migrations.AddField(
            model_name='userranking',
            name='last_raced',
            field=models.DateField(null=True),
        ),
        migrations.AddIndex(
            model_name='userranking',
            index=models.Index(fields=['category', 'goal', 'last_raced'], name='racetime_us_categor_013cdd_idx'),
        ),
        migrations.RunPython(populate_last_raced, migrations.RunPython.noop),
    ]
