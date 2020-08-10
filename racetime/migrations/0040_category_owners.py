from django.conf import settings
from django.db import migrations, models


def transfer_owner_to_owners(apps, schema_editor):
    Category = apps.get_model('racetime', 'Category')
    for category in Category.objects.all():
        category.owners.add(category.owner)


class Migration(migrations.Migration):
    dependencies = [
        ('racetime', '0039_auto_20200810_1535'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='owners',
            field=models.ManyToManyField(help_text='Users who hold ownership of this category.', related_name='owned_categories', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(transfer_owner_to_owners, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='category',
            name='owner',
        ),
    ]
