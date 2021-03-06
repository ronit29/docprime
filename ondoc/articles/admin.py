from django.contrib.gis import admin
from import_export import resources, fields
from import_export.admin import ImportExportMixin
from import_export.formats import base_formats
from dal import autocomplete
from .models import Article, ArticleImage, ArticleCategory, ArticleLinkedUrl, LinkedArticle, ArticleContentBox, \
    MedicineSpecialization
from reversion.admin import VersionAdmin
from django.contrib.admin import ModelAdmin, TabularInline
from django.utils.safestring import mark_safe
from django import forms
from django.conf import settings

class ArticleForm(forms.ModelForm):
    body = forms.CharField(widget=forms.Textarea, required=False)
    category = forms.ModelChoiceField(queryset=ArticleCategory.objects.all(), widget=forms.Select)
    author_name = forms.CharField(required=False)

    class Media:
        extend=False
        # js = ('ckedit/js/ckeditor.js', 'articles/js/init.js')   # ckeditor-5 replaced with ckeditor-4.11.4
        js = ('https://cdn.ckeditor.com/4.11.4/standard-all/ckeditor.js', 'articles/js/init.js')
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
    fields = ['heading_title', 'title', 'body', 'header_image', 'header_image_alt', 'category', 'url', 'description',
              'keywords', 'icon_tag', 'icon', 'author_name', 'published_date', 'is_published', 'preview', 'author',
              'pharmeasy_url', 'pharmeasy_product_id', 'is_widget_available']
    readonly_fields = ['icon_tag', 'preview']
    inlines = [ArticleLinkedUrlInline, LinkedArticleInline]
    actions = [bulk_publishing]
    autocomplete_fields = ['author']

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
            identifier = obj.category.identifier.lower()
            if ArticleCategory.objects.filter(identifier__iexact=url_components[-1]).exists():
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


class MedicineSpecializationResource(resources.ModelResource):
    class Meta:
        model = MedicineSpecialization
        fields = ('medicine', 'specialization', 'id')


class MedicineSpecializationForm(forms.ModelForm):
    class Media:
        extend = True
        js = ('/admin/js/vendor/jquery/jquery.js', 'admin/js/jquery.init.js', )
        css = {'all': ('admin/css/vendor/select2/select2.css', 'admin/css/autocomplete.css')}

    class Meta:
        model = MedicineSpecialization
        fields = ('__all__')
        widgets = {
            'medicine': autocomplete.ModelSelect2(url='medicine-autocomplete'),
            'specialization': autocomplete.ModelSelect2(url='practicespecialization-autocomplete')
        }


class MedicineSpecializationAdmin(ImportExportMixin, VersionAdmin):
    model = MedicineSpecialization
    formats = (base_formats.XLS, )
    form = MedicineSpecializationForm
    resource_class = MedicineSpecializationResource
    list_display = ('medicine', 'specialization', )
    search_fields = ('medicine__title', 'specialization__name', )


admin.site.register(Article, ArticleAdmin)
admin.site.register(ArticleImage, ArticleImageAdmin)
admin.site.register(ArticleCategory)
admin.site.register(ArticleContentBox)
admin.site.register(MedicineSpecialization, MedicineSpecializationAdmin)

# class FluentCommentsInline(TabularInline):
#     model = Comment
#     can_delete = True
#     verbose_name = "Reply"

#admin.site.register(FluentComment, FluentCommentsAdmin)

class MedicineAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Article.objects.none()
        medicine_category = ArticleCategory.objects.filter(identifier='mddp').first()
        if medicine_category:
            queryset = Article.objects.filter(category_id=medicine_category.id)
        else:
            queryset = Article.objects.none()

        if self.q:
            queryset = queryset.filter(title__istartswith=self.q)

        return queryset.distinct()

