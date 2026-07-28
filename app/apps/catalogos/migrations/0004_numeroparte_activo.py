from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0003_alter_cargacatalogo_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='numeroparte',
            name='activo',
            field=models.BooleanField(default=True),
        ),
    ]
