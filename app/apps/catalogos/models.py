from django.db import models
from django.conf import settings


class CargaCatalogo(models.Model):
    TIPO_NUMEROS_PARTE = 'numeros_parte'
    TIPO_SAT_CLAVE_PRODUCTO_SERVICIO = 'sat_clave_producto_servicio'
    ESTADO_EXITOSA = 'exitosa'
    ESTADO_CON_ERRORES = 'con_errores'
    ESTADO_FALLIDA = 'fallida'

    TIPOS = [
        (TIPO_NUMEROS_PARTE, 'Numeros de parte'),
        (TIPO_SAT_CLAVE_PRODUCTO_SERVICIO, 'SAT clave producto/servicio'),
    ]
    ESTADOS = [
        (ESTADO_EXITOSA, 'Exitosa'),
        (ESTADO_CON_ERRORES, 'Con errores'),
        (ESTADO_FALLIDA, 'Fallida'),
    ]

    tipo_catalogo = models.CharField(max_length=50, choices=TIPOS)
    archivo_nombre = models.CharField(max_length=255)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    total_procesadas = models.PositiveIntegerField(default=0)
    total_creadas = models.PositiveIntegerField(default=0)
    total_actualizadas = models.PositiveIntegerField(default=0)
    total_errores = models.PositiveIntegerField(default=0)
    estado = models.CharField(max_length=30, choices=ESTADOS)
    errores_resumen = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.tipo_catalogo} - {self.archivo_nombre}'

    class Meta:
        permissions = [
            (
                'puede_ver_historial_cargas_catalogo',
                'Puede ver historial de cargas de catalogo',
            ),
        ]


class NumeroParte(models.Model):
    numero_parte = models.CharField(max_length=100, unique=True)
    modelo = models.CharField(max_length=100, blank=True)
    descripcion = models.CharField(max_length=255)
    fraccion = models.CharField(max_length=30, blank=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.numero_parte

    class Meta:
        permissions = [
            ('puede_importar_numeroparte', 'Puede importar numeros de parte'),
        ]


class ClaveProductoServicioSAT(models.Model):
    clave = models.CharField(max_length=20, unique=True)
    descripcion = models.CharField(max_length=255)
    incluir_iva_trasladado = models.CharField(max_length=100, blank=True)
    incluir_ieps_trasladado = models.CharField(max_length=100, blank=True)
    complemento_que_debe_incluir = models.TextField(blank=True)
    fecha_inicio_vigencia = models.DateField(null=True, blank=True)
    fecha_fin_vigencia = models.DateField(null=True, blank=True)
    estimulo_franja_fronteriza = models.CharField(max_length=50, blank=True)
    palabras_similares = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.clave} - {self.descripcion}'

    class Meta:
        permissions = [
            ('puede_importar_claves_sat', 'Puede importar claves SAT'),
        ]
