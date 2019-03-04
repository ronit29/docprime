from django.db import models
from django_comments.models import Comment

from ondoc.authentication.models import TimeStampedModel

# Create your models here.
# from django_comments.abstracts import CommentAbstractModel
#
#
# class CustomComment(CommentAbstractModel):
#     author_id = models.IntegerField(blank=True, null=True)
#
#     class Meta:
#         db_table = 'custom_comment'
from ondoc.doctor.models import Doctor


class CustomComment(TimeStampedModel):
    author = models.ForeignKey(Doctor, null=True, blank=True, related_name='author_comments', on_delete=models.SET_NULL)
    comment = models.ForeignKey(Comment, null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        db_table = 'custom_comments'
