import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('conceptos', '0004_propuestapatronserie'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='patronserie',
            name='estado',
            field=models.CharField(
                choices=[
                    ('observado', 'Observado'),
                    ('en_crecimiento', 'En crecimiento'),
                    ('pendiente', 'Pendiente'),
                    ('aprobado', 'Aprobado'),
                    ('rechazado', 'Rechazado'),
                    ('conflicto', 'Conflicto'),
                ],
                default='aprobado',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='patronserie',
            name='evidencias_totales',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='patronserie',
            name='series_unicas',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='patronserie',
            name='motivo_conflicto',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='patronserie',
            name='revisado_por',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='patronserie',
            name='revisado_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
