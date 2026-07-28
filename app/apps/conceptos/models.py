import re
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver


class DocumentoConceptos(models.Model):
    FUENTE_MANUAL = 'manual'
    FUENTE_CSV = 'csv'
    FUENTE_XLSX = 'xlsx'
    STATUS_BORRADOR = 'borrador'
    STATUS_CONFIRMADO = 'confirmado'
    STATUS_CANCELADO = 'cancelado'

    FUENTES = [
        (FUENTE_MANUAL, 'Manual'),
        (FUENTE_CSV, 'CSV'),
        (FUENTE_XLSX, 'XLSX'),
    ]
    STATUSES = [
        (STATUS_BORRADOR, 'Borrador'),
        (STATUS_CONFIRMADO, 'Confirmado'),
        (STATUS_CANCELADO, 'Cancelado'),
    ]

    folio = models.CharField(max_length=20, unique=True, blank=True)
    fuente = models.CharField(max_length=20, choices=FUENTES, default=FUENTE_MANUAL)
    status = models.CharField(max_length=20, choices=STATUSES, default=STATUS_BORRADOR)
    total = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal('0'))
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        permissions = [
            (
                'puede_confirmar_documentoconceptos',
                'Puede confirmar documentos de conceptos',
            ),
            (
                'puede_cancelar_documentoconceptos',
                'Puede cancelar documentos de conceptos',
            ),
        ]

    def __str__(self):
        return self.folio or 'Documento de conceptos'

    @property
    def es_borrador(self):
        return self.status == self.STATUS_BORRADOR

    def save(self, *args, **kwargs):
        if not self.folio:
            with transaction.atomic():
                ultimo_id = (
                    DocumentoConceptos.objects.select_for_update()
                    .order_by('-id')
                    .values_list('id', flat=True)
                    .first()
                    or 0
                )
                self.folio = f'CON-{ultimo_id + 1:06d}'
                super().save(*args, **kwargs)
                return
        super().save(*args, **kwargs)

    def recalcular_total(self):
        total = self.conceptos.aggregate(total=Sum('total_concepto'))['total']
        self.total = total or Decimal('0')
        self.save(update_fields=['total', 'updated_at'])


class Concepto(models.Model):
    documento = models.ForeignKey(
        DocumentoConceptos,
        related_name='conceptos',
        on_delete=models.CASCADE,
    )
    numero_parte = models.CharField(max_length=100, blank=True)
    serie = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=100, blank=True)
    descripcion = models.CharField(max_length=255, blank=True)
    cantidad = models.DecimalField(max_digits=12, decimal_places=4)
    precio_unitario = models.DecimalField(max_digits=14, decimal_places=6)
    total_concepto = models.DecimalField(max_digits=16, decimal_places=6, default=Decimal('0'))
    orden = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('orden', 'id')

    def __str__(self):
        return self.numero_parte or self.serie or self.descripcion

    def clean(self):
        super().clean()
        if not any([self.numero_parte, self.serie, self.descripcion]):
            raise ValidationError(
                'Debe capturar numero de parte, serie o descripcion.'
            )
        if self.cantidad is not None and self.cantidad <= 0:
            raise ValidationError({'cantidad': 'La cantidad debe ser mayor a 0.'})
        if self.precio_unitario is not None and self.precio_unitario < 0:
            raise ValidationError(
                {'precio_unitario': 'El precio unitario no puede ser negativo.'}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        self.total_concepto = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)
        self.documento.recalcular_total()

    def delete(self, *args, **kwargs):
        documento = self.documento
        resultado = super().delete(*args, **kwargs)
        documento.recalcular_total()
        return resultado


