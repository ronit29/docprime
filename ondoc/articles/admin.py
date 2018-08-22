from django.contrib.gis import admin
from .models import Article, ArticleImage, ArticleCategory
from reversion.admin import VersionAdmin
from django.contrib.admin import ModelAdmin
from django.utils.safestring import mark_safe
from django import forms
from django.conf import settings


class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=forms.Textarea, required=False)
    category = forms.ModelChoiceField(queryset=ArticleCategory.objects.all(),widget=forms.Select)

    class Media:
        extend=False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'articles/js/init.js')
        css = {'all':('articles/css/style.css',)}


# class ArticleCategoryInline(admin.TabularInline):
#     model = Article.category.through


class ArticleAdmin(VersionAdmin):
    form = ArticleForm
    model = Article
    list_display = ('title', 'updated_at', 'created_at', 'created_by')
    search_fields = ['title']
    fields = ['title', 'body', 'header_image', 'category', 'url', 'description', 'keywords', 'icon_tag', 'icon', 'is_published', 'preview']
    readonly_fields = ['icon_tag', 'preview']
    #inlines = [ArticleCategoryInline]

    def preview(self, instance):
        if instance.id:
            app_url = settings.CONSUMER_APP_DOMAIN
            if app_url:
                html = '''<a href='%s/article/%s?preview=1' target=_blank>Preview</a>''' % (app_url, instance.id)
                return mark_safe(html)
        else:
            return mark_safe('''<span></span>''')

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
