from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.core.views import home, system_status


def _user(con_permiso=True, superusuario=False, permisos=None):
    permisos = permisos or set()

    def has_perm(permiso):
        return con_permiso or superusuario or permiso in permisos

    return SimpleNamespace(
        is_authenticated=True,
        is_superuser=superusuario,
        has_perm=has_perm,
        get_username=lambda: 'usuario.prueba',
    )


class HomeDashboardTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _render_home(self, usuario):
        request = self.factory.get(reverse('home'))
        request.user = usuario
        return home(request)

    def test_home_requires_login(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_authenticated_user_can_view_home(self):
        response = self._render_home(_user(False))

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8')
        self.assertIn('Panel de inicio', contenido)
        self.assertIn('Bienvenido, usuario.prueba.', contenido)

    def test_usuario_sin_permisos_ve_estado_pero_no_catalogos(self):
        response = self._render_home(_user(False))
        contenido = response.content.decode('utf-8')

        self.assertIn('Estado del sistema', contenido)
        self.assertNotIn('Numeros de parte', contenido)
        self.assertNotIn('Importar numeros de parte', contenido)
        self.assertNotIn('Claves SAT', contenido)
        self.assertNotIn('Importar claves SAT', contenido)
        self.assertNotIn('Historial de cargas', contenido)

    def test_usuario_con_permiso_view_numeroparte_ve_acceso(self):
        response = self._render_home(
            _user(False, permisos={'catalogos.view_numeroparte'})
        )

        self.assertContains(response, 'Numeros de parte')

    def test_usuario_con_permiso_add_numeroparte_ve_acceso(self):
        response = self._render_home(
            _user(False, permisos={'catalogos.add_numeroparte'})
        )

        self.assertContains(response, 'Nuevo numero de parte')

    def test_usuario_con_permiso_importar_numeroparte_ve_acceso(self):
        response = self._render_home(
            _user(False, permisos={'catalogos.puede_importar_numeroparte'})
        )

        self.assertContains(response, 'Importar numeros de parte')

    def test_usuario_con_permiso_view_sat_ve_acceso(self):
        response = self._render_home(
            _user(False, permisos={'catalogos.view_claveproductoserviciosat'})
        )

        self.assertContains(response, 'Claves SAT')

    def test_usuario_con_permiso_importar_sat_ve_acceso(self):
        response = self._render_home(
            _user(False, permisos={'catalogos.puede_importar_claves_sat'})
        )

        self.assertContains(response, 'Importar claves SAT')

    def test_usuario_con_permiso_historial_ve_acceso(self):
        response = self._render_home(
            _user(False, permisos={'catalogos.puede_ver_historial_cargas_catalogo'})
        )

        self.assertContains(response, 'Historial de cargas')

    def test_superusuario_ve_todos_los_accesos(self):
        response = self._render_home(_user(False, superusuario=True))
        contenido = response.content.decode('utf-8')

        self.assertIn('Estado del sistema', contenido)
        self.assertIn('Numeros de parte', contenido)
        self.assertIn('Importar numeros de parte', contenido)
        self.assertIn('Claves SAT', contenido)
        self.assertIn('Importar claves SAT', contenido)
        self.assertIn('Historial de cargas', contenido)


class SystemStatusViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_status_requires_login(self):
        response = self.client.get(reverse('system_status'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response['Location'])

    def test_login_page_responds_ok(self):
        response = self.client.get(reverse('login'))

        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_can_view_status(self):
        request = self.factory.get(reverse('system_status'))
        request.user = _user(True)

        with (
            patch('apps.core.views._get_database_status', return_value='OK'),
            patch('apps.core.views._get_latest_installation_status', return_value=None),
            patch('apps.core.views._get_git_commit', return_value='No disponible'),
        ):
            response = system_status(request)

        self.assertEqual(response.status_code, 200)
        contenido = response.content.decode('utf-8')
        self.assertIn('Estado del sistema', contenido)
        self.assertIn('Numeros de parte', contenido)
        self.assertIn('Cerrar sesion', contenido)

    def test_logout_post_redirects_to_login(self):
        response = self.client.post(reverse('logout'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/accounts/login/')
