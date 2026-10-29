from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.models import Group, Permission

from apps.administracion.permisos import GRUPO_ADMINISTRADORES

APPS_CON_PERMISOS = ('catalogos', 'conceptos')


class PermisoChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, permiso):
        return f'{permiso.content_type.app_label.capitalize()} · {permiso.name}'


class UsuarioForm(forms.ModelForm):
    es_administrador = forms.BooleanField(
        label='Administrador',
        required=False,
        help_text='Acceso a usuarios, estado del sistema y descarga de tablas.',
    )
    permisos = PermisoChoiceField(
        label='Permisos',
        queryset=Permission.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    password1 = forms.CharField(label='Contraseña', required=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirmar contraseña', required=False, widget=forms.PasswordInput)

    class Meta:
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active')
        labels = {
            'username': 'Usuario',
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo',
            'is_active': 'Activo',
        }

    def __init__(self, *args, editor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        self.fields['permisos'].queryset = Permission.objects.filter(
            content_type__app_label__in=APPS_CON_PERMISOS,
        ).select_related('content_type').order_by('content_type__app_label', 'content_type__model', 'codename')
        if self.instance.pk:
            self.fields['es_administrador'].initial = self.instance.groups.filter(
                name=GRUPO_ADMINISTRADORES,
            ).exists()
            self.fields['permisos'].initial = self.instance.user_permissions.all()
            self.fields['password1'].help_text = 'Déjala vacía para conservar la actual.'
        else:
            self.fields['password1'].required = True
            self.fields['password2'].required = True

    def _es_el_editor(self):
        return self.editor is not None and self.instance.pk == self.editor.pk

    def clean(self):
        datos = super().clean()
        password1 = datos.get('password1')
        password2 = datos.get('password2')
        if password1 or password2:
            if password1 != password2:
                self.add_error('password2', 'Las contraseñas no coinciden.')
            else:
                try:
                    password_validation.validate_password(password1, self.instance)
                except forms.ValidationError as error:
                    self.add_error('password1', error)
        if self._es_el_editor():
            if not datos.get('is_active'):
                self.add_error('is_active', 'No puedes desactivar tu propio usuario.')
            if not datos.get('es_administrador') and not self.instance.is_superuser:
                self.add_error('es_administrador', 'No puedes quitarte el rol de administrador.')
        return datos

    def save(self, commit=True):
        usuario = super().save(commit=False)
        if self.cleaned_data.get('password1'):
            usuario.set_password(self.cleaned_data['password1'])
        usuario.save()
        grupo, _creado = Group.objects.get_or_create(name=GRUPO_ADMINISTRADORES)
        if self.cleaned_data.get('es_administrador'):
            usuario.groups.add(grupo)
        else:
            usuario.groups.remove(grupo)
        permisos_fuera_de_alcance = usuario.user_permissions.exclude(content_type__app_label__in=APPS_CON_PERMISOS)
        usuario.user_permissions.set([*permisos_fuera_de_alcance, *self.cleaned_data.get('permisos', [])])
        return usuario
