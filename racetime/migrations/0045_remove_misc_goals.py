from django.db import migrations
from django.db.models import F


def remove_misc_goals(apps, schema_editor):
    Goal = apps.get_model('racetime', 'Goal')
    Race = apps.get_model('racetime', 'Race')

    goals = Goal.objects.filter(category__slug='misc')
    races = Race.objects.filter(goal__in=goals)

    for race in races:
        race.custom_goal = race.goal.name
        race.goal = None
        race.recordable = False
        race.version = F('version') + 1
        race.save()

    goals.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('racetime', '0044_cancel_empty_races'),
    ]

    operations = [
        migrations.RunPython(remove_misc_goals, migrations.RunPython.noop),
    ]
