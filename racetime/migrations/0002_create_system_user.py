from django.contrib.auth.hashers import make_password
from django.db import migrations


def create_system_user(apps, schema_editor):
    """
    Create a system user.
    """
    User = apps.get_model('racetime', 'User')
    SYSTEM_USER = 'system@racetime.gg'

    if User.objects.filter(email=SYSTEM_USER).exists():
        return

    User.objects.create(
        email=SYSTEM_USER,
        password=make_password(None),
        name='System',
        discriminator='0000',
    )


class Migration(migrations.Migration):
    dependencies = [
        ('racetime', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_system_user, migrations.RunPython.noop),
    ]
