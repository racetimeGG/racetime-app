# Generated by Django 3.0.14 on 2021-07-31 18:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('racetime', '0055_auto_20210426_1615'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='hide_avatars_while_racing',
            field=models.BooleanField(default=False, help_text='Hide user avatars while in a race.'),
        ),
    ]
