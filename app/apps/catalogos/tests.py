from io import BytesIO
from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.shortcuts import render
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.catalogos.models import CargaCatalogo, NumeroParte
from apps.catalogos.services.importacion import (
    MAX_FILAS_NUMEROS_PARTE,
    analizar_numeros_parte_csv,
    importar_claves_sat_csv,
    importar_numeros_parte_csv,
)
from apps.catalogos.views import (
    PREVIEW_NUMEROS_PARTE_SESSION_KEY,
    _registrar_carga_catalogo,
    cargas_list,
    descargar_plantilla_numeros_parte,
    descargar_plantilla_sat,
    exportar_cargas_csv,
    exportar_numeros_parte_csv,
    exportar_sat_csv,
    importar_numeros_parte,
    importar_sat,
    numeros_parte_list,
    sat_list,
)


GRUPOS_ESPERADOS = {
    'Catalogos - Consulta': {
        'view_numeroparte',
        'view_claveproductoserviciosat',
    },
    'Catalogos - Importacion': {
        'view_numeroparte',
        'puede_importar_numeroparte',
        'view_claveproductoserviciosat',
        'puede_importar_claves_sat',
    },
    'Catalogos - Auditoria': {
        'puede_ver_historial_cargas_catalogo',
    },
    'Catalogos - Administrador': {
        'view_numeroparte',
        'add_numeroparte',
        'change_numeroparte',
        'delete_numeroparte',
        'puede_importar_numeroparte',
        'view_claveproductoserviciosat',
        'add_claveproductoserviciosat',
        'change_claveproductoserviciosat',
        'delete_claveproductoserviciosat',
        'puede_importar_claves_sat',
        'view_cargacatalogo',
        'puede_ver_historial_cargas_catalogo',
    },
}


def _csv(contenido):
    archivo = BytesIO(contenido.encode('utf-8'))
    archivo.name = 'catalogo.csv'
    return archivo


def _xlsx(filas, nombre='catalogo.xlsx'):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    for fila in filas:
        sheet.append(fila)
    archivo = BytesIO()
    workbook.save(archivo)
    archivo.seek(0)
    archivo.name = nombre
    return archivo


def _user(con_permiso=True, superusuario=False, permisos=None):
    permisos = permisos or set()

    def has_perm(permiso):
        return con_permiso or superusuario or permiso in permisos

    return SimpleNamespace(
        is_authenticated=True,
        is_superuser=superusuario,
        has_perm=has_perm,
        has_perms=lambda requeridos: all(has_perm(permiso) for permiso in requeridos),
        get_username=lambda: 'usuario.prueba',
    )


def _render_base_con_usuario(request, usuario):
    request.user = usuario
    return render(request, 'core/home.html', {'app_version': 'test'})


class FakeQuerySet(list):
    def __init__(self, items, filtered_items=None):
        super().__init__(items)
        self.filtered_items = filtered_items or []
        self.filter_called = False

    def all(self):
        return self

    def order_by(self, *fields):
        return self

    def select_related(self, *fields):
        return self

    def filter(self, *args, **kwargs):
        self.filter_called = True
        items = self.filtered_items or list(self)
        return FakeQuerySet(items, filtered_items=items)


class ImportarNumerosParteCSVTests(SimpleTestCase):
    def test_importa_csv_por_posicion(self):
        archivo = _csv('ABC123,MOD-2026,Sensor de temperatura,9026.10.01\n')

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            manager.filter.return_value.values_list.return_value = []
            manager.update_or_create.return_value = (SimpleNamespace(), True)
            resultado = importar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['procesadas'], 1)
        self.assertEqual(resultado['creadas'], 1)
        manager.update_or_create.assert_called_once_with(
            numero_parte='ABC123',
            defaults={
                'modelo': 'MOD-2026',
                'descripcion': 'Sensor de temperatura',
                'fraccion': '9026.10.01',
            },
        )

    def test_actualiza_si_numero_parte_ya_existe(self):
        archivo = _csv('ABC123,,Sensor de temperatura,\n')

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            manager.filter.return_value.values_list.return_value = ['ABC123']
            manager.update_or_create.return_value = (SimpleNamespace(), False)
            resultado = importar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['actualizadas'], 1)

    def test_reporta_error_si_falta_numero_parte(self):
        archivo = _csv(',MOD-2026,Sensor de temperatura,\n')

        resultado = importar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['creadas'], 0)
        self.assertEqual(resultado['errores'][0]['fila'], 1)
        self.assertIn('numero_parte', resultado['errores'][0]['error'])

    def test_reporta_error_si_falta_descripcion(self):
        archivo = _csv('ABC123,MOD-2026,,9026.10.01\n')

        resultado = importar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['creadas'], 0)
        self.assertEqual(resultado['errores'][0]['fila'], 1)
        self.assertIn('descripcion', resultado['errores'][0]['error'])

    def test_analiza_csv_sin_guardar_cambios(self):
        archivo = _csv('ABC123,MOD-2026,Sensor de temperatura,9026.10.01\n')

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            manager.filter.return_value.values_list.return_value = []
            resultado = analizar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['filas_validas'], 1)
        self.assertEqual(resultado['crearian'], 1)
        manager.update_or_create.assert_not_called()

    def test_analiza_csv_detecta_duplicados_en_archivo(self):
        archivo = _csv(
            'ABC123,MOD-2026,Sensor de temperatura,9026.10.01\n'
            'ABC123,MOD-2026,Sensor duplicado,9026.10.01\n'
        )

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            manager.filter.return_value.values_list.return_value = []
            resultado = analizar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['filas_validas'], 1)
        self.assertEqual(len(resultado['errores']), 1)
        self.assertIn('duplicado', resultado['errores'][0]['error'])

    def test_analiza_csv_limita_filas(self):
        contenido = ''.join(
            f'NP-{indice},MOD,Descripcion {indice},\n'
            for indice in range(MAX_FILAS_NUMEROS_PARTE + 1)
        )

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            manager.filter.return_value.values_list.return_value = []
            resultado = analizar_numeros_parte_csv(_csv(contenido))

        self.assertEqual(resultado['filas_validas'], MAX_FILAS_NUMEROS_PARTE)
        self.assertIn('limite', resultado['errores'][0]['error'])

    def test_importa_xlsx_por_posicion_y_omite_encabezado(self):
        archivo = _xlsx([
            ['numero_parte', 'modelo', 'descripcion', 'fraccion'],
            ['XLSX-001', 'MOD-X', 'Descripcion XLSX', '1234.56.78'],
        ])

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            manager.filter.return_value.values_list.return_value = []
            manager.update_or_create.return_value = (SimpleNamespace(), True)
            resultado = importar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['procesadas'], 1)
        self.assertEqual(resultado['creadas'], 1)
        manager.update_or_create.assert_called_once_with(
            numero_parte='XLSX-001',
            defaults={
                'modelo': 'MOD-X',
                'descripcion': 'Descripcion XLSX',
                'fraccion': '1234.56.78',
            },
        )

    def test_analiza_xlsx_sin_guardar_y_detecta_error(self):
        archivo = _xlsx([
            ['numero_parte', 'modelo', 'descripcion', 'fraccion'],
            ['', 'MOD-X', 'Descripcion XLSX', ''],
        ])

        with patch('apps.catalogos.services.importacion.NumeroParte.objects') as manager:
            resultado = analizar_numeros_parte_csv(archivo)

        self.assertEqual(resultado['filas_validas'], 0)
        self.assertIn('numero_parte', resultado['errores'][0]['error'])
        manager.update_or_create.assert_not_called()


