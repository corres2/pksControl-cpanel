from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse

from apps.administracion.permisos import GRUPO_ADMINISTRADORES, es_administrador
from apps.conceptos.models import PatronSerie

CLAVE = 'Clave-segura-2026'


class AdministracionBaseTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.grupo = Group.objects.get(name=GRUPO_ADMINISTRADORES)
        self.admin = User.objects.create_user(username='admin.grupo', password=CLAVE)
        self.admin.groups.add(self.grupo)
        self.operador = User.objects.create_user(username='operador', password=CLAVE)


class PermisosAdministradorTests(AdministracionBaseTests):
    def test_migracion_crea_grupo_administradores(self):
        self.assertTrue(Group.objects.filter(name=GRUPO_ADMINISTRADORES).exists())

    def test_es_administrador_por_grupo_o_superusuario(self):
        superusuario = get_user_model().objects.create_superuser(username='root', password=CLAVE)

        self.assertTrue(es_administrador(self.admin))
        self.assertTrue(es_administrador(superusuario))
        self.assertFalse(es_administrador(self.operador))

    def test_operador_no_entra_a_modulos_de_administracion(self):
        self.client.force_login(self.operador)
        urls = [
            reverse('administracion:usuarios_list'),
            reverse('administracion:usuario_create'),
            reverse('administracion:exportaciones'),
            reverse('administracion:exportar_tabla', args=['patrones', 'csv']),
            reverse('system_status'),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonimo_va_al_login(self):
        response = self.client.get(reverse('administracion:usuarios_list'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_administrador_ve_estado_y_menu(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('system_status'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usuarios y permisos')
        self.assertContains(response, 'Descargar tablas')

    def test_operador_no_ve_menu_de_administracion(self):
        self.client.force_login(self.operador)

        response = self.client.get(reverse('home'))

        self.assertNotContains(response, 'Usuarios y permisos')
        self.assertNotContains(response, 'Estado del sistema')


class UsuariosTests(AdministracionBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        self.permiso = Permission.objects.get(codename='view_numeroparte')

    def _datos(self, **extra):
        datos = {
            'username': 'nuevo.usuario',
            'first_name': 'Nuevo',
            'last_name': 'Usuario',
            'email': 'nuevo@example.com',
            'is_active': 'on',
            'password1': CLAVE,
            'password2': CLAVE,
            'permisos': [self.permiso.pk],
        }
        datos.update(extra)
        return {clave: valor for clave, valor in datos.items() if valor is not None}

    def test_lista_usuarios_con_busqueda(self):
        response = self.client.get(reverse('administracion:usuarios_list'), {'q': 'oper'})

        self.assertContains(response, '<td>operador</td>', html=False)
        self.assertNotContains(response, '<td>admin.grupo</td>', html=False)

    def test_crea_usuario_con_permisos(self):
        response = self.client.post(reverse('administracion:usuario_create'), self._datos())

        self.assertRedirects(response, reverse('administracion:usuarios_list'))
        usuario = get_user_model().objects.get(username='nuevo.usuario')
        self.assertTrue(usuario.check_password(CLAVE))
        self.assertTrue(usuario.has_perm('catalogos.view_numeroparte'))
        self.assertFalse(es_administrador(usuario))

    def test_crea_usuario_administrador(self):
        self.client.post(reverse('administracion:usuario_create'), self._datos(es_administrador='on'))

        self.assertTrue(es_administrador(get_user_model().objects.get(username='nuevo.usuario')))

    def test_crear_exige_contrasenas_iguales(self):
        response = self.client.post(
            reverse('administracion:usuario_create'),
            self._datos(password2='Otra-clave-2026'),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Las contraseñas no coinciden.')
        self.assertFalse(get_user_model().objects.filter(username='nuevo.usuario').exists())

    def test_editar_sin_contrasena_conserva_la_actual_y_cambia_permisos(self):
        url = reverse('administracion:usuario_update', args=[self.operador.pk])

        response = self.client.post(
            url,
            self._datos(username='operador', password1='', password2='', es_administrador='on'),
        )

        self.assertRedirects(response, reverse('administracion:usuarios_list'))
        self.operador.refresh_from_db()
        self.assertTrue(self.operador.check_password(CLAVE))
        self.assertTrue(es_administrador(self.operador))
        self.assertTrue(self.operador.user_permissions.filter(pk=self.permiso.pk).exists())

    def test_administrador_no_puede_quitarse_el_rol_ni_desactivarse(self):
        url = reverse('administracion:usuario_update', args=[self.admin.pk])

        response = self.client.post(
            url,
            self._datos(username='admin.grupo', password1='', password2='', is_active=None),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'No puedes desactivar tu propio usuario.')
        self.assertContains(response, 'No puedes quitarte el rol de administrador.')
        self.assertTrue(es_administrador(self.admin))


class ExportacionesTests(AdministracionBaseTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)
        PatronSerie.objects.create(prefix='ABC00', numero_parte='NP-001', firma_json={'modelo': 'M'})

    def test_lista_tablas(self):
        response = self.client.get(reverse('administracion:exportaciones'))

        self.assertContains(response, 'Biblioteca de patrones de serie')

    def test_exporta_csv(self):
        response = self.client.get(reverse('administracion:exportar_tabla', args=['patrones', 'csv']))

        contenido = b''.join(response.streaming_content).decode('utf-8-sig')
        self.assertIn('prefix', contenido.splitlines()[0])
        self.assertIn('ABC00', contenido)
        self.assertIn('attachment', response['Content-Disposition'])

    def test_exporta_xlsx(self):
        from openpyxl import load_workbook

        response = self.client.get(reverse('administracion:exportar_tabla', args=['patrones', 'xlsx']))

        filas = list(load_workbook(BytesIO(response.content)).active.values)
        self.assertIn('prefix', filas[0])
        self.assertIn('ABC00', filas[1])

    def test_tabla_o_formato_desconocido_da_404(self):
        for clave, formato in (('usuarios', 'csv'), ('patrones', 'pdf')):
            with self.subTest(clave=clave, formato=formato):
                url = reverse('administracion:exportar_tabla', args=[clave, formato])
                self.assertEqual(self.client.get(url).status_code, 404)
