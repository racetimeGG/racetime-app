# Generated migration for adding YouTube support to User model
# This migration should be created using: python manage.py makemigrations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('racetime', '0081_alter_race_bot_meta'),  # Update this to the latest migration
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='youtube_id',
            field=models.CharField(
                max_length=50,
                null=True,
                editable=False,
                help_text='YouTube channel ID'
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='youtube_code',
            field=models.TextField(
                null=True,
                editable=False,
                help_text='YouTube OAuth token data (JSON)'
            ),
        ),
    ]