from django.db import migrations
from django.db.models import F


def cancel_empty_races(apps, schema_editor):
    Race = apps.get_model('racetime', 'Race')
    races = Race.objects.filter(
        state='finished',
        recordable=False,
        recorded=False,
    ).exclude(
        entrant__finish_time__isnull=False,
    )
    for race in races:
        race.state = 'cancelled'
        race.cancelled_at = race.ended_at
        race.version = F('version') + 1
        race.save()


class Migration(migrations.Migration):
    dependencies = [
        ('racetime', '0043_auto_20200820_1341'),
    ]

    operations = [
        migrations.RunPython(cancel_empty_races, migrations.RunPython.noop),
    ]
