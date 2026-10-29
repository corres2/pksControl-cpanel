from django.db import migrations

GRUPO_ADMINISTRADORES = 'Administradores'


def crear_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.get_or_create(name=GRUPO_ADMINISTRADORES)


def eliminar_grupo(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name=GRUPO_ADMINISTRADORES).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.RunPython(crear_grupo, eliminar_grupo),
    ]
