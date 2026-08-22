from pathlib import Path

from django import forms

from apps.catalogos.models import NumeroParte


class CSVUploadForm(forms.Form):
    archivo = forms.FileField(label='Archivo CSV o XLSX')

    def clean_archivo(self):
        archivo = self.cleaned_data['archivo']
        extension = Path(archivo.name).suffix.lower()
        if extension not in {'.csv', '.xlsx'}:
            raise forms.ValidationError('Solo se permiten archivos .csv o .xlsx.')
        return archivo


class NumeroParteForm(forms.ModelForm):
    class Meta:
        model = NumeroParte
        fields = ('numero_parte', 'modelo', 'descripcion', 'fraccion')
        labels = {
            'numero_parte': 'Numero de parte',
            'modelo': 'Modelo',
            'descripcion': 'Descripcion',
            'fraccion': 'Fraccion',
        }

    def clean_numero_parte(self):
        numero_parte = self.cleaned_data['numero_parte'].strip()
        existe = NumeroParte.objects.filter(numero_parte=numero_parte)

        if self.instance.pk:
            existe = existe.exclude(pk=self.instance.pk)

        if existe.exists():
            raise forms.ValidationError('Ya existe un numero de parte con ese valor.')

        return numero_parte