class ImportarClavesSATCSVTests(SimpleTestCase):
    def test_importa_sat_ignorando_metadatos(self):
        archivo = _csv(
            'Catalogo SAT\n'
            'Actualizado al 2026\n'
            'Clave,Descripcion,IVA,IEPS\n'
            '10101500,Animales vivos de granja,Opcional,Opcional,,1/1/2022,,1,Publico\n'
        )

        with patch('apps.catalogos.services.importacion.ClaveProductoServicioSAT.objects') as manager:
            manager.update_or_create.return_value = (SimpleNamespace(), True)
            resultado = importar_claves_sat_csv(archivo)

        self.assertEqual(resultado['procesadas'], 1)
        self.assertEqual(resultado['creadas'], 1)
        manager.update_or_create.assert_called_once()

    def test_detecta_primera_fila_de_datos_por_clave_numerica(self):
        archivo = _csv(
            'metadata\n'
            'otra fila\n'
            '10101500,Animales vivos de granja,,,,,,,\n'
            '10101600,Animales domesticos,,,,,,,\n'
        )

        with patch('apps.catalogos.services.importacion.ClaveProductoServicioSAT.objects') as manager:
            manager.update_or_create.return_value = (SimpleNamespace(), True)
            resultado = importar_claves_sat_csv(archivo)

        self.assertEqual(resultado['procesadas'], 2)
        self.assertEqual(manager.update_or_create.call_count, 2)


class CrearGruposCatalogosCommandTests(TestCase):
    def test_comando_crea_los_grupos_esperados(self):
        call_command('crear_grupos_catalogos', stdout=StringIO())

        self.assertEqual(
            set(
                Group.objects.filter(name__in=GRUPOS_ESPERADOS).values_list(
                    'name',
                    flat=True,
                )
            ),
            set(GRUPOS_ESPERADOS),
        )

    def test_comando_asigna_permisos_esperados(self):
        call_command('crear_grupos_catalogos', stdout=StringIO())

        for nombre_grupo, permisos_esperados in GRUPOS_ESPERADOS.items():
            grupo = Group.objects.get(name=nombre_grupo)
            permisos = set(grupo.permissions.values_list('codename', flat=True))
            self.assertEqual(permisos, permisos_esperados)

    def test_comando_es_idempotente(self):
        call_command('crear_grupos_catalogos', stdout=StringIO())
        total_grupos = Group.objects.count()

        call_command('crear_grupos_catalogos', stdout=StringIO())

        self.assertEqual(Group.objects.count(), total_grupos)
        self.assertEqual(
            Group.objects.filter(name__in=GRUPOS_ESPERADOS).count(),
            len(GRUPOS_ESPERADOS),
        )


class NumeroParteManualViewsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='operador',
            password='clave-segura',
        )

    def _login(self):
        self.client.force_login(self.user)

    def _grant(self, *codenames):
        permisos = Permission.objects.filter(
            content_type__app_label='catalogos',
            codename__in=codenames,
        )
        self.user.user_permissions.add(*permisos)

    def _crear_numero_parte(self, numero_parte='NP-001', activo=True):
        return NumeroParte.objects.create(
            numero_parte=numero_parte,
            modelo='MOD-A',
            descripcion='Sensor de temperatura',
            fraccion='9026.10.01',
            activo=activo,
        )

    def test_numero_parte_activo_default_true(self):
        numero_parte = NumeroParte.objects.create(
            numero_parte='NP-DEFAULT',
            modelo='MOD-A',
            descripcion='Sensor de temperatura',
            fraccion='9026.10.01',
        )

        self.assertTrue(numero_parte.activo)

    def test_detalle_requiere_login(self):
        response = self.client.get(
            reverse('catalogos:numero_parte_detail', kwargs={'pk': 1})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_detalle_requiere_permiso_view_numeroparte(self):
        numero_parte = self._crear_numero_parte()
        self._login()

        response = self.client.get(
            reverse('catalogos:numero_parte_detail', kwargs={'pk': numero_parte.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_crear_requiere_permiso_add_numeroparte(self):
        self._login()

        response = self.client.get(reverse('catalogos:numero_parte_create'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_editar_requiere_permiso_change_numeroparte(self):
        numero_parte = self._crear_numero_parte()
        self._login()

        response = self.client.get(
            reverse('catalogos:numero_parte_update', kwargs={'pk': numero_parte.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_usuario_con_permiso_puede_crear_numero_parte(self):
        self._grant('add_numeroparte')
        self._login()

        response = self.client.post(
            reverse('catalogos:numero_parte_create'),
            {
                'numero_parte': 'NP-001',
                'modelo': 'MOD-A',
                'descripcion': 'Sensor de temperatura',
                'fraccion': '9026.10.01',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(NumeroParte.objects.filter(numero_parte='NP-001').exists())

    def test_crear_duplicado_muestra_error_y_no_duplica(self):
        self._crear_numero_parte('NP-001')
        self._grant('add_numeroparte')
        self._login()

        response = self.client.post(
            reverse('catalogos:numero_parte_create'),
            {
                'numero_parte': 'NP-001',
                'modelo': 'MOD-B',
                'descripcion': 'Sensor duplicado',
                'fraccion': '9026.10.01',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ya existe un numero de parte con ese valor.')
        self.assertEqual(NumeroParte.objects.filter(numero_parte='NP-001').count(), 1)

    def test_usuario_con_permiso_puede_editar_numero_parte(self):
        numero_parte = self._crear_numero_parte()
        self._grant('change_numeroparte')
        self._login()

        response = self.client.post(
            reverse('catalogos:numero_parte_update', kwargs={'pk': numero_parte.pk}),
            {
                'numero_parte': 'NP-001',
                'modelo': 'MOD-Z',
                'descripcion': 'Sensor actualizado',
                'fraccion': '9026.10.02',
            },
        )

        self.assertEqual(response.status_code, 302)
        numero_parte.refresh_from_db()
        self.assertEqual(numero_parte.modelo, 'MOD-Z')
        self.assertEqual(numero_parte.descripcion, 'Sensor actualizado')

    def test_listado_muestra_boton_nuevo_solo_con_permiso_add(self):
        self._crear_numero_parte()
        self._grant('view_numeroparte')
        self._login()

        response = self.client.get(reverse('catalogos:numeros_parte_list'))

        self.assertNotContains(response, 'Nuevo numero de parte')

        self._grant('add_numeroparte')
        response = self.client.get(reverse('catalogos:numeros_parte_list'))

        self.assertContains(response, 'Nuevo numero de parte')

    def test_listado_muestra_boton_editar_solo_con_permiso_change(self):
        self._crear_numero_parte()
        self._grant('view_numeroparte')
        self._login()

        response = self.client.get(reverse('catalogos:numeros_parte_list'))

        self.assertNotContains(response, 'Editar')

        self._grant('change_numeroparte')
        response = self.client.get(reverse('catalogos:numeros_parte_list'))

        self.assertContains(response, 'Editar')

    def test_listado_default_muestra_activos_y_oculta_inactivos(self):
        self._crear_numero_parte('NP-ACTIVO', activo=True)
        self._crear_numero_parte('NP-INACTIVO', activo=False)
        self._grant('view_numeroparte')
        self._login()

        response = self.client.get(reverse('catalogos:numeros_parte_list'))

        self.assertContains(response, 'NP-ACTIVO')
        self.assertNotContains(response, 'NP-INACTIVO')

    def test_filtro_estado_inactivos(self):
        self._crear_numero_parte('NP-ACTIVO', activo=True)
        self._crear_numero_parte('NP-INACTIVO', activo=False)
        self._grant('view_numeroparte')
        self._login()

        response = self.client.get(
            reverse('catalogos:numeros_parte_list'),
            {'estado': 'inactivos'},
        )

        self.assertNotContains(response, 'NP-ACTIVO')
        self.assertContains(response, 'NP-INACTIVO')

    def test_filtro_estado_todos(self):
        self._crear_numero_parte('NP-ACTIVO', activo=True)
        self._crear_numero_parte('NP-INACTIVO', activo=False)
        self._grant('view_numeroparte')
        self._login()

        response = self.client.get(
            reverse('catalogos:numeros_parte_list'),
            {'estado': 'todos'},
        )

        self.assertContains(response, 'NP-ACTIVO')
        self.assertContains(response, 'NP-INACTIVO')

    def test_exportacion_numeros_parte_respeta_estado(self):
        self._crear_numero_parte('NP-ACTIVO', activo=True)
        self._crear_numero_parte('NP-INACTIVO', activo=False)
        self._grant('view_numeroparte')
        self._login()

        response = self.client.get(
            reverse('catalogos:exportar_numeros_parte_csv'),
            {'estado': 'inactivos'},
        )
        contenido = response.content.decode('utf-8-sig')

        self.assertNotIn('NP-ACTIVO', contenido)
        self.assertIn('NP-INACTIVO', contenido)

    def test_usuario_con_change_puede_inactivar_y_activar(self):
        numero_parte = self._crear_numero_parte()
        self._grant('change_numeroparte')
        self._login()

        response = self.client.post(
            reverse('catalogos:numero_parte_inactivar', kwargs={'pk': numero_parte.pk})
        )
        self.assertEqual(response.status_code, 302)
        numero_parte.refresh_from_db()
        self.assertFalse(numero_parte.activo)

        response = self.client.post(
            reverse('catalogos:numero_parte_activar', kwargs={'pk': numero_parte.pk})
        )
        self.assertEqual(response.status_code, 302)
        numero_parte.refresh_from_db()
        self.assertTrue(numero_parte.activo)

    def test_usuario_sin_change_no_puede_inactivar_ni_activar(self):
        numero_parte = self._crear_numero_parte()
        self._login()

        response = self.client.post(
            reverse('catalogos:numero_parte_inactivar', kwargs={'pk': numero_parte.pk})
        )

        self.assertEqual(response.status_code, 302)
        numero_parte.refresh_from_db()
        self.assertTrue(numero_parte.activo)

    def test_importacion_crea_nuevos_activos(self):
        resultado = importar_numeros_parte_csv(_csv('NP-NUEVO,MOD,Sensor,\n'))

        self.assertEqual(resultado['creadas'], 1)
        self.assertTrue(NumeroParte.objects.get(numero_parte='NP-NUEVO').activo)

    def test_importacion_actualiza_existente_sin_cambiar_activo(self):
        self._crear_numero_parte('NP-INACTIVO', activo=False)

        resultado = importar_numeros_parte_csv(
            _csv('NP-INACTIVO,MOD-Z,Sensor actualizado,\n')
        )

        numero_parte = NumeroParte.objects.get(numero_parte='NP-INACTIVO')
        self.assertEqual(resultado['actualizadas'], 1)
        self.assertFalse(numero_parte.activo)
        self.assertEqual(numero_parte.modelo, 'MOD-Z')

    def test_superusuario_puede_crear_editar_y_ver(self):
        superusuario = get_user_model().objects.create_superuser(
            username='admin',
            password='clave-segura',
        )
        self.client.force_login(superusuario)

        response = self.client.post(
            reverse('catalogos:numero_parte_create'),
            {
                'numero_parte': 'NP-ADMIN',
                'modelo': 'MOD-A',
                'descripcion': 'Sensor admin',
                'fraccion': '',
            },
        )

        self.assertEqual(response.status_code, 302)
        numero_parte = NumeroParte.objects.get(numero_parte='NP-ADMIN')

        detail_response = self.client.get(
            reverse('catalogos:numero_parte_detail', kwargs={'pk': numero_parte.pk})
        )
        self.assertEqual(detail_response.status_code, 200)

        update_response = self.client.post(
            reverse('catalogos:numero_parte_update', kwargs={'pk': numero_parte.pk}),
            {
                'numero_parte': 'NP-ADMIN',
                'modelo': 'MOD-B',
                'descripcion': 'Sensor admin actualizado',
                'fraccion': '',
            },
        )

        self.assertEqual(update_response.status_code, 302)
        numero_parte.refresh_from_db()
        self.assertEqual(numero_parte.modelo, 'MOD-B')


class CatalogosViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_vista_de_carga_requiere_login(self):
        response = self.client.get(reverse('catalogos:importar_numeros_parte'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_vista_muestra_tabla_de_referencia(self):
        request = self.factory.get(reverse('catalogos:importar_numeros_parte'))
        request.user = _user(True)
        response = importar_numeros_parte(request)
        contenido = response.content.decode('utf-8')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Columna', contenido)
        self.assertIn('numero_parte', contenido)

    def test_listado_numeros_parte_requiere_login(self):
        response = self.client.get(reverse('catalogos:numeros_parte_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_usuario_sin_permiso_no_puede_ver_listado_numeros_parte(self):
        request = self.factory.get(reverse('catalogos:numeros_parte_list'))
        request.user = _user(False)

        response = numeros_parte_list(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_listado_sat_requiere_login(self):
        response = self.client.get(reverse('catalogos:sat_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_usuario_sin_permiso_no_puede_ver_listado_sat(self):
        request = self.factory.get(reverse('catalogos:sat_list'))
        request.user = _user(False)

        response = sat_list(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_listado_numeros_parte_responde_con_usuario_autenticado(self):
        request = self.factory.get(reverse('catalogos:numeros_parte_list'))
        request.user = _user(True)
        items = [
            SimpleNamespace(
                pk=1,
                numero_parte='ABC123',
                modelo='MOD-2026',
                descripcion='Sensor de temperatura',
                fraccion='9026.10.01',
                updated_at=None,
            )
        ]
        queryset = FakeQuerySet(items, filtered_items=items)

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = numeros_parte_list(request)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8')
        self.assertIn('ABC123', contenido)
        self.assertIn('Historial de cargas', contenido)
        self.assertIn('Cerrar sesion', contenido)

    def test_listado_sat_responde_con_usuario_autenticado(self):
        request = self.factory.get(reverse('catalogos:sat_list'))
        request.user = _user(True)
        queryset = FakeQuerySet([
            SimpleNamespace(
                clave='10101500',
                descripcion='Animales vivos de granja',
                incluir_iva_trasladado='Opcional',
                incluir_ieps_trasladado='Opcional',
                fecha_inicio_vigencia=None,
                fecha_fin_vigencia=None,
            )
        ])

        with patch('apps.catalogos.views.ClaveProductoServicioSAT.objects', queryset):
            response = sat_list(request)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8')
        self.assertIn('10101500', contenido)
        self.assertIn('Historial de cargas', contenido)
        self.assertIn('Cerrar sesion', contenido)

    def test_busqueda_numeros_parte_filtra_resultados(self):
        request = self.factory.get(reverse('catalogos:numeros_parte_list'), {'q': 'ABC'})
        request.user = _user(True)
        queryset = FakeQuerySet(
            [
                SimpleNamespace(
                    pk=1,
                    numero_parte='ABC123',
                    modelo='MOD-2026',
                    descripcion='Sensor de temperatura',
                    fraccion='9026.10.01',
                    updated_at=None,
                ),
                SimpleNamespace(
                    pk=2,
                    numero_parte='XYZ999',
                    modelo='MOD-2025',
                    descripcion='Valvula',
                    fraccion='8481.80.99',
                    updated_at=None,
                ),
            ],
            filtered_items=[
                SimpleNamespace(
                    pk=1,
                    numero_parte='ABC123',
                    modelo='MOD-2026',
                    descripcion='Sensor de temperatura',
                    fraccion='9026.10.01',
                    updated_at=None,
                )
            ],
        )

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = numeros_parte_list(request)

        contenido = response.content.decode('utf-8')
        self.assertTrue(queryset.filter_called)
        self.assertIn('ABC123', contenido)
        self.assertNotIn('XYZ999', contenido)

    def test_filtros_numeros_parte_modelo_y_fraccion_son_combinables(self):
        request = self.factory.get(
            reverse('catalogos:numeros_parte_list'),
            {'q': 'sensor', 'modelo': 'MOD-2026', 'fraccion': '9026'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet([
            SimpleNamespace(
                pk=1,
                numero_parte='ABC123',
                modelo='MOD-2026',
                descripcion='Sensor de temperatura',
                fraccion='9026.10.01',
                updated_at=None,
            )
        ])

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = numeros_parte_list(request)

        contenido = response.content.decode('utf-8')
        self.assertEqual(queryset.filter_called, True)
        self.assertIn('value="sensor"', contenido)
        self.assertIn('value="MOD-2026"', contenido)
        self.assertIn('value="9026"', contenido)

    def test_paginacion_numeros_parte_preserva_filtros(self):
        request = self.factory.get(
            reverse('catalogos:numeros_parte_list'),
            {'q': 'sensor', 'modelo': 'MOD', 'fraccion': '9026'},
        )
        request.user = _user(True)
        items = [
            SimpleNamespace(
                pk=indice,
                numero_parte=f'NP-{indice}',
                modelo='MOD',
                descripcion='Sensor',
                fraccion='9026',
                updated_at=None,
            )
            for indice in range(30)
        ]
        queryset = FakeQuerySet(items, filtered_items=items)

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = numeros_parte_list(request)

        contenido = response.content.decode('utf-8')
        self.assertIn('q=sensor&amp;modelo=MOD&amp;fraccion=9026&page=2', contenido)

    def test_listado_numeros_parte_muestra_exportar_con_filtros(self):
        request = self.factory.get(
            reverse('catalogos:numeros_parte_list'),
            {'q': 'sensor', 'modelo': 'MOD', 'fraccion': '9026'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet([])

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = numeros_parte_list(request)

        contenido = response.content.decode('utf-8')
        self.assertIn('Exportar CSV', contenido)
        self.assertIn(
            '/catalogos/numeros-parte/exportar/?q=sensor&amp;modelo=MOD&amp;fraccion=9026',
            contenido,
        )

    def test_exportar_numeros_parte_requiere_permiso_view(self):
        request = self.factory.get(reverse('catalogos:exportar_numeros_parte_csv'))
        request.user = _user(False)

        response = exportar_numeros_parte_csv(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_exportar_numeros_parte_respeta_filtros_y_descarga_csv(self):
        request = self.factory.get(
            reverse('catalogos:exportar_numeros_parte_csv'),
            {'q': 'ABC', 'modelo': 'MOD-2026', 'fraccion': '9026'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet(
            [
                SimpleNamespace(
                    numero_parte='ABC123',
                    modelo='MOD-2026',
                    descripcion='Sensor de temperatura',
                    fraccion='9026.10.01',
                    updated_at=None,
                ),
                SimpleNamespace(
                    numero_parte='XYZ999',
                    modelo='MOD-2025',
                    descripcion='Valvula',
                    fraccion='8481.80.99',
                    updated_at=None,
                ),
            ],
            filtered_items=[
                SimpleNamespace(
                    numero_parte='ABC123',
                    modelo='MOD-2026',
                    descripcion='Sensor de temperatura',
                    fraccion='9026.10.01',
                    updated_at=None,
                )
            ],
        )

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = exportar_numeros_parte_csv(request)

        contenido = response.content.decode('utf-8-sig')
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="numeros_parte_filtrado.csv"', response['Content-Disposition'])
        self.assertTrue(queryset.filter_called)
        self.assertIn('numero_parte,modelo,descripcion,fraccion,updated_at', contenido)
        self.assertIn('ABC123,MOD-2026,Sensor de temperatura,9026.10.01,', contenido)
        self.assertNotIn('XYZ999', contenido)

    def test_busqueda_sat_filtra_resultados(self):
        request = self.factory.get(reverse('catalogos:sat_list'), {'q': 'granja'})
        request.user = _user(True)
        queryset = FakeQuerySet(
            [
                SimpleNamespace(
                    clave='10101500',
                    descripcion='Animales vivos de granja',
                    incluir_iva_trasladado='Opcional',
                    incluir_ieps_trasladado='Opcional',
                    fecha_inicio_vigencia=None,
                    fecha_fin_vigencia=None,
                ),
                SimpleNamespace(
                    clave='10101600',
                    descripcion='Animales domesticos',
                    incluir_iva_trasladado='Opcional',
                    incluir_ieps_trasladado='Opcional',
                    fecha_inicio_vigencia=None,
                    fecha_fin_vigencia=None,
                ),
            ],
            filtered_items=[
                SimpleNamespace(
                    clave='10101500',
                    descripcion='Animales vivos de granja',
                    incluir_iva_trasladado='Opcional',
                    incluir_ieps_trasladado='Opcional',
                    fecha_inicio_vigencia=None,
                    fecha_fin_vigencia=None,
                )
            ],
        )

        with patch('apps.catalogos.views.ClaveProductoServicioSAT.objects', queryset):
            response = sat_list(request)

        contenido = response.content.decode('utf-8')
        self.assertTrue(queryset.filter_called)
        self.assertIn('10101500', contenido)
        self.assertNotIn('10101600', contenido)

    def test_filtros_sat_iva_ieps_y_vigente_son_combinables(self):
        request = self.factory.get(
            reverse('catalogos:sat_list'),
            {'q': 'granja', 'iva': 'Opcional', 'ieps': 'Opcional', 'vigente': '1'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet([
            SimpleNamespace(
                clave='10101500',
                descripcion='Animales vivos de granja',
                incluir_iva_trasladado='Opcional',
                incluir_ieps_trasladado='Opcional',
                fecha_inicio_vigencia=None,
                fecha_fin_vigencia=None,
            )
        ])

        with patch('apps.catalogos.views.ClaveProductoServicioSAT.objects', queryset):
            response = sat_list(request)

        contenido = response.content.decode('utf-8')
        self.assertTrue(queryset.filter_called)
        self.assertIn('value="granja"', contenido)
        self.assertIn('value="Opcional"', contenido)
        self.assertIn('value="1" selected', contenido)

    def test_paginacion_sat_preserva_filtros(self):
        request = self.factory.get(
            reverse('catalogos:sat_list'),
            {'q': 'granja', 'iva': 'Opcional', 'ieps': 'Opcional', 'vigente': '1'},
        )
        request.user = _user(True)
        items = [
            SimpleNamespace(
                clave=f'101015{indice:02d}',
                descripcion='Animales vivos de granja',
                incluir_iva_trasladado='Opcional',
                incluir_ieps_trasladado='Opcional',
                fecha_inicio_vigencia=None,
                fecha_fin_vigencia=None,
            )
            for indice in range(30)
        ]
        queryset = FakeQuerySet(items, filtered_items=items)

        with patch('apps.catalogos.views.ClaveProductoServicioSAT.objects', queryset):
            response = sat_list(request)

        contenido = response.content.decode('utf-8')
        self.assertIn(
            'q=granja&amp;iva=Opcional&amp;ieps=Opcional&amp;vigente=1&page=2',
            contenido,
        )

    def test_listado_sat_muestra_exportar_con_filtros(self):
        request = self.factory.get(
            reverse('catalogos:sat_list'),
            {'q': 'granja', 'iva': 'Opcional', 'ieps': 'Opcional', 'vigente': '1'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet([])

        with patch('apps.catalogos.views.ClaveProductoServicioSAT.objects', queryset):
            response = sat_list(request)

        contenido = response.content.decode('utf-8')
        self.assertIn('Exportar CSV', contenido)
        self.assertIn(
            '/catalogos/sat/exportar/?q=granja&amp;iva=Opcional&amp;ieps=Opcional&amp;vigente=1',
            contenido,
        )

    def test_exportar_sat_requiere_permiso_view(self):
        request = self.factory.get(reverse('catalogos:exportar_sat_csv'))
        request.user = _user(False)

        response = exportar_sat_csv(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_exportar_sat_respeta_filtros_y_descarga_csv(self):
        request = self.factory.get(
            reverse('catalogos:exportar_sat_csv'),
            {'q': 'granja', 'iva': 'Opcional', 'ieps': 'Opcional', 'vigente': '1'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet(
            [
                SimpleNamespace(
                    clave='10101500',
                    descripcion='Animales vivos de granja',
                    incluir_iva_trasladado='Opcional',
                    incluir_ieps_trasladado='Opcional',
                    complemento_que_debe_incluir='',
                    fecha_inicio_vigencia=None,
                    fecha_fin_vigencia=None,
                    estimulo_franja_fronteriza='1',
                    palabras_similares='Publico en general',
                    updated_at=None,
                ),
                SimpleNamespace(
                    clave='10101600',
                    descripcion='Animales domesticos',
                    incluir_iva_trasladado='Opcional',
                    incluir_ieps_trasladado='Opcional',
                    complemento_que_debe_incluir='',
                    fecha_inicio_vigencia=None,
                    fecha_fin_vigencia=None,
                    estimulo_franja_fronteriza='1',
                    palabras_similares='Mascotas',
                    updated_at=None,
                ),
            ],
            filtered_items=[
                SimpleNamespace(
                    clave='10101500',
                    descripcion='Animales vivos de granja',
                    incluir_iva_trasladado='Opcional',
                    incluir_ieps_trasladado='Opcional',
                    complemento_que_debe_incluir='',
                    fecha_inicio_vigencia=None,
                    fecha_fin_vigencia=None,
                    estimulo_franja_fronteriza='1',
                    palabras_similares='Publico en general',
                    updated_at=None,
                )
            ],
        )

        with patch('apps.catalogos.views.ClaveProductoServicioSAT.objects', queryset):
            response = exportar_sat_csv(request)

        contenido = response.content.decode('utf-8-sig')
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="catalogo_sat_filtrado.csv"', response['Content-Disposition'])
        self.assertTrue(queryset.filter_called)
        self.assertIn('clave,descripcion,incluir_iva_trasladado', contenido)
        self.assertIn('10101500,Animales vivos de granja,Opcional,Opcional', contenido)
        self.assertNotIn('10101600', contenido)

    def test_importar_numeros_parte_genera_preview_sin_crear_carga(self):
        archivo = SimpleUploadedFile('partes.csv', b'ABC123,,Sensor,\n', content_type='text/csv')
        request = self.factory.post(
            reverse('catalogos:importar_numeros_parte'),
            {'archivo': archivo},
        )
        request.user = _user(True)
        request.session = {}
        preview = {
            'archivo_nombre': 'partes.csv',
            'filas_validas': 1,
            'crearian': 1,
            'actualizarian': 0,
            'errores': [],
            'muestra': [],
            'filas': [
                {
                    'fila': 1,
                    'numero_parte': 'ABC123',
                    'modelo': '',
                    'descripcion': 'Sensor',
                    'fraccion': '',
                }
            ],
        }

        with (
            patch('apps.catalogos.views.analizar_numeros_parte_csv', return_value=preview),
            patch('apps.catalogos.views.CargaCatalogo.objects') as manager,
        ):
            response = importar_numeros_parte(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(PREVIEW_NUMEROS_PARTE_SESSION_KEY, request.session)
        manager.create.assert_not_called()

    def test_confirmar_importar_numeros_parte_crea_registro_carga(self):
        request = self.factory.post(
            reverse('catalogos:importar_numeros_parte'),
            {'accion': 'confirmar'},
        )
        request.user = _user(True)
        request.session = {
            PREVIEW_NUMEROS_PARTE_SESSION_KEY: {
                'archivo_nombre': 'partes.csv',
                'errores': [],
                'filas': [
                    {
                        'fila': 1,
                        'numero_parte': 'ABC123',
                        'modelo': '',
                        'descripcion': 'Sensor',
                        'fraccion': '',
                    }
                ],
            }
        }
        resultado = {'procesadas': 1, 'creadas': 1, 'actualizadas': 0, 'errores': []}

        with (
            patch('apps.catalogos.views.guardar_numeros_parte_desde_filas', return_value=resultado),
            patch('apps.catalogos.views.CargaCatalogo.objects') as manager,
            patch('apps.catalogos.views._agregar_mensaje_resultado'),
        ):
            response = importar_numeros_parte(request)

        self.assertEqual(response.status_code, 200)
        manager.create.assert_called_once()
        self.assertEqual(
            manager.create.call_args.kwargs['tipo_catalogo'],
            CargaCatalogo.TIPO_NUMEROS_PARTE,
        )
        self.assertEqual(manager.create.call_args.kwargs['archivo_nombre'], 'partes.csv')
        self.assertNotIn(PREVIEW_NUMEROS_PARTE_SESSION_KEY, request.session)

    def test_cancelar_importar_numeros_parte_limpia_session(self):
        request = self.factory.post(
            reverse('catalogos:importar_numeros_parte'),
            {'accion': 'cancelar'},
        )
        request.user = _user(True)
        request.session = {PREVIEW_NUMEROS_PARTE_SESSION_KEY: {'filas': []}}

        with patch('apps.catalogos.views.messages.success'):
            response = importar_numeros_parte(request)

        self.assertEqual(response.status_code, 302)
        self.assertNotIn(PREVIEW_NUMEROS_PARTE_SESSION_KEY, request.session)

    def test_confirmar_sin_preview_muestra_error_controlado(self):
        request = self.factory.post(
            reverse('catalogos:importar_numeros_parte'),
            {'accion': 'confirmar'},
        )
        request.user = _user(True)
        request.session = {}

        with patch('apps.catalogos.views.messages.error') as mensaje_error:
            response = importar_numeros_parte(request)

        self.assertEqual(response.status_code, 302)
        mensaje_error.assert_called_once()

    def test_usuario_sin_permiso_no_puede_importar_numeros_parte(self):
        request = self.factory.get(reverse('catalogos:importar_numeros_parte'))
        request.user = _user(False)

        response = importar_numeros_parte(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_importar_sat_crea_registro_carga(self):
        archivo = SimpleUploadedFile('sat.csv', b'10101500,Animales\n', content_type='text/csv')
        request = self.factory.post(
            reverse('catalogos:importar_sat'),
            {'archivo': archivo},
        )
        request.user = _user(True)
        resultado = {'procesadas': 1, 'creadas': 1, 'actualizadas': 0, 'errores': []}

        with (
            patch('apps.catalogos.views.importar_claves_sat_csv', return_value=resultado),
            patch('apps.catalogos.views.CargaCatalogo.objects') as manager,
            patch('apps.catalogos.views._agregar_mensaje_resultado'),
        ):
            response = importar_sat(request)

        self.assertEqual(response.status_code, 200)
        manager.create.assert_called_once()
        self.assertEqual(
            manager.create.call_args.kwargs['tipo_catalogo'],
            CargaCatalogo.TIPO_SAT_CLAVE_PRODUCTO_SERVICIO,
        )
        self.assertEqual(manager.create.call_args.kwargs['archivo_nombre'], 'sat.csv')

    def test_usuario_sin_permiso_no_puede_importar_sat(self):
        request = self.factory.get(reverse('catalogos:importar_sat'))
        request.user = _user(False)

        response = importar_sat(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_carga_con_errores_queda_estado_con_errores(self):
        archivo = SimpleNamespace(name='partes.csv')
        resultado = {
            'procesadas': 1,
            'creadas': 0,
            'actualizadas': 0,
            'errores': [{'fila': 1, 'error': 'descripcion es requerida.'}],
        }

        with patch('apps.catalogos.views.CargaCatalogo.objects') as manager:
            _registrar_carga_catalogo(
                CargaCatalogo.TIPO_NUMEROS_PARTE,
                archivo,
                SimpleNamespace(is_authenticated=False),
                resultado,
            )

        self.assertEqual(manager.create.call_args.kwargs['estado'], CargaCatalogo.ESTADO_CON_ERRORES)
        self.assertIn('descripcion', manager.create.call_args.kwargs['errores_resumen'])

    def test_listado_cargas_requiere_login(self):
        response = self.client.get(reverse('catalogos:cargas_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_usuario_sin_permiso_no_puede_ver_historial(self):
        request = self.factory.get(reverse('catalogos:cargas_list'))
        request.user = _user(False)

        response = cargas_list(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_listado_cargas_responde_con_usuario_autenticado(self):
        request = self.factory.get(reverse('catalogos:cargas_list'))
        request.user = _user(True)
        queryset = FakeQuerySet([
            SimpleNamespace(
                created_at=None,
                tipo_catalogo='numeros_parte',
                archivo_nombre='partes.csv',
                usuario=None,
                total_procesadas=1,
                total_creadas=1,
                total_actualizadas=0,
                total_errores=0,
                estado='exitosa',
            )
        ])

        with patch('apps.catalogos.views.CargaCatalogo.objects', queryset):
            response = cargas_list(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn('partes.csv', response.content.decode('utf-8'))

    def test_filtros_cargas_fecha_desde_y_hasta_son_combinables(self):
        request = self.factory.get(
            reverse('catalogos:cargas_list'),
            {
                'q': 'partes',
                'fecha_desde': '2026-01-01',
                'fecha_hasta': '2026-01-31',
            },
        )
        request.user = _user(True)
        queryset = FakeQuerySet([
            SimpleNamespace(
                created_at=None,
                tipo_catalogo='numeros_parte',
                archivo_nombre='partes.csv',
                usuario=None,
                total_procesadas=1,
                total_creadas=1,
                total_actualizadas=0,
                total_errores=0,
                estado='exitosa',
            )
        ])

        with patch('apps.catalogos.views.CargaCatalogo.objects', queryset):
            response = cargas_list(request)

        contenido = response.content.decode('utf-8')
        self.assertTrue(queryset.filter_called)
        self.assertIn('value="partes"', contenido)
        self.assertIn('value="2026-01-01"', contenido)
        self.assertIn('value="2026-01-31"', contenido)

    def test_filtros_cargas_fecha_invalida_no_truena(self):
        request = self.factory.get(
            reverse('catalogos:cargas_list'),
            {'fecha_desde': 'fecha-invalida'},
        )
        request.user = _user(True)
        queryset = FakeQuerySet([])

        with patch('apps.catalogos.views.CargaCatalogo.objects', queryset):
            response = cargas_list(request)

        contenido = response.content.decode('utf-8')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Formato de fecha invalido', contenido)
        self.assertIn('value="fecha-invalida"', contenido)

    def test_paginacion_cargas_preserva_filtros_de_fecha(self):
        request = self.factory.get(
            reverse('catalogos:cargas_list'),
            {
                'q': 'partes',
                'fecha_desde': '2026-01-01',
                'fecha_hasta': '2026-01-31',
            },
        )
        request.user = _user(True)
        items = [
            SimpleNamespace(
                created_at=None,
                tipo_catalogo='numeros_parte',
                archivo_nombre=f'partes-{indice}.csv',
                usuario=None,
                total_procesadas=1,
                total_creadas=1,
                total_actualizadas=0,
                total_errores=0,
                estado='exitosa',
            )
            for indice in range(30)
        ]
        queryset = FakeQuerySet(items, filtered_items=items)

        with patch('apps.catalogos.views.CargaCatalogo.objects', queryset):
            response = cargas_list(request)

        contenido = response.content.decode('utf-8')
        self.assertIn(
            'q=partes&amp;fecha_desde=2026-01-01&amp;fecha_hasta=2026-01-31&page=2',
            contenido,
        )

    def test_listado_cargas_muestra_exportar_con_filtros(self):
        request = self.factory.get(
            reverse('catalogos:cargas_list'),
            {
                'q': 'partes',
                'fecha_desde': '2026-01-01',
                'fecha_hasta': '2026-01-31',
            },
        )
        request.user = _user(True)
        queryset = FakeQuerySet([])

        with patch('apps.catalogos.views.CargaCatalogo.objects', queryset):
            response = cargas_list(request)

        contenido = response.content.decode('utf-8')
        self.assertIn('Exportar CSV', contenido)
        self.assertIn(
            '/catalogos/cargas/exportar/?q=partes&amp;fecha_desde=2026-01-01&amp;fecha_hasta=2026-01-31',
            contenido,
        )

    def test_exportar_cargas_requiere_permiso_historial(self):
        request = self.factory.get(reverse('catalogos:exportar_cargas_csv'))
        request.user = _user(False)

        response = exportar_cargas_csv(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_exportar_cargas_respeta_filtros_y_descarga_csv(self):
        request = self.factory.get(
            reverse('catalogos:exportar_cargas_csv'),
            {
                'q': 'partes',
                'archivo': 'partes',
                'tipo_catalogo': 'numeros',
                'estado': 'exitosa',
                'fecha_desde': '2026-01-01',
                'fecha_hasta': '2026-01-31',
            },
        )
        request.user = _user(True)
        queryset = FakeQuerySet(
            [
                SimpleNamespace(
                    created_at=None,
                    tipo_catalogo='numeros_parte',
                    archivo_nombre='partes.csv',
                    usuario='operador',
                    total_procesadas=1,
                    total_creadas=1,
                    total_actualizadas=0,
                    total_errores=0,
                    estado='exitosa',
                    errores_resumen='',
                ),
                SimpleNamespace(
                    created_at=None,
                    tipo_catalogo='sat_clave_producto_servicio',
                    archivo_nombre='sat.csv',
                    usuario='operador',
                    total_procesadas=1,
                    total_creadas=1,
                    total_actualizadas=0,
                    total_errores=0,
                    estado='exitosa',
                    errores_resumen='',
                ),
            ],
            filtered_items=[
                SimpleNamespace(
                    created_at=None,
                    tipo_catalogo='numeros_parte',
                    archivo_nombre='partes.csv',
                    usuario='operador',
                    total_procesadas=1,
                    total_creadas=1,
                    total_actualizadas=0,
                    total_errores=0,
                    estado='exitosa',
                    errores_resumen='',
                )
            ],
        )

        with patch('apps.catalogos.views.CargaCatalogo.objects', queryset):
            response = exportar_cargas_csv(request)

        contenido = response.content.decode('utf-8-sig')
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'filename="historial_cargas_catalogos_filtrado.csv"',
            response['Content-Disposition'],
        )
        self.assertTrue(queryset.filter_called)
        self.assertIn('created_at,tipo_catalogo,archivo_nombre,usuario', contenido)
        self.assertIn('numeros_parte,partes.csv,operador,1,1,0,0,exitosa', contenido)
        self.assertNotIn('sat.csv', contenido)

    def test_superusuario_puede_acceder_a_catalogos(self):
        request = self.factory.get(reverse('catalogos:numeros_parte_list'))
        request.user = _user(False, superusuario=True)
        queryset = FakeQuerySet([
            SimpleNamespace(
                pk=1,
                numero_parte='ABC123',
                modelo='MOD-2026',
                descripcion='Sensor de temperatura',
                fraccion='9026.10.01',
                updated_at=None,
            )
        ])

        with patch('apps.catalogos.views.NumeroParte.objects', queryset):
            response = numeros_parte_list(request)

        self.assertEqual(response.status_code, 200)

    def test_usuario_sin_permisos_no_ve_enlaces_de_catalogos(self):
        request = self.factory.get(reverse('home'))
        response = _render_base_con_usuario(request, _user(False))

        contenido = response.content.decode('utf-8')
        self.assertIn('Inicio', contenido)
        self.assertNotIn('Numeros de parte</a>', contenido)
        self.assertNotIn('Importar numeros de parte', contenido)
        self.assertNotIn('Claves SAT', contenido)
        self.assertNotIn('Importar claves SAT', contenido)
        self.assertNotIn('Historial de cargas', contenido)

    def test_usuario_con_permiso_numeros_parte_ve_enlace_correspondiente(self):
        request = self.factory.get(reverse('home'))
        response = _render_base_con_usuario(
            request,
            _user(False, permisos={'catalogos.view_numeroparte'}),
        )

        contenido = response.content.decode('utf-8')
        self.assertIn('Numeros de parte', contenido)
        self.assertNotIn('Claves SAT', contenido)

    def test_usuario_con_permiso_sat_ve_enlace_correspondiente(self):
        request = self.factory.get(reverse('home'))
        response = _render_base_con_usuario(
            request,
            _user(False, permisos={'catalogos.view_claveproductoserviciosat'}),
        )

        contenido = response.content.decode('utf-8')
        self.assertIn('Claves SAT', contenido)
        self.assertNotIn('Numeros de parte</a>', contenido)

    def test_usuario_con_permiso_historial_ve_enlace_correspondiente(self):
        request = self.factory.get(reverse('home'))
        response = _render_base_con_usuario(
            request,
            _user(False, permisos={'catalogos.puede_ver_historial_cargas_catalogo'}),
        )

        contenido = response.content.decode('utf-8')
        self.assertIn('Historial de cargas', contenido)
        self.assertNotIn('Numeros de parte</a>', contenido)
        self.assertNotIn('Claves SAT', contenido)

    def test_superusuario_ve_todos_los_enlaces_de_catalogos(self):
        request = self.factory.get(reverse('home'))
        response = _render_base_con_usuario(request, _user(False, superusuario=True))

        contenido = response.content.decode('utf-8')
        self.assertIn('Numeros de parte', contenido)
        self.assertIn('Importar numeros de parte', contenido)
        self.assertIn('Claves SAT', contenido)
        self.assertIn('Importar claves SAT', contenido)
        self.assertIn('Historial de cargas', contenido)

    def test_plantilla_numeros_parte_requiere_login(self):
        response = self.client.get(reverse('catalogos:plantilla_numeros_parte'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_plantilla_sat_requiere_login(self):
        response = self.client.get(reverse('catalogos:plantilla_sat'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_usuario_autenticado_descarga_plantilla_numeros_parte(self):
        request = self.factory.get(reverse('catalogos:plantilla_numeros_parte'))
        request.user = _user(True)

        response = descargar_plantilla_numeros_parte(request)
        contenido = response.content.decode('utf-8-sig')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'filename="plantilla_numeros_parte.csv"',
            response['Content-Disposition'],
        )
        self.assertIn('numero de parte,MODELO,descripcion,fracción', contenido)

    def test_usuario_autenticado_descarga_plantilla_sat(self):
        request = self.factory.get(reverse('catalogos:plantilla_sat'))
        request.user = _user(True)

        response = descargar_plantilla_sat(request)
        contenido = response.content.decode('utf-8-sig')

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'filename="plantilla_sat_claves_producto_servicio.csv"',
            response['Content-Disposition'],
        )
        self.assertIn('c_ClaveProdServ,Descripción,Incluir IVA trasladado', contenido)
