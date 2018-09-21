import nested_admin
from django.contrib.gis import admin
from .models import Article, ArticleImage, ArticleCategory, ArticleLinkedUrl, LinkedArticle
from reversion.admin import VersionAdmin
from django.contrib.admin import ModelAdmin, TabularInline
from django.utils.safestring import mark_safe
from django import forms
from django.conf import settings


class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=forms.Textarea, required=False)
    category = forms.ModelChoiceField(queryset=ArticleCategory.objects.all(),widget=forms.Select)
    author_name = forms.CharField(required=False)

    class Media:
        extend=False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'articles/js/init.js')
        css = {'all':('articles/css/style.css',)}


# class ArticleCategoryInline(admin.TabularInline):
#     model = Article.category.through

def bulk_publishing(modeladmin, request, queryset):
    queryset.update(is_published=True)


bulk_publishing.short_description = "Publish selected articles"


class ArticleLinkedUrlInline(TabularInline):
    model = ArticleLinkedUrl
    extra = 0
    can_delete = True
    verbose_name = "Linked Url"
    verbose_name_plural = "Linked Urls"


class LinkedArticleInline(TabularInline):
    model = LinkedArticle
    fk_name = 'article'
    extra = 0
    can_delete = True
    autocomplete_fields = ['linked_article']
    verbose_name = "Linked Article"
    verbose_name_plural = "Linked Articles"


class ArticleAdmin(VersionAdmin):
    form = ArticleForm
    model = Article
    list_display = ('title', 'updated_at', 'created_at', 'created_by', 'preview')
    search_fields = ['title']
    fields = ['title', 'body', 'header_image', 'header_image_alt', 'category', 'url', 'description', 'keywords',
              'icon_tag', 'icon', 'author_name', 'is_published', 'preview']
    readonly_fields = ['icon_tag', 'preview']
    inlines = [ArticleLinkedUrlInline, LinkedArticleInline]
    actions = [bulk_publishing]

    def preview(self, instance):
        if instance.id:
            app_url = settings.CONSUMER_APP_DOMAIN
            if app_url:
                html = '''<a href='%s/%s' target=_blank>Preview</a>''' % (app_url, instance.url)
                return mark_safe(html)
        else:
            return mark_safe('''<span></span>''')

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user

        if hasattr(obj, 'url'):
            obj.url = obj.url.strip('/')
            url_components = obj.url.split('-')
            identifier = obj.category.identifier
            if ArticleCategory.objects.filter(identifier=url_components[-1]).exists():
                    if url_components[-1] == identifier:
                        pass
                    else:
                        obj.url = '%s-%s' % ('-'.join(url_components[:-1]), identifier)
            else:
                obj.url = '%s-%s' % (obj.url, identifier)

        super().save_model(request, obj, form, change)


class ArticleImageAdmin(ModelAdmin):
    fields = ['image_tag']
    readonly_fields = ['image_tag']


admin.site.register(Article, ArticleAdmin)
admin.site.register(ArticleImage, ArticleImageAdmin)
admin.site.register(ArticleCategory)
