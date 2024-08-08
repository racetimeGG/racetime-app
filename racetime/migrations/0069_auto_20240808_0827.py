# Generated by Django 3.2.19 on 2024-08-08 08:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('racetime', '0068_leaderboard_inactivity'),
    ]

    operations = [
        migrations.AddField(
            model_name='race',
            name='ranked',
            field=models.BooleanField(db_index=True, default=True, help_text='Untick this to prevent this race result being recorded. Races with a custom goal are always unranked.'),
        ),
        migrations.AlterField(
            model_name='goal',
            name='leaderboard_hide_after',
            field=models.DurationField(help_text='Number of days after which a user is considered inactive if they have not been recorded in a race. Inactive players are not shown on the leaderboard. Leave blank for no threshold.', null=True, verbose_name='Inactivity threshold (days)'),
        ),
    ]
