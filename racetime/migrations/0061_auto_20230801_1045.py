from django.db import migrations, models


def set_goal_defaults(apps, schema_editor):
    Goal = apps.get_model('racetime', 'Goal')
    for goal in Goal.objects.all():
        goal.show_leaderboard = goal.active
        goal.streaming_required = goal.category.streaming_required
        goal.allow_stream_override = goal.category.allow_stream_override
        goal.save()


class Migration(migrations.Migration):
    dependencies = [
        ('racetime', '0060_race_time_limit_auto_complete'),
    ]

    operations = [
        migrations.AddField(
            model_name='goal',
            name='allow_stream_override',
            field=models.BooleanField(default=False, help_text='Allow race monitors to change the streaming requirements for their race room. By default, only moderators can change this.'),
        ),
        migrations.AddField(
            model_name='goal',
            name='default_settings',
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name='goal',
            name='show_leaderboard',
            field=models.BooleanField(default=True, help_text='Leaderboard is publicly viewable.'),
        ),
        migrations.AddField(
            model_name='goal',
            name='streaming_required',
            field=models.BooleanField(default=True, help_text='Require entrants to be streaming when they join a race. Moderators may override this for individual races.'),
        ),
        migrations.AddField(
            model_name='goal',
            name='team_races_allowed',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='goal',
            name='team_races_required',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(set_goal_defaults, migrations.RunPython.noop),
    ]
