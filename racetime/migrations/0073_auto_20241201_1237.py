# Generated by Django 3.2.19 on 2024-12-01 12:37

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('racetime', '0072_alter_user_pronouns'),
    ]

    operations = [
        migrations.AlterField(
            model_name='team',
            name='profile',
            field=models.TextField(blank=True, help_text="Add some information to your team's public profile. It can include anything you like.", max_length=2000, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='profile_bio',
            field=models.TextField(blank=True, help_text='Add some information to your public profile. Plug your Discord server, stream schedule, or anything else you like.', max_length=2000, null=True),
        ),
    ]
