from django.contrib.gis import admin
from .models import Article, ArticleImage, ArticleCategory
from reversion.admin import VersionAdmin
from django.contrib.admin import ModelAdmin

from django import forms


class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=forms.Textarea, required=False)
    category = forms.ModelMultipleChoiceField(queryset=ArticleCategory.objects.all(),widget=forms.CheckboxSelectMultiple)

    class Media:
        extend=False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'articles/js/init.js')


class ArticleAdmin(VersionAdmin):
    form = ArticleForm
    model = Article
    list_display = ('title', 'updated_at', 'created_at', 'created_by')
    search_fields = ['title']

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)


class ArticleImageAdmin(ModelAdmin):
    fields = ['image_tag', 'height', 'width']
    readonly_fields = ['image_tag', 'height', 'width']


admin.site.register(Article, ArticleAdmin)
admin.site.register(ArticleImage, ArticleImageAdmin)
admin.site.register(ArticleCategory)