class PatronSerie(models.Model):
    CAMPO_SERIE = 'serie'
    ESTADO_OBSERVADO = 'observado'
    ESTADO_EN_CRECIMIENTO = 'en_crecimiento'
    ESTADO_PENDIENTE = 'pendiente'
    ESTADO_APROBADO = 'aprobado'
    ESTADO_RECHAZADO = 'rechazado'
    ESTADO_CONFLICTO = 'conflicto'
    ESTADOS = [
        (ESTADO_OBSERVADO, 'Observado'),
        (ESTADO_EN_CRECIMIENTO, 'En crecimiento'),
        (ESTADO_PENDIENTE, 'Pendiente'),
        (ESTADO_APROBADO, 'Aprobado'),
        (ESTADO_RECHAZADO, 'Rechazado'),
        (ESTADO_CONFLICTO, 'Conflicto'),
    ]

    campo_identificador = models.CharField(max_length=30, default=CAMPO_SERIE)
    prefix = models.CharField(max_length=100)
    numero_parte = models.CharField(max_length=100)
    modelo = models.CharField(max_length=255, blank=True)
    descripcion = models.TextField(blank=True)
    firma_json = models.JSONField(default=dict, blank=True)
    firma_texto = models.TextField(blank=True)
    sample_size = models.PositiveIntegerField(default=0)
    min_required = models.PositiveIntegerField(default=3)
    confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal('0'),
    )
    activo = models.BooleanField(default=True)
    source = models.CharField(max_length=50, default='manual')
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_APROBADO)
    evidencias_totales = models.PositiveIntegerField(default=0)
    series_unicas = models.PositiveIntegerField(default=0)
    motivo_conflicto = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    revisado_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(
                fields=('activo', 'campo_identificador', 'prefix'),
                name='conceptos_patron_lookup_idx',
            ),
        ]
        ordering = ('campo_identificador', 'prefix')

    def __str__(self):
        return f'{self.prefix} -> {self.numero_parte}'

    def save(self, *args, **kwargs):
        self.campo_identificador = self.campo_identificador.strip().lower()
        self.prefix = self.prefix.strip().upper()
        super().save(*args, **kwargs)


class HistorialCoincidencia(models.Model):
    documento = models.ForeignKey(
        DocumentoConceptos,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    concepto = models.ForeignKey(
        Concepto,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    serie = models.CharField(max_length=100, blank=True)
    numero_parte = models.CharField(max_length=100, blank=True)
    modelo = models.CharField(max_length=255, blank=True)
    descripcion = models.TextField(blank=True)
    firma_texto = models.TextField(blank=True)
    firma_json = models.JSONField(default=dict, blank=True)
    regla_usada = models.CharField(max_length=50, default='manual')
    match_type = models.CharField(max_length=50, default='confirmado')
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    confirmado_en_importacion = models.BooleanField(default=False)
    usar_para_biblioteca = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return self.numero_parte or self.serie or f'Historial {self.pk}'


def normalizar_texto(valor):
    return re.sub(r'\s+', ' ', (valor or '').strip()).upper()


def construir_firma_concepto(concepto):
    firma_json = {
        'numero_parte': normalizar_texto(concepto.numero_parte),
        'modelo': normalizar_texto(concepto.modelo),
        'descripcion': normalizar_texto(concepto.descripcion),
    }
    firma_texto = '|'.join(
        f'{clave}={valor}' for clave, valor in firma_json.items()
    )
    return firma_texto, firma_json


def registrar_historial_concepto(
    concepto,
    usuario=None,
    regla_usada='manual',
    match_type='confirmado',
    confirmado_en_importacion=False,
):
    if concepto.documento.status != DocumentoConceptos.STATUS_CONFIRMADO:
        return None
    if not (concepto.serie or concepto.numero_parte):
        return None

    firma_texto, firma_json = construir_firma_concepto(concepto)
    historial, _created = HistorialCoincidencia.objects.get_or_create(
        concepto=concepto,
        defaults={
            'documento': concepto.documento,
            'serie': normalizar_texto(concepto.serie),
            'numero_parte': normalizar_texto(concepto.numero_parte),
            'modelo': normalizar_texto(concepto.modelo),
            'descripcion': concepto.descripcion.strip(),
            'firma_texto': firma_texto,
            'firma_json': firma_json,
            'regla_usada': regla_usada,
            'match_type': match_type,
            'confirmado_por': usuario if getattr(usuario, 'is_authenticated', False) else None,
            'confirmado_en_importacion': confirmado_en_importacion,
        },
    )
    return historial


@receiver(post_save, sender=Concepto)
def registrar_historial_concepto_confirmado(sender, instance, **kwargs):
    registrar_historial_concepto(instance)
