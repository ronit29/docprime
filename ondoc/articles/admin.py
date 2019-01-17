import nested_admin
from django.contrib.gis import admin
from django_comments.models import Comment, CommentFlag
from fluent_comments.admin import CommentModel
from raven.utils import urlparse
from django.utils.safestring import mark_safe

from .models import Article, ArticleImage, ArticleCategory, ArticleLinkedUrl, LinkedArticle, ArticleContentBox
from reversion.admin import VersionAdmin
from django.contrib.admin import ModelAdmin, TabularInline
from django.utils.safestring import mark_safe
from django import forms
from django.conf import settings
from threadedcomments.models import ThreadedComment
from fluent_comments.models import FluentComment
from fluent_comments import appsettings
from django.contrib.admin.widgets import AdminTextInputWidget
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import force_text
from django.utils.html import escape, format_html
from django.utils.translation import ugettext_lazy as _


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
    fields = ['heading_title','title', 'body', 'header_image', 'header_image_alt', 'category', 'url', 'description', 'keywords',
              'icon_tag', 'icon', 'author_name', 'published_date', 'is_published', 'preview', 'author']
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


admin.site.register(Article, ArticleAdmin)
admin.site.register(ArticleImage, ArticleImageAdmin)
admin.site.register(ArticleCategory)
admin.site.register(ArticleContentBox)
admin.site.unregister(ThreadedComment)
admin.site.unregister(FluentComment)

if appsettings.USE_THREADEDCOMMENTS:
    # Avoid getting weird situations where both comment apps are loaded in the admin.
    if not hasattr(settings, 'COMMENTS_APP') or settings.COMMENTS_APP == 'comments':
        raise ImproperlyConfigured("To use 'threadedcomments', specify the COMMENTS_APP as well")

    from threadedcomments.admin import ThreadedCommentsAdmin as CommentsAdminBase
else:
    from django_comments.admin import CommentsAdmin as CommentsAdminBase


class FluentCommentsAdmin(CommentsAdminBase):
    """
    Updated admin screen for the comments model.
    The ability to add a comment is removed here, the admin screen can only be used for managing comments.
    Adding comments can happen at the frontend instead.
    The fieldsets are more logically organized, and the generic relation is a readonly field instead of a massive pulldown + textarea.
    The class supports both the standard ``django_comments`` and the ``threadedcomments`` applications.
    """

    fieldsets = [
        (_('Content'),
           {'fields': ('object_link', 'user_name', 'user_email', 'user_url', 'comment', 'submit_date',)}
        ),
        (_('Account information'),
           {'fields': ('user', 'ip_address',)},
        ),
        (_('Moderation'),
           {'fields': ('is_public', 'is_removed')}
        ),
    ]

    list_display = ('user_name_col', 'object_link', 'ip_address', 'submit_date', 'is_public', 'is_removed')
    readonly_fields = ('parent_comment', 'parent_link', 'object_link', 'user', 'ip_address', 'submit_date',)

    # Adjust the fieldsets for threaded comments
    if appsettings.USE_THREADEDCOMMENTS:
        fieldsets[0][1]['fields'] = ('object_link', 'user_name', 'user_email', 'user_url', 'title', 'comment', 'submit_date',)  # add title field.
        fieldsets.insert(2, ('Hierarchy', {'fields': ('parent_comment', 'parent_link')}))
        raw_id_fields = ('parent',)

    def parent_comment(self, comment):
        if comment.parent:
            return mark_safe('<a target="_blank" href="/admin/fluent_comments/fluentcomment/%s/change/">%s</a>' % (comment.parent.id, comment.parent.comment))
        else:
            return None

    def parent_link(self, comment):
        return 'admin/fluent_comments/fluentcomment/'+ str(comment.parent.id) +'/change/'

    def get_queryset(self, request):
        return super(FluentCommentsAdmin, self).get_queryset(request).select_related('user')

    def object_link(self, comment):
        try:
            object = comment.content_object
        except AttributeError:
            return ''

        if not object:
            return ''

        title = force_text(object)
        if hasattr(object, 'get_absolute_url'):
            return format_html(u'<a href="{0}">{1}</a>', object.get_absolute_url(), title)
        else:
            return title

    object_link.short_description = _("Page")
    object_link.allow_tags = True

    def user_name_col(self, comment):
        if comment.user_name:
            return comment.user_name
        elif comment.user_id:
            return force_text(comment.user)
        else:
            return None

    user_name_col.short_description = _("user's name")

    def has_add_permission(self, request):
        return False

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'title':
            kwargs['widget'] = AdminTextInputWidget
        return super(FluentCommentsAdmin, self).formfield_for_dbfield(db_field, **kwargs)

admin.site.register(CommentModel, FluentCommentsAdmin)


# admin.site.register(DjangoComments)

# class CommentsAdmin(admin.ModelAdmin):
#     fields = ['content_type','object_pk', 'site', 'article_url', 'user', 'user_name', 'user_email', 'user_url', 'comment', 'submit_date', 'ip_address', 'is_public', 'is_removed']
#     readonly_fields = ['article_url']
#
#     # fieldsets = (
#     #     (
#     #         _('Content'),
#     #         {'fields': ('user', 'object_pk', 'user_name', 'user_email', 'user_url', 'comment')}
#     #     ),
#     #     (
#     #         _('Metadata'),
#     #         {'fields': ('submit_date', 'ip_address', 'is_public', 'is_removed')}
#     #     ),
#     #
#     # )
#     #
#
#     list_display = ('name', 'object_pk',  'article_url', 'ip_address', 'submit_date', 'is_public', 'is_removed')
#     list_filter = ('submit_date', 'is_public', 'is_removed')
#     ordering = ('-submit_date',)
#     actions = ["approve_comments", "remove_comments"]
#
#     def article_url(self, obj):
#         return obj.content_object.url
#
#     def approve_comments(self, request, queryset):
#         self._bulk_flag(request, queryset, perform_approve,
#                         lambda n: ungettext('approved', 'approved', n))
#
#     # approve_comments.short_description = _("Approve selected comments")
#
#     def remove_comments(self, request, queryset):
#         self._bulk_flag(request, queryset, perform_delete,
#                         lambda n: ungettext('removed', 'removed', n))
#
#     # remove_comments.short_description = _("Remove selected comments")
#
#     def _bulk_flag(self, request, queryset, action, done_message):
#         """
#         Flag, approve, or remove some comments from an admin action. Actually
#         calls the `action` argument to perform the heavy lifting.
#         """
#         n_comments = 0
#         for comment in queryset:
#             action(request, comment)
#             n_comments += 1
#
#         msg = ungettext('%(count)s comment was successfully %(action)s.',
#                         '%(count)s comments were successfully %(action)s.',
#                         n_comments)
#         self.message_user(request, msg % {'count': n_comments, 'action': done_message(n_comments)})

# admin.site.register(Comment, CommentsAdmin)
# admin.site.register(CommentFlag)


