from django import forms

class CustomImageWidget(forms.Select):
    template_name = 'imagewidget.html'

    # def render(self, name, value, attrs=None):
         # super().render(name, value, attrs)
