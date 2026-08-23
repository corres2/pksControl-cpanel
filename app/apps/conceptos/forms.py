from django import forms

from apps.conceptos.models import Concepto, DocumentoConceptos


class DocumentoConceptosForm(forms.ModelForm):
    class Meta:
        model = DocumentoConceptos
        fields = ('observaciones',)
        labels = {'observaciones': 'Observaciones'}


class ConceptoForm(forms.ModelForm):
    def __init__(self, *args, documento=None, **kwargs):
        self.documento = documento
        super().__init__(*args, **kwargs)
        if not self.is_bound and not (self.instance and self.instance.pk):
            self.fields['cantidad'].initial = '1'
            self.fields['precio_unitario'].initial = '0'

    class Meta:
        model = Concepto
        fields = (
            'numero_parte',
            'serie',
            'modelo',
            'descripcion',
            'cantidad',
            'precio_unitario',
            'orden',
        )
        labels = {
            'numero_parte': 'Número de parte',
            'serie': 'Serie',
            'modelo': 'Modelo',
            'descripcion': 'Descripción',
            'cantidad': 'Cantidad',
            'precio_unitario': 'Precio unitario',
            'orden': 'Orden',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_serie(self):
        serie = (self.cleaned_data.get('serie') or '').strip()
        if not serie or not self.documento:
            return serie

        serie_normalizada = serie.upper()
        conceptos = Concepto.objects.filter(documento=self.documento).exclude(serie='')
        if self.instance and self.instance.pk:
            conceptos = conceptos.exclude(pk=self.instance.pk)

        for serie_existente in conceptos.values_list('serie', flat=True):
            if serie_existente.strip().upper() == serie_normalizada:
                raise forms.ValidationError('La serie ya existe en este documento.')

        return serie
