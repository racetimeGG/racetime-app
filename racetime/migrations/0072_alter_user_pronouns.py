# Generated by Django 3.2.19 on 2024-10-13 10:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('racetime', '0071_user_racetime_us_is_supp_16b095_idx'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='pronouns',
            field=models.CharField(blank=True, choices=[('', 'none'), ('she/her', 'she/her'), ('he/him', 'he/him'), ('they/them', 'they/them'), ('she/they', 'she/they'), ('he/they', 'he/they'), ('any/all', 'any/all'), ('other/ask!', 'other/ask!')], help_text='Select which pronouns appear next to your name on the site.', max_length=16, null=True),
        ),
    ]
