# Generated by Django 3.2.19 on 2024-08-08 16:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('racetime', '0070_auto_20240808_1522'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='user',
            index=models.Index(fields=['is_supporter', 'patreon_id'], name='racetime_us_is_supp_16b095_idx'),
        ),
    ]
