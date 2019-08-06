import datetime

from django.contrib.contenttypes.models import ContentType
from fluent_comments import appsettings
from django.contrib.admin.widgets import AdminTextInputWidget
from django.core.exceptions import ImproperlyConfigured
from django.utils.encoding import force_text
from django.utils.html import escape, format_html
from django.utils.translation import ugettext_lazy as _
from django.utils.safestring import mark_safe
from threadedcomments.models import ThreadedComment
from django.conf import settings
from django.contrib.gis import admin

from fluent_comments.models import FluentComment

from .forms import CustomCommentForm

from .models import CustomComment
# Register your models here.

# class CustomCommentAdmin(VersionAdmin):
#     form = CustomCommentForm
# admin.site.register(CustomComment, CustomCommentAdmin)

if appsettings.USE_THREADEDCOMMENTS:
    # Avoid getting weird situations where both comment apps are loaded in the admin.
    if not hasattr(settings, 'COMMENTS_APP') or settings.COMMENTS_APP == 'comments':
        raise ImproperlyConfigured("To use 'threadedcomments', specify the COMMENTS_APP as well")

    from threadedcomments.admin import ThreadedCommentsAdmin as CommentsAdminBase
else:
    from django_comments.admin import CommentsAdmin as CommentsAdminBase


class CustomCommentsAdmin(CommentsAdminBase):
    """
    Updated admin screen for the comments model.
    The ability to add a comment is removed here, the admin screen can only be used for managing comments.
    Adding comments can happen at the frontend instead.
    The fieldsets are more logically organized, and the generic relation is a readonly field instead of a massive pulldown + textarea.
    The class supports both the standard ``django_comments`` and the ``threadedcomments`` applications.
    """
    form = CustomCommentForm
    fieldsets = [
        (_('Content'),
           {'fields': ('object_link', 'user_name', 'user_email', 'comment', 'submit_date', 'author', )}
        ),
        (_('Add new comment'),
         {'fields': ('new_comment','name','email','is_author',)}
         ),

        (_('Account information'),
           {'fields': ('user', )},
        ),
        (_('Moderation'),
           {'fields': ('is_public',)}
        ),
    ]

    list_display = ('user_name_col', 'email', 'comment', 'object_link',  'submit_date', 'is_public')
    readonly_fields = ('parent_comment', 'object_link', 'user', 'ip_address', 'submit_date','comment',
                       'user_name', 'user_email', 'user_url', 'title', 'author', )
    #inlines = [FluentCommentsInline]

    # Adjust the fieldsets for threaded comments
    if appsettings.USE_THREADEDCOMMENTS:
        fieldsets[0][1]['fields'] = ('object_link', 'user_name', 'user_email', 'comment', 'submit_date', 'author', )  # add title field.
        fieldsets.insert(2, ('Hierarchy', {'fields': ('parent_comment', )}))
        raw_id_fields = ('parent',)

    def save_model(self, request, obj, form, change):
        #obj.user = request.user
        super().save_model(request, obj, form, change)
        new_comment = form.cleaned_data.get('new_comment')
        is_author = form.cleaned_data.get('is_author')
        name = form.cleaned_data.get('name')
        email = form.cleaned_data.get('email')

        if new_comment:
            if is_author:
                email = ''
                name = ''

            comment = FluentComment.objects.create(object_pk=obj.object_pk,
                                                   comment=new_comment,
                                                   content_type_id=obj.content_type_id,
                                                   site_id=obj.site_id, parent=obj,
                                                   user_name=name,
                                                   user_email=email, user=request.user,
                                                   is_public=True,  is_removed=False)

            if comment.id:
                if comment.content_type and comment.content_type == ContentType.objects.get(model="hospital"):
                    author_id = None
                elif obj and obj.content_object and obj.content_object.author and obj.content_object.author.id:
                    author_id = obj.content_object.author.id
                    custom_comment = CustomComment.objects.create(author_id=author_id, comment_id=comment.id)
                else:
                    author_id = None

    def author(self, comment):
        if comment:
            if comment.content_type and comment.content_type==ContentType.objects.get(model="hospital"):
                return "docprime"
            elif comment.content_object and comment.content_object.author.id:
                author = comment.content_object.author
                author_id = author.id
                author_name = author.name
            return mark_safe('<a target="_blank" href="/admin/doctor/doctor/%s/change/">%s</a>' % (
                author_id, author_name))

        return None

    def parent_comment(self, comment):
        if comment.parent:
            return mark_safe('<a target="_blank" href="/admin/fluent_comments/fluentcomment/%s/change/">%s</a>' % (comment.parent.id, comment.parent.comment))
        else:
            return None

    def get_queryset(self, request):
        return super(CustomCommentsAdmin, self).get_queryset(request).select_related('user')

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
        # elif comment.user_id:
        #     return force_text(comment.user)
        else:
            return None

    user_name_col.short_description = _("user's name")

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'title':
            kwargs['widget'] = AdminTextInputWidget
        return super(CustomCommentsAdmin, self).formfield_for_dbfield(db_field, **kwargs)


admin.site.unregister(ThreadedComment)

admin.site.register(FluentComment, CustomCommentsAdmin)
